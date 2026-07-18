"""JSON and CSV export for OptimizationResult."""

import csv
import json
from pathlib import Path

from decision_intelligence.contracts import OptimizationResult


def export_json(result: OptimizationResult, path: str | Path) -> Path:
    """Write the full OptimizationResult as indented JSON."""
    path = Path(path)
    data = result.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def export_csv(result: OptimizationResult, path: str | Path) -> Path:
    """
    Write allocations as CSV.  Each row is one allocation item.
    Nested metadata fields are flattened with a 'meta_' prefix.
    A second sheet (appended as a second CSV block with a blank separator)
    contains the sensitivity analysis.
    """
    path = Path(path)

    rows: list[dict] = []
    for a in result.allocations:
        row = {
            "asset_id":          a.asset_id,
            "label":             a.label,
            "allocated_value":   round(a.allocated_value, 2),
            "allocated_fraction": round(a.allocated_fraction, 6),
        }
        for k, v in a.metadata.items():
            row[f"meta_{k}"] = v
        rows.append(row)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # ── Section 1: summary ──
        writer.writerow(["# OPTIMIZATION RESULT SUMMARY"])
        writer.writerow(["request_id",    result.request_id])
        writer.writerow(["domain",        result.domain])
        writer.writerow(["status",        result.status.value])
        writer.writerow(["objective",     round(result.objective_value, 6)])
        writer.writerow(["baseline",      round(result.baseline_value, 6)])
        writer.writerow(["improvement",   round(result.improvement, 6)])
        writer.writerow(["improvement_pct", round(result.improvement_pct, 4)])
        writer.writerow(["timestamp",     str(result.timestamp)])
        writer.writerow([])

        # ── Section 2: allocations ──
        writer.writerow(["# ALLOCATIONS"])
        if rows:
            fieldnames = list(rows[0].keys())
            writer.writerow(fieldnames)
            for row in rows:
                writer.writerow([row.get(f, "") for f in fieldnames])
        writer.writerow([])

        # ── Section 3: sensitivities ──
        writer.writerow(["# SENSITIVITY ANALYSIS"])
        writer.writerow(
            ["parameter", "shadow_price", "range_lower", "range_upper", "interpretation"]
        )
        for s in result.sensitivities:
            writer.writerow([
                s.parameter,
                round(s.shadow_price, 6),
                round(s.range_lower, 2),
                round(s.range_upper, 2),
                s.interpretation,
            ])
        writer.writerow([])

        # ── Section 4: binding constraints ──
        writer.writerow(["# BINDING CONSTRAINTS"])
        for bc in result.binding_constraints:
            writer.writerow([bc])
        writer.writerow([])

        # ── Section 5: scenarios ──
        if result.scenario_results:
            writer.writerow(["# SCENARIOS"])
            writer.writerow(["scenario", "status", "objective", "improvement_pct"])
            for name, sr in result.scenario_results.items():
                writer.writerow(
                    [
                        name,
                        sr.status.value,
                        round(sr.objective_value, 4),
                        round(sr.improvement_pct, 4),
                    ]
                )

    return path
