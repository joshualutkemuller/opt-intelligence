"""Run evidence packet generator for workflow proof-of-concept demos."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from typing import Any


def build_workflow_evidence_packet(
    *,
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    preset: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a structured evidence packet from a completed workflow run."""

    result = _record(response.get("result"))
    plan = _record(response.get("plan"))
    payload = _record(payload)
    preset = _record(preset)
    workflow = _record(workflow)
    steps = [_record(step) for step in result.get("step_results", []) or []]
    final_step = steps[-1] if steps else {}
    final_result = _record(final_step.get("result"))
    validation = _record(result.get("validation_summary"))
    dependency = _record(result.get("dependency_summary"))
    explanation = _record(result.get("explanation_report"))
    workflow_id = (
        result.get("workflow_id")
        or workflow.get("workflow_id")
        or payload.get("workflow")
        or plan.get("workflow_id")
        or "workflow-demo"
    )

    return {
        "packet_type": "workflow_run_evidence",
        "schema_version": 1,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "overview": {
            "title": result.get("name") or workflow.get("name") or plan.get("name"),
            "workflow_id": workflow_id,
            "preset_id": preset.get("preset_id"),
            "preset_name": preset.get("name"),
            "audience": preset.get("audience"),
            "portfolio_id": payload.get("portfolio_id")
            or _dig(final_step, "request", "portfolio_id"),
            "seed": payload.get("seed"),
            "status": result.get("status"),
            "step_count": len(steps),
            "validation_passed": bool(validation.get("passed", False)),
            "dependency_effect_count": dependency.get("total_effects", 0),
            "final_domain": final_result.get("domain") or final_step.get("domain"),
            "final_status": final_result.get("status") or final_step.get("status"),
            "final_objective_value": final_result.get("objective_value"),
            "final_improvement_pct": final_result.get("improvement_pct"),
        },
        "demo_story": {
            "description": preset.get("description") or workflow.get("description"),
            "talking_points": _list(preset.get("talking_points")),
            "success_criteria": _list(preset.get("success_criteria")),
            "summary": explanation.get("summary") or result.get("explanation"),
            "recommendation": explanation.get("overall_recommendation"),
            "key_drivers": _list(explanation.get("key_drivers")),
            "next_actions": _list(explanation.get("next_actions")),
        },
        "inputs": {
            "payload": payload,
            "workflow_context": payload.get("context", {}),
            "plan_context": plan.get("context", {}),
        },
        "solver_evidence": [_solver_summary(step) for step in steps],
        "allocation_evidence": [_allocation_summary(step) for step in steps],
        "dependency_evidence": {
            "summary": dependency,
            "effects": _list(dependency.get("context_changes")),
        },
        "validation_evidence": {
            "summary": validation,
            "step_reports": [_step_validation_summary(step) for step in steps],
        },
        "raw_response": {
            "plan": plan,
            "result": result,
        },
    }


def generate_workflow_evidence_pdf(packet: dict[str, Any]) -> bytes:
    """Render the evidence packet as a compact PDF for stakeholder sharing."""

    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:  # pragma: no cover - exercised only without optional extra
        raise RuntimeError(
            "PDF evidence export requires reportlab. Install the project with the ingest extra."
        ) from exc

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    overview = _record(packet.get("overview"))
    story = _record(packet.get("demo_story"))
    elements: list[Any] = [
        Paragraph(str(overview.get("title") or "Workflow Evidence Packet"), title_style),
        Paragraph(
            f"Generated {packet.get('generated_at')} for "
            f"{overview.get('portfolio_id') or 'unknown portfolio'}.",
            body_style,
        ),
        Spacer(1, 10),
        _table(
            [
                ["Workflow", overview.get("workflow_id")],
                ["Preset", overview.get("preset_name")],
                ["Status", overview.get("status")],
                ["Validation", "Passed" if overview.get("validation_passed") else "Review"],
                ["Dependency effects", overview.get("dependency_effect_count")],
                ["Final improvement", _format_pct(overview.get("final_improvement_pct"))],
            ],
            widths=[1.55 * inch, 5.15 * inch],
        ),
        Spacer(1, 12),
        Paragraph("Presenter Proof Points", heading_style),
        *_bullet_paragraphs(_list(story.get("talking_points")), body_style),
        Spacer(1, 8),
        Paragraph("Success Criteria", heading_style),
        *_bullet_paragraphs(_list(story.get("success_criteria")), body_style),
        Spacer(1, 8),
        Paragraph("Solver Evidence", heading_style),
        _solver_table(_list(packet.get("solver_evidence"))),
        Spacer(1, 8),
        Paragraph("Dependency Evidence", heading_style),
        _dependency_table(_list(_dig(packet, "dependency_evidence", "effects"))),
        Spacer(1, 8),
        Paragraph("Validation Evidence", heading_style),
        _validation_table(_record(_dig(packet, "validation_evidence", "summary"))),
        Spacer(1, 8),
        Paragraph("Allocation Evidence", heading_style),
        _allocation_table(_list(packet.get("allocation_evidence"))),
        Spacer(1, 8),
        Paragraph("Recommendation", heading_style),
        Paragraph(str(story.get("recommendation") or "Review workflow output."), body_style),
    ]
    document.build(elements)
    return buffer.getvalue()


def encode_pdf_base64(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("ascii")


def _solver_summary(step: dict[str, Any]) -> dict[str, Any]:
    result = _record(step.get("result"))
    metadata = _record(result.get("solver_metadata"))
    return {
        "step_id": step.get("step_id"),
        "name": step.get("name"),
        "domain": step.get("domain"),
        "status": result.get("status") or step.get("status"),
        "solver_backend": metadata.get("solver_backend"),
        "problem_type": metadata.get("problem_type"),
        "solver_method": metadata.get("solver_method"),
        "objective_value": result.get("objective_value"),
        "baseline_value": result.get("baseline_value"),
        "improvement_pct": result.get("improvement_pct"),
        "binding_constraints": _list(result.get("binding_constraints")),
    }


def _allocation_summary(step: dict[str, Any]) -> dict[str, Any]:
    result = _record(step.get("result"))
    return {
        "step_id": step.get("step_id"),
        "name": step.get("name"),
        "domain": step.get("domain"),
        "allocation_count": len(result.get("allocations", []) or []),
        "allocations": [_record(item) for item in result.get("allocations", []) or []],
    }


def _step_validation_summary(step: dict[str, Any]) -> dict[str, Any]:
    result = _record(step.get("result"))
    report = _record(result.get("validation_report"))
    return {
        "step_id": step.get("step_id"),
        "name": step.get("name"),
        "domain": step.get("domain"),
        "passed": report.get("passed"),
        "recommendation": report.get("recommendation"),
        "risk_score": report.get("risk_score"),
        "warnings": _list(report.get("warnings")),
        "violations": _list(report.get("violations")),
    }


def _table(rows: list[list[Any]], widths: list[float] | None = None) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table([[str(cell) for cell in row] for row in rows], colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef7")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d3e3")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f7f9fc")],
                ),
            ]
        )
    )
    return table


def _solver_table(items: list[Any]) -> Any:
    rows = [["Step", "Domain", "Solver", "Problem", "Objective", "Improvement"]]
    for item in items:
        record = _record(item)
        rows.append(
            [
                record.get("name"),
                record.get("domain"),
                record.get("solver_backend"),
                record.get("problem_type"),
                _format_number(record.get("objective_value")),
                _format_pct(record.get("improvement_pct")),
            ]
        )
    return _table(rows)


def _dependency_table(items: list[Any]) -> Any:
    rows = [["Source", "Target", "Context", "Before", "After", "Reason"]]
    for item in items[:8]:
        record = _record(item)
        rows.append(
            [
                record.get("source_step_id"),
                record.get("target_step_id"),
                record.get("target_context_key"),
                _format_number(record.get("previous_value")),
                _format_number(record.get("new_value")),
                record.get("reason"),
            ]
        )
    if len(rows) == 1:
        rows.append(["None", "", "", "", "", "No dependency effects recorded."])
    return _table(rows)


def _validation_table(summary: dict[str, Any]) -> Any:
    from reportlab.lib.units import inch

    return _table(
        [
            ["Metric", "Value"],
            ["Passed", "Yes" if summary.get("passed") else "No"],
            ["Total steps", summary.get("total_steps", 0)],
            ["Warnings", summary.get("warning_count", 0)],
            ["Violations", summary.get("violation_count", 0)],
        ],
        widths=[1.55 * inch, 5.15 * inch],
    )


def _allocation_table(items: list[Any]) -> Any:
    rows = [["Step", "Domain", "Allocations", "Top allocation"]]
    for item in items:
        record = _record(item)
        allocations = [_record(allocation) for allocation in record.get("allocations", []) or []]
        top = allocations[0] if allocations else {}
        rows.append(
            [
                record.get("name"),
                record.get("domain"),
                record.get("allocation_count"),
                f"{top.get('label', 'n/a')} ({_format_number(top.get('allocated_value'))})",
            ]
        )
    return _table(rows)


def _bullet_paragraphs(items: list[Any], style: Any) -> list[Any]:
    from reportlab.platypus import Paragraph

    entries = items or ["None recorded."]
    return [Paragraph(f"- {item}", style) for item in entries]


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _format_number(value: Any) -> str:
    try:
        return f"{float(value):,.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "n/a"
