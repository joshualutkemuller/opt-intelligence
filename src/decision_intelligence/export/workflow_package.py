"""Stakeholder-ready HTML package generator for workflow demo runs."""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from typing import Any


def generate_workflow_demo_package(
    *,
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    preset: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
) -> str:
    """Build a self-contained HTML report for a completed workflow demo."""

    result = _record(response.get("result"))
    plan = _record(response.get("plan"))
    preset = _record(preset)
    workflow = _record(workflow)
    payload = _record(payload)
    package = _build_package(
        result=result,
        plan=plan,
        preset=preset,
        workflow=workflow,
        payload=payload,
        generated_at=datetime.now(UTC).isoformat(),
    )
    return _render_html(package)


def _build_package(
    *,
    result: dict[str, Any],
    plan: dict[str, Any],
    preset: dict[str, Any],
    workflow: dict[str, Any],
    payload: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    validation = _record(result.get("validation_summary"))
    dependency = _record(result.get("dependency_summary"))
    explanation = _record(result.get("explanation_report"))
    steps = [_record(step) for step in result.get("step_results", []) or []]
    final_step = steps[-1] if steps else {}
    final_result = _record(final_step.get("result"))

    return {
        "generated_at": generated_at,
        "title": result.get("name") or workflow.get("name") or plan.get("name") or "Workflow Demo",
        "workflow_id": (
            result.get("workflow_id")
            or workflow.get("workflow_id")
            or payload.get("workflow")
        ),
        "status": result.get("status", "unknown"),
        "portfolio_id": payload.get("portfolio_id") or _dig(final_step, "request", "portfolio_id"),
        "preset_name": preset.get("name", "Custom workflow run"),
        "preset_description": preset.get("description", ""),
        "audience": preset.get("audience", "stakeholder demo"),
        "summary": explanation.get("summary") or result.get("explanation", ""),
        "recommendation": explanation.get("overall_recommendation", ""),
        "validation_passed": bool(validation.get("passed", False)),
        "validation": validation,
        "dependency": dependency,
        "key_drivers": _list(explanation.get("key_drivers")),
        "dependency_changes": _list(explanation.get("dependency_changes")),
        "risks": _list(explanation.get("risks")),
        "next_actions": _list(explanation.get("next_actions")),
        "talking_points": _list(preset.get("talking_points")),
        "success_criteria": _list(preset.get("success_criteria")),
        "final_result": {
            "domain": final_result.get("domain") or final_step.get("domain"),
            "status": final_result.get("status", final_step.get("status", "unknown")),
            "objective_value": final_result.get("objective_value"),
            "baseline_value": final_result.get("baseline_value"),
            "improvement": final_result.get("improvement"),
            "improvement_pct": final_result.get("improvement_pct"),
            "allocation_count": len(final_result.get("allocations", []) or []),
        },
        "steps": [_step_summary(step) for step in steps],
        "payload": payload,
        "raw_response": {"plan": plan, "result": result},
    }


def _step_summary(step: dict[str, Any]) -> dict[str, Any]:
    result = _record(step.get("result"))
    summary = _record(step.get("summary"))
    return {
        "step_id": step.get("step_id", ""),
        "name": step.get("name", ""),
        "domain": step.get("domain", ""),
        "status": step.get("status", result.get("status", "unknown")),
        "objective_value": result.get("objective_value", summary.get("objective_value")),
        "baseline_value": result.get("baseline_value", summary.get("baseline_value")),
        "improvement_pct": result.get("improvement_pct", summary.get("improvement_pct")),
        "allocation_count": len(result.get("allocations", []) or []),
        "binding_constraints": _list(result.get("binding_constraints")),
        "dependency_effects": [_record(item) for item in step.get("dependency_effects", []) or []],
    }


def _render_html(package: dict[str, Any]) -> str:
    payload_json = json.dumps(package, indent=2, sort_keys=True, default=str)
    title = _escape(str(package["title"]))
    status_class = "ok" if package.get("status") == "complete" else "review"
    validation_class = "ok" if package.get("validation_passed") else "review"
    generated_at = _escape(str(package["generated_at"]))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - Demo Package</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #647084;
      --line: #d9e0ea;
      --panel: #ffffff;
      --page: #f4f7fb;
      --blue: #285c9e;
      --green: #18745a;
      --amber: #9b6415;
      --red: #a94442;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    header {{
      background: #111827;
      color: white;
      padding: 32px 40px;
    }}
    header p {{ color: #cbd5e1; margin: 8px 0 0; max-width: 880px; }}
    main {{ padding: 28px 40px 44px; max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin: 0; letter-spacing: 0; }}
    h2 {{ font-size: 18px; margin: 0 0 14px; }}
    h3 {{ font-size: 14px; margin: 18px 0 8px; }}
    .meta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }}
    .pill {{
      border: 1px solid rgba(255,255,255,.24);
      border-radius: 999px;
      padding: 5px 10px;
      color: #e5e7eb;
      font-size: 12px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, .05);
    }}
    .wide {{ grid-column: 1 / -1; }}
    .half {{ grid-column: span 2; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
    .metric strong {{ display: block; font-size: 22px; }}
    .ok {{ color: var(--green); }}
    .review {{ color: var(--amber); }}
    .muted {{ color: var(--muted); }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 5px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 600; }}
    code, pre {{ font-family: "SFMono-Regular", Consolas, monospace; }}
    pre {{
      overflow: auto;
      background: #0f172a;
      color: #dbeafe;
      border-radius: 8px;
      padding: 16px;
      font-size: 12px;
      max-height: 520px;
    }}
    @media print {{
      header {{ background: white; color: var(--ink); border-bottom: 1px solid var(--line); }}
      header p, .pill {{ color: var(--ink); }}
      main {{ padding: 20px; }}
      .card {{ box-shadow: none; break-inside: avoid; }}
    }}
    @media (max-width: 860px) {{
      header, main {{ padding-left: 20px; padding-right: 20px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .half {{ grid-column: 1 / -1; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>{_package_summary(package)}</p>
    <div class="meta">
      <span class="pill">Workflow: {_escape(str(package.get("workflow_id") or "unknown"))}</span>
      <span class="pill">Portfolio: {_escape(str(package.get("portfolio_id") or "unknown"))}</span>
      <span class="pill">Preset: {_escape(str(package.get("preset_name") or "custom"))}</span>
      <span class="pill">Generated: {generated_at}</span>
    </div>
  </header>
  <main>
    <section class="grid">
      {_metric("Workflow Status", str(package.get("status", "unknown")).title(), status_class)}
      {_metric(
          "Validation",
          "Passed" if package.get("validation_passed") else "Review",
          validation_class,
      )}
      {_metric("Dependency Effects", str(_dig(package, "dependency", "total_effects") or 0), "")}
      {_metric(
          "Final Improvement",
          _format_pct(_dig(package, "final_result", "improvement_pct")),
          "ok",
      )}
      <article class="card wide">
        <h2>Recommendation</h2>
        <p>{_escape(str(package.get("recommendation") or "Review workflow output before use."))}</p>
      </article>
      {_list_card("Presenter Talking Points", package.get("talking_points"), "half")}
      {_list_card("Success Criteria", package.get("success_criteria"), "half")}
      {_list_card("Key Drivers", package.get("key_drivers"), "half")}
      {_list_card("Risks", package.get("risks"), "half")}
      {_list_card("Dependency Changes", package.get("dependency_changes"), "half")}
      {_list_card("Next Actions", package.get("next_actions"), "half")}
      <article class="card wide">
        <h2>Workflow Timeline</h2>
        {_steps_table(package.get("steps", []))}
      </article>
      <article class="card wide">
        <h2>Validation Summary</h2>
        {_validation_table(_record(package.get("validation")))}
      </article>
      <article class="card wide">
        <h2>Audit Payload</h2>
        <p class="muted">
          The embedded payload below makes this package reproducible from the
          local demo API.
        </p>
        <pre>{_escape(payload_json)}</pre>
      </article>
    </section>
  </main>
</body>
</html>
"""


def _metric(label: str, value: str, class_name: str) -> str:
    return (
        '<article class="card metric">'
        f"<span>{_escape(label)}</span>"
        f'<strong class="{_escape(class_name)}">{_escape(value)}</strong>'
        "</article>"
    )


def _package_summary(package: dict[str, Any]) -> str:
    return _escape(
        str(package.get("summary") or "Shareable Decision Intelligence workflow package.")
    )


def _list_card(title: str, items: Any, class_name: str = "") -> str:
    entries = _list(items)
    body = (
        "".join(f"<li>{_escape(str(item))}</li>" for item in entries)
        or "<li>None recorded.</li>"
    )
    return (
        f'<article class="card {class_name}">'
        f"<h2>{_escape(title)}</h2><ul>{body}</ul></article>"
    )


def _steps_table(steps: list[dict[str, Any]]) -> str:
    rows = []
    for step in steps:
        constraints = ", ".join(_list(step.get("binding_constraints"))[:3]) or "None"
        rows.append(
            "<tr>"
            f"<td>{_escape(str(step.get('name', '')))}</td>"
            f"<td>{_escape(str(step.get('domain', '')))}</td>"
            f"<td>{_escape(str(step.get('status', '')))}</td>"
            f"<td>{_format_number(step.get('objective_value'))}</td>"
            f"<td>{_format_pct(step.get('improvement_pct'))}</td>"
            f"<td>{_escape(str(step.get('allocation_count', 0)))}</td>"
            f"<td>{_escape(constraints)}</td>"
            f"<td>{_escape(str(len(step.get('dependency_effects', []) or [])))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="8">No workflow steps recorded.</td></tr>')
    return (
        "<table><thead><tr>"
        "<th>Step</th><th>Domain</th><th>Status</th><th>Objective</th>"
        "<th>Improvement</th><th>Allocations</th><th>Binding Constraints</th><th>Deps</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _validation_table(validation: dict[str, Any]) -> str:
    warnings = _list(validation.get("warnings"))
    violations = _list(validation.get("violations"))
    rows = [
        ("Passed", "Yes" if validation.get("passed") else "No"),
        ("Total steps", validation.get("total_steps", 0)),
        ("Total checks", validation.get("total_checks", 0)),
        ("Warnings", len(warnings)),
        ("Violations", len(violations)),
    ]
    summary = "".join(
        f"<tr><th>{_escape(str(label))}</th><td>{_escape(str(value))}</td></tr>"
        for label, value in rows
    )
    issues = "".join(
        f"<li>{_escape(str(item))}</li>" for item in [*warnings, *violations]
    ) or "<li>No warnings or violations recorded.</li>"
    return f"<table><tbody>{summary}</tbody></table><h3>Issues</h3><ul>{issues}</ul>"


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dig(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
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


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
