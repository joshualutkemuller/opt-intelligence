#!/usr/bin/env python
"""Evaluate the LLM collateral-schedule parser against hand-labelled gold sets.

Gold files live in ``examples/collateral/gold/<doc-stem>.json``:

    { "doc": "<filename>", "match": {"haircut_tolerance_pct": 0.25},
      "entries": [ {"asset_class": "GOVT", "haircut_pct": 2.0,
                    "max_maturity_years": 1.0, ...}, ... ] }

Scoring — greedy multiset matching:
  * A predicted entry matches a gold entry when asset_class is equal and
    |haircut diff| <= tolerance; ties prefer an exact max_maturity match.
  * precision / recall / F1 over matched entries.
  * haircut MAE over matched pairs.
  * maturity accuracy over matched pairs where gold states a maturity.
  * rating accuracy over matched pairs where gold states a rating floor.

Modes (isolate the input-quality lever, same schema both ways):
  * improved  — table-aware pdfplumber extraction + chunked calls (default)
  * baseline  — flat pypdf text, single call truncated to the char budget
                (the pre-accuracy-bundle input path)

Usage:
    python scripts/eval_collateral_llm.py [--mode improved|baseline]
        [--model llama3.2] [--gold-dir examples/collateral/gold]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))  # for run_collateral_llm import

from collateral_schedule.llm_parser import (
    _entries_from_schedule,
    _extract_text_chunked,
    _pdf_bytes_to_text,
    parse_pdf_with_llm,
)
from run_collateral_llm import resolve_default_provider  # same scripts/ dir


def predict(
    doc_path: Path, provider: Any, mode: str, max_text_chars: int = 24_000
) -> list[dict[str, Any]]:
    raw = doc_path.read_bytes()
    if mode == "improved":
        return parse_pdf_with_llm(raw, provider, max_text_chars=max_text_chars)
    # baseline: flat text, single truncated call (pre-bundle input path)
    text = (
        _pdf_bytes_to_text(raw)
        if raw[:5] == b"%PDF-"
        else raw.decode("utf-8", errors="replace")
    )
    schedule = _extract_text_chunked(
        provider, text[:max_text_chars], max_text_chars=max_text_chars, max_chunks=1
    )
    return _entries_from_schedule(schedule)


def match_entries(
    preds: list[dict[str, Any]], gold: list[dict[str, Any]], hc_tol: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Greedy multiset matching gold→pred on (class, haircut±tol); prefer same maturity."""
    unmatched = list(range(len(preds)))
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for g in gold:
        best_i, best_score = None, None
        for i in unmatched:
            p = preds[i]
            if p.get("asset_class") != g["asset_class"]:
                continue
            g_hc, p_hc = g.get("haircut_pct"), p.get("haircut_pct")
            if g_hc is None or p_hc is None or abs(g_hc - p_hc) > hc_tol:
                continue
            # score: prefer exact maturity, then closer haircut
            mat_bonus = 0 if p.get("max_maturity_years") == g.get("max_maturity_years") else 1
            score = (mat_bonus, abs(g_hc - p_hc))
            if best_score is None or score < best_score:
                best_i, best_score = i, score
        if best_i is not None:
            unmatched.remove(best_i)
            pairs.append((g, preds[best_i]))
    return pairs


def score_doc(
    preds: list[dict[str, Any]], gold_spec: dict[str, Any]
) -> dict[str, Any]:
    gold = gold_spec["entries"]
    tol = float(gold_spec.get("match", {}).get("haircut_tolerance_pct", 0.25))
    pairs = match_entries(preds, gold, tol)
    tp = len(pairs)
    precision = tp / len(preds) if preds else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    hc_err = [abs(g["haircut_pct"] - p["haircut_pct"]) for g, p in pairs]
    mat_pairs = [(g, p) for g, p in pairs if g.get("max_maturity_years") is not None]
    mat_ok = sum(1 for g, p in mat_pairs if p.get("max_maturity_years") == g["max_maturity_years"])
    rat_pairs = [(g, p) for g, p in pairs if g.get("rating_floor")]
    rat_ok = sum(1 for g, p in rat_pairs if p.get("rating_floor") == g["rating_floor"])
    return {
        "n_pred": len(preds),
        "n_gold": len(gold),
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "haircut_mae": sum(hc_err) / len(hc_err) if hc_err else None,
        "maturity_acc": (mat_ok / len(mat_pairs)) if mat_pairs else None,
        "rating_acc": (rat_ok / len(rat_pairs)) if rat_pairs else None,
    }


def fmt(v: float | None, pct: bool = True) -> str:
    if v is None:
        return "  —  "
    return f"{v * 100:5.1f}%" if pct else f"{v:5.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("improved", "baseline"), default="improved")
    ap.add_argument("--gold-dir", default="examples/collateral/gold")
    ap.add_argument("--docs-dir", default="examples/collateral")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    provider, kind = resolve_default_provider(args.model)
    if provider is None:
        print("No LLM provider available (need API keys or a running Ollama).", file=sys.stderr)
        return 2
    print(
        f"mode={args.mode}  provider={kind}  model={getattr(provider, 'model', '?')}  "
        f"native_pdf={getattr(provider, 'supports_native_pdf', False)}\n"
    )

    gold_files = sorted(Path(args.gold_dir).glob("*.json"))
    if not gold_files:
        print(f"No gold files in {args.gold_dir}", file=sys.stderr)
        return 1

    rows = []
    for gf in gold_files:
        spec = json.loads(gf.read_text())
        doc = Path(args.docs_dir) / spec["doc"]
        t0 = time.time()
        try:
            preds = predict(doc, provider, args.mode)
        except Exception as exc:  # noqa: BLE001
            print(f"{spec['doc']}: ERROR {exc}")
            continue
        s = score_doc(preds, spec)
        s["doc"] = spec["doc"]
        s["secs"] = time.time() - t0
        rows.append(s)

    print(f"{'document':<52} {'gold':>4} {'pred':>4} {'tp':>3}  {'prec':>6} {'rec':>6} {'f1':>6}  {'hcMAE':>5} {'matAcc':>6} {'ratAcc':>6} {'secs':>5}")
    for s in rows:
        print(
            f"{s['doc']:<52} {s['n_gold']:>4} {s['n_pred']:>4} {s['tp']:>3}  "
            f"{fmt(s['precision'])} {fmt(s['recall'])} {fmt(s['f1'])}  "
            f"{fmt(s['haircut_mae'], pct=False)} {fmt(s['maturity_acc'])} {fmt(s['rating_acc'])} "
            f"{s['secs']:>4.0f}s"
        )
    if rows:
        n = len(rows)
        print(
            f"{'MEAN':<52} {'':>4} {'':>4} {'':>3}  "
            f"{fmt(sum(r['precision'] for r in rows) / n)} "
            f"{fmt(sum(r['recall'] for r in rows) / n)} "
            f"{fmt(sum(r['f1'] for r in rows) / n)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
