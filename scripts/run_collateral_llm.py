#!/usr/bin/env python
"""Run the LLM collateral-schedule parser over documents in examples/collateral/.

This is a *consumer* of the standalone ``collateral_schedule`` library: it wires
up an LLM provider (via ``decision_intelligence.llm``) and injects it. The
library itself imports nothing from ``decision_intelligence``.

Provider selection (provider-agnostic):
  * If ANTHROPIC_API_KEY / OPENAI_API_KEY / DI_LLM_* is configured, that provider
    is used (Anthropic reads PDFs natively).
  * Otherwise, if a local Ollama server is reachable, it is used by default
    (OpenAI-compatible endpoint at http://localhost:11434/v1).

Usage:
    python scripts/run_collateral_llm.py [--dir examples/collateral]
        [--model llama3.2] [--glob '*.pdf'] [--persist]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

from collateral_schedule import CollateralDatabase, parse_pdf_with_llm
from decision_intelligence.llm import resolve_provider
from decision_intelligence.llm.openai_provider import OpenAIProvider

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _ollama_up(base: str = OLLAMA_URL, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def resolve_default_provider(model: str | None):
    """Configured provider if any, else local Ollama, else None."""
    provider = resolve_provider()  # honors DI_LLM_* / ANTHROPIC / OPENAI creds
    if provider is not None:
        return provider, "configured"
    if _ollama_up():
        return (
            OpenAIProvider(
                model=model or "llama3.2",
                base_url=f"{OLLAMA_URL}/v1",
                api_key="ollama",
            ),
            "ollama",
        )
    return None, "none"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="examples/collateral", help="Directory of documents.")
    ap.add_argument("--glob", default="*.pdf", help="Filename glob (default: *.pdf).")
    ap.add_argument("--model", default=None, help="Model id (Ollama default: llama3.2).")
    ap.add_argument("--persist", action="store_true", help="Persist entries to a SQLite DB.")
    ap.add_argument(
        "--db", default="/tmp/collateral_llm_demo.db", help="DB path when --persist is set."
    )
    args = ap.parse_args()

    provider, kind = resolve_default_provider(args.model)
    if provider is None:
        print(
            "No LLM provider available. Set ANTHROPIC_API_KEY / OPENAI_API_KEY / "
            "DI_LLM_* , or start a local Ollama server (ollama serve).",
            file=sys.stderr,
        )
        return 2

    model = getattr(provider, "model", "?")
    native = getattr(provider, "supports_native_pdf", False)
    print(f"Provider: {kind}  model={model}  native_pdf={native}\n")

    docs = sorted(Path(args.dir).glob(args.glob))
    if not docs:
        print(f"No documents matching {args.glob!r} in {args.dir}", file=sys.stderr)
        return 1

    db = CollateralDatabase(args.db) if args.persist else None
    cp = agr = None
    if db is not None:
        cp = db.create_counterparty("LLM Demo Counterparty")
        agr = db.create_agreement(counterparty_id=cp["id"], margin_type="OTHER")

    total = 0
    for doc in docs:
        print(f"── {doc.name} " + "─" * max(0, 60 - len(doc.name)))
        t0 = time.time()
        try:
            entries, schedule = parse_pdf_with_llm(
                doc.read_bytes(), provider, return_schedule=True
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}\n")
            continue
        dt = time.time() - t0

        meta = []
        if schedule.detected_margin_type:
            meta.append(f"margin={schedule.detected_margin_type}")
        if schedule.base_currency:
            meta.append(f"ccy={schedule.base_currency}")
        meta_str = ("  [" + ", ".join(meta) + "]") if meta else ""
        print(f"  {len(entries)} entries in {dt:.1f}s{meta_str}")

        for e in entries[:12]:
            hc = e.get("haircut_pct")
            hc_s = f"{hc:g}%" if hc is not None else "—"
            elig = "✓" if e.get("eligible") else "✗"
            print(
                f"    {elig} {e['asset_class']:<8} hc={hc_s:<7} "
                f"rating={e.get('rating_floor', '—')!s:<6} {e.get('notes', '') or ''}"[:100]
            )
        if len(entries) > 12:
            print(f"    … and {len(entries) - 12} more")
        print()

        total += len(entries)
        if db is not None and agr is not None and entries:
            db.insert_entries(agr["id"], entries, replace=False)

    print(f"TOTAL: {total} entries across {len(docs)} document(s).")
    if db is not None and agr is not None:
        print("Summary:", db.summary(agr["id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
