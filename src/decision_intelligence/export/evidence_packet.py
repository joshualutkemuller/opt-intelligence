"""Run evidence packet generator for workflow proof-of-concept demos."""

from __future__ import annotations

import base64
import csv
from datetime import UTC, datetime
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


def build_workflow_evidence_packet(
    *,
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    preset: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    audit_narrative: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a structured evidence packet from a completed workflow run."""

    result = _record(response.get("result"))
    plan = _record(response.get("plan"))
    payload = _record(payload)
    preset = _record(preset)
    workflow = _record(workflow)
    comparison = _record(comparison)
    steps = [_record(step) for step in result.get("step_results", []) or []]
    final_step = steps[-1] if steps else {}
    final_result = _record(final_step.get("result"))
    validation = _record(result.get("validation_summary"))
    dependency = _record(result.get("dependency_summary"))
    explanation = _record(result.get("explanation_report"))
    policy_ingestion = _policy_ingestion_evidence(payload)
    governance_evidence = _governance_evidence(steps, policy_ingestion)
    comparison_evidence = _comparison_evidence(comparison)
    operational_evidence = _operational_evidence(steps)
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
            "source_policy": _dig(policy_ingestion, "summary", "filename"),
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
        "policy_ingestion_evidence": policy_ingestion,
        "solver_evidence": [_solver_summary(step) for step in steps],
        "allocation_evidence": [_allocation_summary(step) for step in steps],
        "operational_evidence": operational_evidence,
        "dependency_evidence": {
            "summary": dependency,
            "effects": _list(dependency.get("context_changes")),
        },
        "governance_evidence": governance_evidence,
        "comparison_evidence": comparison_evidence,
        "validation_evidence": {
            "summary": validation,
            "step_reports": [_step_validation_summary(step) for step in steps],
        },
        "audit_narrative": _record(audit_narrative),
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
                ["Source policy", overview.get("source_policy") or "None"],
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
        Paragraph("Policy Ingestion Evidence", heading_style),
        _policy_table(_record(packet.get("policy_ingestion_evidence"))),
        Spacer(1, 8),
        Paragraph("Solver Evidence", heading_style),
        _solver_table(_list(packet.get("solver_evidence"))),
        Spacer(1, 8),
        Paragraph("Governance Evidence", heading_style),
        _governance_table(_record(packet.get("governance_evidence"))),
        Spacer(1, 8),
        Paragraph("Comparison Evidence", heading_style),
        _comparison_table(_record(packet.get("comparison_evidence"))),
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
        Paragraph("Operational Action Evidence", heading_style),
        _operational_table(_list(_dig(packet, "operational_evidence", "actions"))),
        Spacer(1, 8),
        Paragraph("Recommendation", heading_style),
        Paragraph(str(story.get("recommendation") or "Review workflow output."), body_style),
        *_narrative_elements(packet, heading_style, body_style),
    ]
    document.build(elements)
    return buffer.getvalue()


def encode_pdf_base64(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("ascii")


def generate_workflow_evidence_csvs(packet: dict[str, Any]) -> list[dict[str, str]]:
    """Render evidence packet tables as CSV artifacts."""

    tables = _evidence_tables(packet)
    csv_files = []
    for table_name, rows in tables.items():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
        csv_files.append(
            {
                "filename": f"{table_name}.csv",
                "content_type": "text/csv",
                "content": output.getvalue(),
            }
        )
    return csv_files


def generate_workflow_evidence_xlsx(packet: dict[str, Any]) -> bytes:
    """Render evidence packet tables as a compact XLSX workbook."""

    tables = _evidence_tables(packet)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as workbook:
        _write_xlsx_static_files(workbook, list(tables))
        for index, (table_name, rows) in enumerate(tables.items(), start=1):
            workbook.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet_xml(rows),
            )
    return buffer.getvalue()


def _narrative_elements(
    packet: dict[str, Any],
    heading_style: Any,
    body_style: Any,
) -> list[Any]:
    """Return PDF elements for the audit narrative section, if present."""
    try:
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        return []

    narrative = _record(packet.get("audit_narrative"))
    markdown = str(narrative.get("markdown") or "").strip()
    if not markdown:
        return []

    elements: list[Any] = [
        Spacer(1, 10),
        Paragraph("Audit Narrative", heading_style),
        Paragraph(
            f"Generated: {narrative.get('generated_at', '')}",
            body_style,
        ),
    ]
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            elements.append(Spacer(1, 4))
        elif stripped.startswith("# "):
            pass  # already shown as section heading
        elif stripped.startswith("## "):
            elements.append(Paragraph(stripped[3:], heading_style))
        elif stripped.startswith("- "):
            elements.append(Paragraph(f"• {stripped[2:]}", body_style))
        else:
            elements.append(Paragraph(stripped, body_style))
    return elements


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


def _policy_ingestion_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    policy = _record(payload.get("policy_ingestion"))
    context_policy = _record(_dig(payload, "context", "policy_ingestion"))
    if not policy and not context_policy:
        return {
            "summary": {"present": False},
            "applied_inputs": {},
            "extracted_fields": [],
        }

    summary = _record(policy.get("review_summary"))
    metadata = _record(_dig(policy, "context_patch", "policy_ingestion"))
    filename = (
        metadata.get("filename")
        or context_policy.get("filename")
        or policy.get("filename")
        or payload.get("filename")
    )
    return {
        "summary": {
            "present": True,
            "workflow_id": policy.get("workflow_id") or payload.get("workflow"),
            "source_type": policy.get("source_type") or context_policy.get("source_type"),
            "filename": filename,
            "backend": summary.get("backend") or context_policy.get("backend"),
            "ready": summary.get("ready"),
            "applied_to_workflow": context_policy.get("applied_to_workflow", True),
            "missing_required": _list(summary.get("missing_required")),
            "warnings": _list(summary.get("warnings")),
        },
        "applied_inputs": _record(policy.get("input_values")),
        "context_patch": _record(policy.get("context_patch")),
        "extracted_fields": [_record(field) for field in _list(policy.get("extracted_fields"))],
    }


def _governance_evidence(
    steps: list[dict[str, Any]],
    policy_ingestion: dict[str, Any],
) -> dict[str, Any]:
    records = []
    for step in steps:
        governance = _record(_dig(step, "result", "governance"))
        if not governance:
            continue
        records.append(
            {
                "step_id": step.get("step_id"),
                "name": step.get("name"),
                "domain": step.get("domain"),
                **governance,
            }
        )

    highest_tier = max(
        (int(record.get("tier", 0) or 0) for record in records),
        default=0,
    )
    pending = [record for record in records if record.get("status") == "pending"]
    escalated = [record for record in records if record.get("escalated")]
    policy_summary = _record(policy_ingestion.get("summary"))
    return {
        "summary": {
            "record_count": len(records),
            "highest_tier": highest_tier,
            "pending_count": len(pending),
            "escalated_count": len(escalated),
            "policy_ingestion_present": bool(policy_summary.get("present")),
            "policy_driven_constraint_change": bool(
                _dig(
                    policy_ingestion,
                    "context_patch",
                    "governance",
                    "production_constraint_change",
                )
            ),
        },
        "records": records,
        "pending_approval_ids": [
            record.get("approval_id") for record in pending if record.get("approval_id")
        ],
        "escalations": [
            {
                "step_id": record.get("step_id"),
                "tier": record.get("tier"),
                "base_tier": record.get("base_tier"),
                "reason": record.get("escalation_reason"),
                "factors": _record(record.get("governance_factors")),
            }
            for record in escalated
        ],
    }


def _comparison_evidence(comparison: dict[str, Any]) -> dict[str, Any]:
    if not comparison:
        return {
            "summary": {"present": False, "name": None, "run_count": 0},
            "runs": [],
            "insights": [],
        }
    body = _record(comparison.get("comparison") or comparison)
    return {
        "summary": {
            "present": True,
            "name": comparison.get("name") or body.get("name") or "Workflow comparison",
            "created_at": comparison.get("created_at"),
            "run_count": body.get("run_count", 0),
            "baseline_run_id": body.get("baseline_run_id"),
            "best_run_id": body.get("best_run_id"),
            "comparison_ready": body.get("comparison_ready", False),
        },
        "runs": [_record(run) for run in _list(body.get("runs"))],
        "insights": _list(body.get("insights")),
    }


def _operational_evidence(steps: list[dict[str, Any]]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for step in steps:
        result = _record(step.get("result"))
        domain = str(step.get("domain") or result.get("domain") or "")
        attachments = _record(_dig(result, "solver_metadata", "domain_attachments"))

        if domain == "treasury_operations":
            for allocation in [_record(item) for item in _list(result.get("allocations"))]:
                metadata = _record(allocation.get("metadata"))
                actions.append(
                    {
                        "step_id": step.get("step_id"),
                        "domain": domain,
                        "action_type": "cash_transfer",
                        "action_id": allocation.get("asset_id"),
                        "label": allocation.get("label"),
                        "status": result.get("status"),
                        "amount": allocation.get("allocated_value"),
                        "currency": metadata.get("currency"),
                        "source": metadata.get("from_account_id"),
                        "target": metadata.get("to_account_id"),
                        "route": metadata.get("rail_id"),
                        "cost": metadata.get("cost"),
                        "priority": "",
                        "recommended_action": "execute_transfer",
                        "reason": "least-cost cutoff-feasible route",
                    }
                )

        if domain == "margin_operations":
            for call in [_record(item) for item in _list(attachments.get("assigned_calls"))]:
                actions.append(
                    {
                        "step_id": step.get("step_id"),
                        "domain": domain,
                        "action_type": "assigned_margin_call",
                        "action_id": call.get("call_id"),
                        "label": call.get("counterparty"),
                        "status": result.get("status"),
                        "amount": call.get("amount"),
                        "currency": "USD",
                        "source": call.get("counterparty"),
                        "target": "margin_operations_queue",
                        "route": f"order_{call.get('assigned_order')}",
                        "cost": call.get("capacity_minutes"),
                        "priority": call.get("priority_score"),
                        "recommended_action": call.get("recommended_action"),
                        "reason": "assigned inside current capacity window",
                    }
                )
            for call in [_record(item) for item in _list(attachments.get("deferred_calls"))]:
                actions.append(
                    {
                        "step_id": step.get("step_id"),
                        "domain": domain,
                        "action_type": "deferred_margin_call",
                        "action_id": call.get("call_id"),
                        "label": call.get("counterparty"),
                        "status": result.get("status"),
                        "amount": call.get("amount"),
                        "currency": "USD",
                        "source": call.get("counterparty"),
                        "target": "deferred_queue",
                        "route": call.get("defer_reason"),
                        "cost": call.get("ops_minutes"),
                        "priority": call.get("priority_score"),
                        "recommended_action": call.get("recommended_action"),
                        "reason": call.get("defer_reason"),
                    }
                )

    return {
        "summary": {
            "present": bool(actions),
            "action_count": len(actions),
            "domains": sorted(
                {str(action.get("domain")) for action in actions if action.get("domain")}
            ),
        },
        "actions": actions,
    }


def _evidence_tables(packet: dict[str, Any]) -> dict[str, list[list[Any]]]:
    overview = _record(packet.get("overview"))
    policy = _record(packet.get("policy_ingestion_evidence"))
    governance = _record(packet.get("governance_evidence"))
    comparison = _record(packet.get("comparison_evidence"))
    validation = _record(_dig(packet, "validation_evidence", "summary"))
    return {
        "overview": [
            ["Field", "Value"],
            ["Generated at", packet.get("generated_at")],
            ["Workflow", overview.get("workflow_id")],
            ["Preset", overview.get("preset_name")],
            ["Portfolio", overview.get("portfolio_id")],
            ["Status", overview.get("status")],
            ["Source policy", overview.get("source_policy")],
            ["Validation passed", overview.get("validation_passed")],
            ["Dependency effects", overview.get("dependency_effect_count")],
        ],
        "workflow_steps": _workflow_step_rows(_list(packet.get("solver_evidence"))),
        "allocations": _allocation_rows(_list(packet.get("allocation_evidence"))),
        "operational_actions": _operational_action_rows(
            _list(_dig(packet, "operational_evidence", "actions"))
        ),
        "dependencies": _dependency_rows(_list(_dig(packet, "dependency_evidence", "effects"))),
        "validation": _validation_rows(validation),
        "governance": _governance_rows(governance),
        "policy_fields": _policy_rows(policy),
        "comparison": _comparison_rows(comparison),
        "audit_narrative": _narrative_rows(_record(packet.get("audit_narrative"))),
    }


def _workflow_step_rows(items: list[Any]) -> list[list[Any]]:
    rows = [
        [
            "Step ID",
            "Step",
            "Domain",
            "Status",
            "Solver",
            "Problem",
            "Objective",
            "Baseline",
            "Improvement %",
            "Binding Constraints",
        ]
    ]
    for item in items:
        record = _record(item)
        rows.append(
            [
                record.get("step_id"),
                record.get("name"),
                record.get("domain"),
                record.get("status"),
                record.get("solver_backend"),
                record.get("problem_type"),
                record.get("objective_value"),
                record.get("baseline_value"),
                record.get("improvement_pct"),
                "; ".join(str(value) for value in _list(record.get("binding_constraints"))),
            ]
        )
    return _with_empty_row(rows, "No workflow steps recorded.")


def _allocation_rows(items: list[Any]) -> list[list[Any]]:
    rows = [
        [
            "Step ID",
            "Step",
            "Domain",
            "Allocation Label",
            "Allocated Value",
            "Allocated Fraction",
        ]
    ]
    for item in items:
        record = _record(item)
        for allocation in [_record(value) for value in _list(record.get("allocations"))]:
            rows.append(
                [
                    record.get("step_id"),
                    record.get("name"),
                    record.get("domain"),
                    allocation.get("label"),
                    allocation.get("allocated_value"),
                    allocation.get("allocated_fraction"),
                ]
            )
    return _with_empty_row(rows, "No allocations recorded.")


def _dependency_rows(items: list[Any]) -> list[list[Any]]:
    rows = [["Source", "Target", "Context Key", "Before", "After", "Delta", "Reason"]]
    for item in [_record(value) for value in items]:
        rows.append(
            [
                item.get("source_step_id"),
                item.get("target_step_id"),
                item.get("target_context_key"),
                item.get("previous_value"),
                item.get("new_value"),
                item.get("delta"),
                item.get("reason"),
            ]
        )
    return _with_empty_row(rows, "No dependency effects recorded.")


def _operational_action_rows(items: list[Any]) -> list[list[Any]]:
    rows = [
        [
            "Step ID",
            "Domain",
            "Action Type",
            "Action ID",
            "Label",
            "Status",
            "Amount",
            "Currency",
            "Source",
            "Target",
            "Route",
            "Cost / Minutes",
            "Priority",
            "Recommended Action",
            "Reason",
        ]
    ]
    for item in [_record(value) for value in items]:
        rows.append(
            [
                item.get("step_id"),
                item.get("domain"),
                item.get("action_type"),
                item.get("action_id"),
                item.get("label"),
                item.get("status"),
                item.get("amount"),
                item.get("currency"),
                item.get("source"),
                item.get("target"),
                item.get("route"),
                item.get("cost"),
                item.get("priority"),
                item.get("recommended_action"),
                item.get("reason"),
            ]
        )
    return _with_empty_row(rows, "No operational actions recorded.")


def _validation_rows(summary: dict[str, Any]) -> list[list[Any]]:
    rows = [
        ["Metric", "Value"],
        ["Passed", summary.get("passed")],
        ["Total steps", summary.get("total_steps")],
        ["Total checks", summary.get("total_checks")],
        ["Warnings", summary.get("warning_count")],
        ["Violations", summary.get("violation_count")],
    ]
    for warning in _list(summary.get("warnings")):
        rows.append(["Warning", warning])
    for violation in _list(summary.get("violations")):
        rows.append(["Violation", violation])
    return rows


def _governance_rows(governance: dict[str, Any]) -> list[list[Any]]:
    rows = [
        [
            "Step ID",
            "Domain",
            "Tier",
            "Status",
            "Required",
            "Escalated",
            "Reason",
            "Approval ID",
        ]
    ]
    for record in [_record(value) for value in _list(governance.get("records"))]:
        rows.append(
            [
                record.get("step_id"),
                record.get("domain"),
                record.get("tier"),
                record.get("status"),
                record.get("required"),
                record.get("escalated"),
                record.get("escalation_reason"),
                record.get("approval_id"),
            ]
        )
    return _with_empty_row(rows, "No governance records recorded.")


def _policy_rows(policy: dict[str, Any]) -> list[list[Any]]:
    rows = [["Key", "Label", "Value", "Confidence", "Applied", "Evidence"]]
    for field in [_record(value) for value in _list(policy.get("extracted_fields"))]:
        rows.append(
            [
                field.get("key"),
                field.get("label"),
                field.get("value"),
                field.get("confidence"),
                field.get("applied"),
                field.get("evidence"),
            ]
        )
    return _with_empty_row(rows, "No policy fields extracted.")


def _comparison_rows(comparison: dict[str, Any]) -> list[list[Any]]:
    summary = _record(comparison.get("summary"))
    rows = [
        [
            "Set Name",
            "Run ID",
            "Label",
            "Workflow",
            "Status",
            "Final Domain",
            "Final Objective",
            "Improvement %",
            "Improvement Delta",
            "Avg Improvement %",
            "Dependencies",
            "Warnings",
            "Violations",
            "Expected Return",
            "Volatility",
            "Sharpe",
            "Best Run",
            "Baseline",
        ]
    ]
    for run in [_record(value) for value in _list(comparison.get("runs"))]:
        deltas = _record(run.get("deltas"))
        rows.append(
            [
                summary.get("name"),
                run.get("run_id"),
                run.get("label"),
                run.get("workflow_id"),
                run.get("status"),
                run.get("final_domain"),
                run.get("final_objective_value"),
                run.get("final_improvement_pct"),
                deltas.get("final_improvement_pct"),
                run.get("average_improvement_pct"),
                run.get("total_dependency_effects"),
                run.get("warning_count"),
                run.get("violation_count"),
                run.get("expected_return"),
                run.get("volatility"),
                run.get("sharpe"),
                run.get("run_id") == summary.get("best_run_id"),
                run.get("run_id") == summary.get("baseline_run_id"),
            ]
        )
    for insight in _list(comparison.get("insights")):
        rows.append([summary.get("name"), "Insight", insight])
    return _with_empty_row(rows, "No comparison set attached.")


def _with_empty_row(rows: list[list[Any]], message: str) -> list[list[Any]]:
    if len(rows) == 1:
        rows.append([message])
    return rows


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


def _policy_table(policy: dict[str, Any]) -> Any:
    summary = _record(policy.get("summary"))
    rows = [["Field", "Value", "Confidence"]]
    if not summary.get("present"):
        rows.append(["Policy", "No IPS ingestion payload was attached.", "n/a"])
        return _table(rows)
    fields = [_record(field) for field in _list(policy.get("extracted_fields"))]
    for field in fields[:8]:
        rows.append(
            [
                field.get("label") or field.get("key"),
                field.get("value"),
                _format_pct(float(field.get("confidence", 0)) * 100),
            ]
        )
    if len(rows) == 1:
        rows.append(["Policy", "No fields extracted.", "n/a"])
    return _table(rows)


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


def _governance_table(governance: dict[str, Any]) -> Any:
    summary = _record(governance.get("summary"))
    rows = [
        ["Metric", "Value"],
        ["Highest tier", summary.get("highest_tier", 0)],
        ["Escalated approvals", summary.get("escalated_count", 0)],
        ["Pending approvals", summary.get("pending_count", 0)],
        [
            "IPS-driven constraint change",
            "Yes" if summary.get("policy_driven_constraint_change") else "No",
        ],
    ]
    return _table(rows)


def _comparison_table(comparison: dict[str, Any]) -> Any:
    summary = _record(comparison.get("summary"))
    rows = [["Run", "Improvement", "Delta", "Deps", "Review"]]
    for run in [_record(value) for value in _list(comparison.get("runs"))][:6]:
        deltas = _record(run.get("deltas"))
        rows.append(
            [
                run.get("label"),
                _format_pct(run.get("final_improvement_pct")),
                _format_pct(deltas.get("final_improvement_pct")),
                run.get("total_dependency_effects"),
                f"{run.get('warning_count', 0)}W/{run.get('violation_count', 0)}V",
            ]
        )
    if len(rows) == 1:
        rows.append([summary.get("name") or "None", "No comparison set attached.", "", "", ""])
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


def _operational_table(items: list[Any]) -> Any:
    rows = [["Step", "Type", "Action", "Amount", "Route", "Recommendation"]]
    for item in [_record(value) for value in items[:8]]:
        rows.append(
            [
                item.get("step_id"),
                item.get("action_type"),
                item.get("label") or item.get("action_id"),
                _format_number(item.get("amount")),
                item.get("route"),
                item.get("recommended_action"),
            ]
        )
    if len(rows) == 1:
        rows.append(["None", "", "No operational actions recorded.", "", "", ""])
    return _table(rows)


def _write_xlsx_static_files(workbook: ZipFile, sheet_names: list[str]) -> None:
    workbook.writestr(
        "[Content_Types].xml",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index in range(1, len(sheet_names) + 1)
        )
        + "</Types>",
    )
    workbook.writestr(
        "_rels/.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>",
    )
    workbook.writestr(
        "xl/workbook.xml",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(
            f'<sheet name="{_xml_escape(_sheet_name(name))}" sheetId="{index}" '
            f'r:id="rId{index}"/>'
            for index, name in enumerate(sheet_names, start=1)
        )
        + "</sheets></workbook>",
    )
    workbook.writestr(
        "xl/_rels/workbook.xml.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(sheet_names) + 1)
        )
        + "</Relationships>",
    )


def _worksheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            cells.append(_cell_xml(reference, value))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )


def _cell_xml(reference: str, value: Any) -> str:
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = "" if value is None else str(value)
    return (
        f'<c r="{reference}" t="inlineStr"><is><t>{_xml_escape(text)}</t></is></c>'
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_name(value: str) -> str:
    safe = "".join(character for character in value.title() if character not in "[]:*?/\\")
    return safe[:31] or "Sheet"


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
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


def _narrative_rows(narrative: dict[str, Any]) -> list[list[Any]]:
    if not narrative:
        return [["Field", "Value"], ["Audit narrative", "Not generated"]]
    rows: list[list[Any]] = [["Field", "Value"]]
    rows.append(["Title", narrative.get("title")])
    rows.append(["Generated at", narrative.get("generated_at")])
    rows.append(["Decision summary", narrative.get("decision_summary")])
    rows.append(["Outcome", narrative.get("outcome")])
    for item in _list(narrative.get("constraint_context")):
        rows.append(["Constraint context", item])
    for item in _list(narrative.get("approval_chain")):
        rows.append(["Approval chain", item])
    for item in _list(narrative.get("risk_flags")):
        rows.append(["Risk flag", item])
    for item in _list(narrative.get("timeline")):
        rows.append(["Timeline", item])
    return rows


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
