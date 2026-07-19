"""Generate operational optimizer MP4 storyboard examples.

Run from the repository root:
    .venv/bin/python scripts/generate_operational_optimizer_video_examples.py
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.ingestion import ingest_policy_document
from decision_intelligence.production_optimizers import (
    CashMovementProductionAdapter,
    MarginCallWorkflowProductionAdapter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "video_examples" / "operations"
TMP_DIR = REPO_ROOT / "tmp" / "video" / "operations_storyboard"
WIDTH = 1280
HEIGHT = 720
FPS = 10
SOURCE_SECONDS = 96
PLAYBACK_SPEED = 1.5
SECONDS = round(SOURCE_SECONDS / PLAYBACK_SPEED)

COLORS = {
    "bg": "#071014",
    "panel": "#101B21",
    "panel2": "#16252C",
    "panel3": "#20343A",
    "ink": "#F1F5F4",
    "muted": "#9CB2B4",
    "faint": "#678184",
    "line": "#2E454B",
    "green": "#89D185",
    "blue": "#7AA2F7",
    "amber": "#E9C46A",
    "cyan": "#5FD4CF",
    "red": "#F07178",
}


@dataclass(frozen=True)
class Scene:
    start: int
    stage: int
    title: str
    caption: str
    action: str
    left_title: str
    left_rows: list[str]
    right_title: str
    right_rows: list[str]
    workflow_label: str
    accent: str
    chat: list[tuple[str, str]] | None = None
    bars: list[tuple[str, float, str]] | None = None
    title_card: str | None = None
    total_stages: int = 8


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)

    cash_result = _run_cash_movement()
    margin_result = _run_margin_workflow()
    _render_video(
        _build_scenes(cash_result, margin_result),
        OUT_DIR / "treasury-margin-operations-storyboard-demo.mp4",
        cash_result,
        margin_result,
        source_seconds=SOURCE_SECONDS,
        playback_speed=PLAYBACK_SPEED,
        frames_subdir="combined",
    )

    treasury_ingestion, treasury_result = _run_cash_movement_from_policy()
    margin_ingestion, policy_margin_result = _run_margin_workflow_from_policy()
    _render_video(
        _build_treasury_policy_scenes(treasury_ingestion, treasury_result),
        OUT_DIR / "treasury-policy-ingestion-cash-movement-demo.mp4",
        treasury_result,
        policy_margin_result,
        source_seconds=90,
        playback_speed=1.25,
        frames_subdir="treasury_policy",
    )
    _render_video(
        _build_margin_policy_scenes(margin_ingestion, policy_margin_result),
        OUT_DIR / "margin-call-sla-triage-policy-demo.mp4",
        treasury_result,
        policy_margin_result,
        source_seconds=90,
        playback_speed=1.25,
        frames_subdir="margin_policy",
    )
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def _render_video(
    scenes: list[Scene],
    output: Path,
    cash_result,
    margin_result,
    *,
    source_seconds: int,
    playback_speed: float,
    frames_subdir: str,
) -> None:
    frames_dir = TMP_DIR / frames_subdir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    seconds = round(source_seconds / playback_speed)
    total_frames = seconds * FPS
    for frame_idx in range(total_frames):
        second = min((frame_idx / FPS) * playback_speed, source_seconds)
        scene = _scene_at(scenes, second)
        image = _draw_frame(scene, cash_result, margin_result, second / source_seconds)
        image.save(frames_dir / f"frame_{frame_idx:05d}.png")

    _encode_mp4(frames_dir, output)


def _run_cash_movement():
    request = OptimizationRequest(
        domain="treasury_operations",
        portfolio_id="PORT_TREASURY_OPS",
        objective=Objective(
            name="minimize_cash_movement_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="transfer_cost",
        ),
        context={
            "data_snapshot_id": "SNAP_CASHMOVE_VIDEO",
            "cutoff_hour": 15,
            "cash_balances": [
                {
                    "account_id": "SRC_1",
                    "entity": "Broker Dealer",
                    "currency": "USD",
                    "available_cash": 150_000_000,
                    "minimum_buffer": 20_000_000,
                },
                {
                    "account_id": "SRC_2",
                    "entity": "Bank Entity",
                    "currency": "USD",
                    "available_cash": 80_000_000,
                    "minimum_buffer": 15_000_000,
                },
            ],
            "funding_requirements": [
                {
                    "requirement_id": "PAY_A",
                    "target_account_id": "CLEARING_A",
                    "currency": "USD",
                    "required_cash": 90_000_000,
                    "cutoff_hour": 15,
                },
                {
                    "requirement_id": "PAY_B",
                    "target_account_id": "SETTLEMENT_B",
                    "currency": "USD",
                    "required_cash": 65_000_000,
                    "cutoff_hour": 16,
                },
            ],
            "payment_rails": [
                {
                    "rail_id": "FEDWIRE",
                    "currency": "USD",
                    "fee_bps": 0.15,
                    "fixed_fee": 35,
                    "cutoff_hour": 17,
                    "max_transfer": 250_000_000,
                },
                {
                    "rail_id": "CHIPS",
                    "currency": "USD",
                    "fee_bps": 0.08,
                    "fixed_fee": 20,
                    "cutoff_hour": 16,
                    "max_transfer": 125_000_000,
                },
            ],
        },
    )
    return CashMovementProductionAdapter().run(request)


def _run_margin_workflow():
    request = OptimizationRequest(
        domain="margin_operations",
        portfolio_id="PORT_MARGIN_OPS",
        objective=Objective(
            name="minimize_sla_breach_risk",
            direction=ObjectiveDirection.MINIMIZE,
            metric="residual_risk",
        ),
        context={
            "data_snapshot_id": "SNAP_MARGIN_VIDEO",
            "team_capacity_minutes": 150,
            "materiality_threshold": 25_000_000,
            "margin_call_queue": [
                {
                    "call_id": "MC_A",
                    "counterparty": "Dealer A",
                    "amount": 40_000_000,
                    "due_in_hours": 2,
                    "dispute_probability": 0.20,
                    "ops_minutes": 80,
                    "risk_tier": "high",
                },
                {
                    "call_id": "MC_B",
                    "counterparty": "CCP B",
                    "amount": 70_000_000,
                    "due_in_hours": 1,
                    "dispute_probability": 0.05,
                    "ops_minutes": 70,
                    "risk_tier": "critical",
                },
                {
                    "call_id": "MC_C",
                    "counterparty": "Dealer C",
                    "amount": 15_000_000,
                    "due_in_hours": 8,
                    "dispute_probability": 0.60,
                    "ops_minutes": 90,
                    "risk_tier": "medium",
                },
            ],
        },
    )
    return MarginCallWorkflowProductionAdapter().run(request)


def _run_cash_movement_from_policy():
    path = REPO_ROOT / "examples" / "policies" / "sample_treasury_payment_policy.md"
    ingestion = ingest_policy_document(
        workflow_id="treasury_cash_movement",
        text=path.read_text(encoding="utf-8"),
        filename=path.name,
    )
    context = {
        **ingestion.context_patch["treasury_operations"],
        "policy_ingestion": ingestion.context_patch["policy_ingestion"],
        "data_snapshot_id": "SNAP_TREASURY_POLICY_VIDEO",
    }
    request = OptimizationRequest(
        domain="treasury_operations",
        portfolio_id=str(ingestion.context_patch["portfolio_id"]),
        objective=Objective(
            name="minimize_cash_movement_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="transfer_cost",
        ),
        context=context,
    )
    return ingestion, CashMovementProductionAdapter().run(request)


def _run_margin_workflow_from_policy():
    path = REPO_ROOT / "examples" / "policies" / "sample_margin_call_sla_procedure.md"
    ingestion = ingest_policy_document(
        workflow_id="margin_call_workflow",
        text=path.read_text(encoding="utf-8"),
        filename=path.name,
    )
    context = {
        **ingestion.context_patch["margin_operations"],
        "policy_ingestion": ingestion.context_patch["policy_ingestion"],
        "data_snapshot_id": "SNAP_MARGIN_POLICY_VIDEO",
    }
    request = OptimizationRequest(
        domain="margin_operations",
        portfolio_id=str(ingestion.context_patch["portfolio_id"]),
        objective=Objective(
            name="minimize_sla_breach_risk",
            direction=ObjectiveDirection.MINIMIZE,
            metric="residual_risk",
        ),
        context=context,
    )
    return ingestion, MarginCallWorkflowProductionAdapter().run(request)


def _build_scenes(cash_result, margin_result) -> list[Scene]:
    total_moved = cash_result.domain_attachments["total_moved_cash"]
    transfer_count = cash_result.domain_attachments["transfer_count"]
    cash_savings = cash_result.baseline_value - cash_result.objective_value
    assigned = margin_result.domain_attachments["assigned_calls"]
    deferred = margin_result.domain_attachments["deferred_calls"]
    assigned_amount = margin_result.domain_attachments["assigned_amount"]
    total_queue = margin_result.domain_attachments["total_queue_amount"]
    capacity_used = margin_result.domain_attachments["capacity_used"]
    return [
        Scene(
            0,
            1,
            "Operational Optimization Extends The Platform Beyond Portfolios",
            (
                "This storyboard combines two new production adapters: treasury "
                "cash movement and margin-call workflow prioritization."
            ),
            "Frame operational decisions as optimizer workflows",
            "New Production Adapters",
            [
                "production.treasury.cash_movement",
                "production.margin_call.workflow",
                "Same adapter lifecycle as portfolio models",
                "Preflight, solve, normalize, evidence",
            ],
            "Why It Matters",
            [
                "Treasury and operations teams get decision support",
                "Controls and evidence are built into the workflow",
                "Firm engines can replace the scaffold later",
                "The UI can surface operational recommendations",
            ],
            "Operations storyboard",
            COLORS["cyan"],
            title_card="Operational Optimizer Walkthrough",
        ),
        Scene(
            9,
            2,
            "Example #1: Treasury Cash Movement",
            "The user asks how to fund clearing and settlement needs before cutoffs.",
            "Collect cash balances, funding needs, rails, buffers, and cutoffs",
            "Business Request",
            [
                "Move cash for clearing and settlement",
                "Protect minimum buffers by source account",
                "Use open payment rails before cutoff",
                "Minimize transfer cost and late-funding risk",
            ],
            "Adapter Contract",
            [
                "validate_inputs(): check balances and rails",
                "build_problem(): normalize requirements",
                "solve(): route cash over feasible rails",
                "serialize_evidence(): retain snapshot and fingerprint",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
            chat=[
                ("User", "We need to fund clearing and settlement today."),
                ("Assistant", "I will route cash through open rails and preserve buffers."),
            ],
        ),
        Scene(
            22,
            3,
            "The Optimizer Routes Cash Through Feasible Rails",
            (
                "The scaffold uses deterministic least-cost routing today and "
                "can later be swapped for LP, MILP, payment-hub, or vendor logic."
            ),
            "Allocate funding from source accounts to target requirements",
            "Inputs",
            [
                "SRC_1 available: $150M / buffer: $20M",
                "SRC_2 available: $80M / buffer: $15M",
                "PAY_A requirement: $90M",
                "PAY_B requirement: $65M",
                "Rails: CHIPS and FEDWIRE",
            ],
            "Run Output",
            [
                f"Status: {cash_result.status}",
                f"Cash moved: {_money(total_moved)}",
                f"Transfers created: {transfer_count}",
                f"Estimated cost saved: {_money(cash_savings)}",
                f"Binding check: {cash_result.binding_constraints[0]}",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
            bars=[
                ("Funding satisfied", 1.0, COLORS["green"]),
                ("Source buffer retained", 0.86, COLORS["cyan"]),
                ("Rail cutoff coverage", 0.92, COLORS["blue"]),
                ("Cost efficiency", 0.74, COLORS["amber"]),
            ],
        ),
        Scene(
            36,
            4,
            "Cash Movement Ends With Reviewer-Ready Evidence",
            (
                "The output is not only a payment list; it carries lineage, "
                "model config, input snapshot, and normalized result sections."
            ),
            "Package transfer recommendations and reproducibility metadata",
            "Recommended Transfers",
            _transfer_rows(cash_result),
            "Evidence Captured",
            [
                "Model version and config version",
                "Data snapshot ID: SNAP_CASHMOVE_VIDEO",
                "Solver method: least_cost_cutoff_feasible",
                "Request, preflight, native solution, normalized result",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
        ),
        Scene(
            47,
            5,
            "Example #2: Margin Call Workflow",
            "The second workflow prioritizes an operations queue when capacity is scarce.",
            "Score margin calls by exposure, SLA urgency, dispute risk, and risk tier",
            "Queue Pressure",
            [
                "Three calls arrive in the work window",
                "One CCP call is due in one hour",
                "One dealer call is material and high risk",
                "Team capacity is limited to 150 minutes",
            ],
            "Optimization Goal",
            [
                "Minimize residual queue risk",
                "Use available team capacity first",
                "Escalate material and disputed calls",
                "Defer lower priority work with evidence",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            title_card="Example #2: Margin Call Workflow",
        ),
        Scene(
            58,
            6,
            "The Adapter Turns A Work Queue Into A Prioritized Plan",
            (
                "The workflow makes operational triage explicit and repeatable "
                "instead of relying on manual queue sorting."
            ),
            "Assign calls that fit capacity and reduce the most risk",
            "Priority Inputs",
            [
                "Amount vs. materiality threshold",
                "Hours until SLA breach",
                "Dispute probability",
                "Counterparty risk tier",
                "Expected ops minutes",
            ],
            "Run Output",
            [
                f"Status: {margin_result.status}",
                f"Assigned amount: {_money(assigned_amount)}",
                f"Queue amount: {_money(total_queue)}",
                f"Capacity used: {capacity_used:.0f} minutes",
                f"Deferred calls: {len(deferred)}",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            bars=[
                ("Queue materiality", 1.0, COLORS["green"]),
                ("SLA urgency", 0.88, COLORS["red"]),
                ("Capacity used", capacity_used / 150, COLORS["amber"]),
                ("Risk reduced", 0.78, COLORS["blue"]),
            ],
        ),
        Scene(
            72,
            7,
            "The Recommendation Explains What To Process First",
            (
                "A manager sees exactly which calls are assigned, which are "
                "deferred, and why the capacity constraint is binding."
            ),
            "Review assigned work, deferred queue, and recommended actions",
            "Assigned Calls",
            _assigned_rows(assigned),
            "Deferred / Binding Context",
            _deferred_rows(deferred)
            + [
                f"Binding check: {margin_result.binding_constraints[0]}",
                "Evidence supports escalation or deferral",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            chat=[
                ("Ops Lead", "Why did the CCP call come first?"),
                ("Assistant", "It is material, critical tier, and due inside one hour."),
            ],
        ),
        Scene(
            84,
            8,
            "The Pattern Is Pluggable For Production Operations",
            (
                "Both workflows share the same adapter surface and can later "
                "point to firm systems, services, or solver engines."
            ),
            "Show a reusable production integration pattern",
            "Common Contract",
            [
                "validate_inputs()",
                "build_problem()",
                "solve()",
                "explain_outputs()",
                "serialize_evidence()",
            ],
            "Production Implication",
            [
                "In-process Python today",
                "Subprocess, REST, gRPC, batch, or containers later",
                "Normalized result contract for UI and API",
                "Governance/versioning ready from day one",
            ],
            "Operational platform extension",
            COLORS["green"],
        ),
    ]


def _build_treasury_policy_scenes(ingestion, cash_result) -> list[Scene]:
    total_moved = cash_result.domain_attachments["total_moved_cash"]
    total_required = cash_result.domain_attachments["total_required_cash"]
    transfer_count = cash_result.domain_attachments["transfer_count"]
    cash_savings = cash_result.baseline_value - cash_result.objective_value
    return _with_total_stages([
        Scene(
            0,
            1,
            "Example #1: Operational Policy Ingestion To Treasury Cash Movement",
            (
                "A treasury payment policy is converted into structured controls, "
                "then used to route same-day cash before payment cutoffs."
            ),
            "Open the treasury payment policy and identify operational constraints",
            "Source Document",
            [
                "sample_treasury_payment_policy.md",
                "Portfolio: PORT_TREASURY_OPS_440",
                "Same-day USD settlement support",
                "Policy describes cutoffs, buffers, rails, and stress",
            ],
            "Demo Story",
            [
                "Ingest payment policy",
                "Extract cutoff and cash requirements",
                "Run production cash movement adapter",
                "Show routed transfers and evidence",
            ],
            "Treasury policy ingestion",
            COLORS["cyan"],
            title_card="Example #1: Treasury Cash Movement",
        ),
        Scene(
            11,
            2,
            "The Policy Becomes Structured Workflow Context",
            "Deterministic ingestion extracts only fields the treasury workflow supports.",
            "Review extracted fields before they become optimizer inputs",
            "Extracted Policy Fields",
            _field_rows(ingestion, "treasury_operations"),
            "Validator Output",
            [
                f"Backend: {ingestion.review_summary['backend']}",
                f"Applied fields: {ingestion.review_summary['applied_count']}",
                f"Ready to run: {ingestion.review_summary['ready']}",
                "Unsupported fields would be rejected before solve",
            ],
            "Treasury policy ingestion",
            COLORS["cyan"],
            chat=[
                ("User", "Ingest the payment policy and route cash for today's settlements."),
                (
                    "Assistant",
                    "I found cutoff, required cash, buffer, rail cap, and stress controls.",
                ),
            ],
        ),
        Scene(
            24,
            3,
            "Before Optimization: Cash Must Move Without Breaking Buffers",
            (
                "The policy asks the workflow to satisfy stressed settlement needs "
                "while preserving source-account operating buffers."
            ),
            "Translate policy controls into the production adapter request",
            "Policy Controls Applied",
            [
                "Treasury cutoff: 15:00",
                "Required cash: $210M",
                "Funding stress: 115%",
                "Source buffer: $30M",
                "Rail transfer cap: $150M",
            ],
            "Pre-Run Risk",
            [
                "Manual routing can miss rail cutoffs",
                "Source liquidity buffers can be breached",
                "Transfer caps can fragment payments",
                "Reviewer needs evidence for the policy source",
            ],
            "Treasury policy ingestion",
            COLORS["blue"],
            bars=[
                ("Required cash", 0.84, COLORS["amber"]),
                ("Stress uplift", 0.15, COLORS["red"]),
                ("Buffer protection", 0.72, COLORS["cyan"]),
                ("Rail capacity used", 0.68, COLORS["blue"]),
            ],
        ),
        Scene(
            38,
            4,
            "The Production Adapter Routes Same-Day Cash",
            (
                "The scaffold chooses least-cost open rails while respecting "
                "cutoff, buffer, currency, and transfer-cap controls."
            ),
            "Run production.treasury.cash_movement",
            "Optimization Result",
            [
                f"Status: {cash_result.status}",
                f"Cash moved: {_money(total_moved)}",
                f"Required cash after stress: {_money(total_required)}",
                f"Transfers created: {transfer_count}",
                f"Estimated cost saved: {_money(cash_savings)}",
            ],
            "Recommended Transfers",
            _transfer_rows(cash_result),
            "Treasury cash movement",
            COLORS["green"],
            bars=[
                ("Funding satisfied", min(1.0, total_moved / total_required), COLORS["green"]),
                ("Source buffer retained", 0.78, COLORS["cyan"]),
                ("Cutoff feasible", 0.92, COLORS["blue"]),
                ("Cost efficiency", 0.74, COLORS["amber"]),
            ],
        ),
        Scene(
            53,
            5,
            "After Optimization: The Route Is Explainable",
            (
                "The output gives operations teams a transfer list plus the "
                "business reason each recommendation is allowed."
            ),
            "Show route, rail, amount, and remaining liquidity",
            "Before",
            [
                "Policy in unstructured document form",
                "Manual transfer routing risk",
                "Unclear link from cutoff rule to action",
                "Evidence must be assembled separately",
            ],
            "After",
            [
                "Structured policy controls applied",
                f"{transfer_count} transfer recommendations",
                "Buffers and rails checked in preflight",
                "Evidence attached to production run",
            ],
            "Treasury cash movement",
            COLORS["cyan"],
        ),
        Scene(
            66,
            6,
            "Evidence Connects The Policy To The Recommendation",
            (
                "The run can be exported or persisted with model config, "
                "preflight, native output, normalized result, and policy metadata."
            ),
            "Package the operational recommendation for review",
            "Evidence Captured",
            [
                "Policy file: sample_treasury_payment_policy.md",
                "Data snapshot: SNAP_TREASURY_POLICY_VIDEO",
                "Model config and adapter ID",
                "Native solution and normalized result",
            ],
            "Reviewer Takeaway",
            [
                "Clear document-to-decision trace",
                "Deterministic optimizer backbone",
                "Controls visible before execution",
                "Ready for firm payment engine replacement",
            ],
            "Treasury evidence review",
            COLORS["green"],
        ),
    ], 6)


def _build_margin_policy_scenes(ingestion, margin_result) -> list[Scene]:
    assigned = margin_result.domain_attachments["assigned_calls"]
    deferred = margin_result.domain_attachments["deferred_calls"]
    assigned_amount = margin_result.domain_attachments["assigned_amount"]
    total_queue = margin_result.domain_attachments["total_queue_amount"]
    capacity_used = margin_result.domain_attachments["capacity_used"]
    capacity_remaining = margin_result.domain_attachments["capacity_remaining"]
    return _with_total_stages([
        Scene(
            0,
            1,
            "Example #2: Margin Call SLA Triage Under Stress",
            (
                "A margin-call SLA procedure is ingested, converted into queue "
                "controls, and used to prioritize work under capacity limits."
            ),
            "Open the SLA procedure and identify triage controls",
            "Source Document",
            [
                "sample_margin_call_sla_procedure.md",
                "Portfolio: PORT_MARGIN_OPS_550",
                "Stress queue review",
                "Procedure describes capacity, materiality, SLA, dispute stress",
            ],
            "Demo Story",
            [
                "Ingest SLA procedure",
                "Extract capacity and escalation rules",
                "Run production margin workflow adapter",
                "Show assigned, deferred, and evidence",
            ],
            "Margin SLA ingestion",
            COLORS["amber"],
            title_card="Example #2: Margin Call SLA Triage",
        ),
        Scene(
            12,
            2,
            "The SLA Procedure Becomes Structured Controls",
            (
                "The ingestion layer extracts only workflow-supported fields "
                "and keeps evidence snippets."
            ),
            "Review extracted fields before queue prioritization",
            "Extracted Procedure Fields",
            _field_rows(ingestion, "margin_operations"),
            "Validator Output",
            [
                f"Backend: {ingestion.review_summary['backend']}",
                f"Applied fields: {ingestion.review_summary['applied_count']}",
                f"Ready to run: {ingestion.review_summary['ready']}",
                "Unsupported or invalid fields would be rejected",
            ],
            "Margin SLA ingestion",
            COLORS["amber"],
            chat=[
                ("Ops Lead", "Triage the margin queue using the SLA procedure."),
                (
                    "Assistant",
                    "I found capacity, materiality, SLA, dispute stress, and governance flags.",
                ),
            ],
        ),
        Scene(
            25,
            3,
            "Before Optimization: Capacity Is The Constraint",
            (
                "The queue contains material and time-sensitive calls, but "
                "the team only has a limited operations window."
            ),
            "Translate SLA policy into queue triage inputs",
            "Policy Controls Applied",
            [
                "Team capacity: 165 minutes",
                "Materiality threshold: $25M",
                "SLA escalation: 2 hours",
                "Dispute stress: 125%",
                "Production constraint change: true",
            ],
            "Pre-Run Queue Pressure",
            [
                "Critical CCP call due inside one hour",
                "Dealer call is material and high risk",
                "One disputed dealer call may not fit capacity",
                "Deferrals require evidence",
            ],
            "Margin workflow",
            COLORS["red"],
            bars=[
                ("Queue amount", 1.0, COLORS["amber"]),
                ("Capacity available", 0.72, COLORS["cyan"]),
                ("SLA pressure", 0.88, COLORS["red"]),
                ("Dispute stress", 0.62, COLORS["blue"]),
            ],
        ),
        Scene(
            39,
            4,
            "The Production Adapter Prioritizes Calls",
            (
                "The scaffold scores calls by exposure, SLA urgency, dispute "
                "probability, and counterparty risk tier."
            ),
            "Run production.margin_call.workflow",
            "Optimization Result",
            [
                f"Status: {margin_result.status}",
                f"Assigned amount: {_money(assigned_amount)}",
                f"Total queue amount: {_money(total_queue)}",
                f"Capacity used: {capacity_used:.0f} minutes",
                f"Capacity remaining: {capacity_remaining:.0f} minutes",
            ],
            "Assigned Calls",
            _assigned_rows(assigned),
            "Margin workflow",
            COLORS["green"],
            bars=[
                ("Assigned amount", assigned_amount / total_queue, COLORS["green"]),
                ("Capacity used", capacity_used / 165, COLORS["amber"]),
                ("Risk reduced", 0.78, COLORS["blue"]),
                ("Deferred queue", 0.30 if deferred else 0.0, COLORS["red"]),
            ],
        ),
        Scene(
            54,
            5,
            "The Recommendation Explains Deferrals And Escalations",
            (
                "A manager can see which calls are processed now, which are "
                "deferred, and which require supervisor or dispute review."
            ),
            "Review assigned work, deferred queue, and recommended actions",
            "Deferred / Binding Context",
            _deferred_rows(deferred)
            + [
                f"Binding check: {margin_result.binding_constraints[0]}",
                "Deferrals are tied to capacity evidence",
            ],
            "Governance Context",
            [
                "Material calls require supervisor review",
                "SLA window is explicitly sourced",
                "Dispute stress is applied before solve",
                "Evidence supports escalation decisions",
            ],
            "Margin workflow",
            COLORS["amber"],
            chat=[
                ("Ops Lead", "Why was this queue order chosen?"),
                ("Assistant", "Materiality, SLA urgency, and risk tier drive the priority score."),
            ],
        ),
        Scene(
            68,
            6,
            "Operational Optimization Produces Control Evidence",
            (
                "The demo closes with a traceable procedure-to-action story "
                "instead of a black-box queue recommendation."
            ),
            "Package assigned/deferred calls and reproducibility metadata",
            "Evidence Captured",
            [
                "Policy file: sample_margin_call_sla_procedure.md",
                "Data snapshot: SNAP_MARGIN_POLICY_VIDEO",
                "Assigned calls and deferred calls",
                "Model config, preflight, native solution, normalized result",
            ],
            "Production Implication",
            [
                "Workflow queue service can replace scaffold",
                "Case management can consume recommended actions",
                "Controls remain visible in UI and API",
                "Governance evidence travels with the run",
            ],
            "Margin evidence review",
            COLORS["green"],
        ),
    ], 6)


def _draw_frame(scene: Scene, cash_result, margin_result, progress: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    fonts = _fonts()
    _background(draw, scene.accent, progress)
    _header(draw, fonts, scene)
    _workflow_metrics(draw, fonts, cash_result, margin_result)
    if scene.title_card:
        _title_card(draw, fonts, scene)
    _panel(draw, 36, 138, 584, 346, scene.left_title, scene.left_rows, fonts)
    right_rows = scene.right_rows[:3] if scene.bars else scene.right_rows
    _panel(draw, 660, 138, 584, 346, scene.right_title, right_rows, fonts)
    if scene.chat:
        _chat(draw, fonts, scene.chat, scene.accent)
    if scene.bars:
        _bars(draw, fonts, scene.bars)
    _caption(draw, fonts, scene, progress)
    _timeline(draw, fonts, scene.stage, scene.total_stages)
    return image


def _background(draw: ImageDraw.ImageDraw, accent: str, progress: float) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg"])
    draw.rectangle((0, 0, WIDTH, 82), fill="#071216")
    for x in range(-100, WIDTH + 140, 36):
        drift = int((progress * 120) % 36)
        draw.line((x + drift, 82, x + 210 + drift, HEIGHT), fill="#0A171B", width=1)
    draw.rounded_rectangle((36, 92, 1244, 98), radius=3, fill=accent)


def _header(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
) -> None:
    draw.rounded_rectangle((36, 22, 72, 58), radius=5, fill=scene.accent)
    draw.text((47, 32), "DI", fill=COLORS["bg"], font=fonts["small_bold"])
    draw.text((88, 20), "Decision Intelligence", fill=COLORS["ink"], font=fonts["label"])
    draw.text((88, 43), scene.workflow_label, fill=COLORS["muted"], font=fonts["small"])
    draw.rounded_rectangle(
        (946, 24, 1244, 56), radius=5, outline=COLORS["line"], fill=COLORS["panel"]
    )
    draw.text(
        (964, 33),
        "video_examples/operations",
        fill=scene.accent,
        font=fonts["small_bold"],
    )


def _workflow_metrics(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    cash,
    margin,
) -> None:
    metrics = [
        ("Cash moved", _money(cash.domain_attachments["total_moved_cash"])),
        ("Transfer count", str(cash.domain_attachments["transfer_count"])),
        ("Assigned margin", _money(margin.domain_attachments["assigned_amount"])),
        ("Capacity used", f"{margin.domain_attachments['capacity_used']:.0f} min"),
    ]
    x = 36
    for label, value in metrics:
        draw.rounded_rectangle(
            (x, 500, x + 286, 550), radius=8, fill=COLORS["panel"], outline=COLORS["line"]
        )
        draw.text((x + 16, 510), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.text((x + 16, 530), value, fill=COLORS["ink"], font=fonts["metric"])
        x += 306


def _title_card(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
) -> None:
    draw.rounded_rectangle(
        (372, 24, 908, 56), radius=8, fill="#071116", outline=scene.accent, width=2
    )
    text_w = draw.textlength(scene.title_card or "", font=fonts["small_bold"])
    draw.text(
        ((WIDTH - text_w) / 2, 34),
        scene.title_card or "",
        fill=scene.accent,
        font=fonts["small_bold"],
    )


def _panel(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    rows: list[str],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=8, fill=COLORS["panel"], outline=COLORS["line"]
    )
    draw.text((x + 18, y + 16), title, fill=COLORS["ink"], font=fonts["subhead"])
    yy = y + 58
    for row in rows[:7]:
        draw.rounded_rectangle((x + 18, yy, x + w - 18, yy + 34), radius=5, fill=COLORS["panel2"])
        _wrapped(draw, row, x + 32, yy + 8, w - 72, fonts["small"], COLORS["ink"], 1)
        yy += 42


def _caption(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
    progress: float,
) -> None:
    x, y, w, h = 36, 570, 1208, 126
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=8, fill="#071116", outline=scene.accent, width=2
    )
    draw.text(
        (x + 18, y + 10),
        f"STAGE {scene.stage} OF {scene.total_stages}",
        fill=scene.accent,
        font=fonts["small_bold"],
    )
    draw.text(
        (x + 960, y + 10),
        "PRODUCTION OPTIMIZER STORYBOARD",
        fill=scene.accent,
        font=fonts["small_bold"],
    )
    draw.text((x + 18, y + 32), scene.title, fill=COLORS["ink"], font=fonts["title"])
    _wrapped(draw, scene.caption, x + 18, y + 62, 1060, fonts["body"], COLORS["ink"], 1)
    draw.text(
        (x + 18, y + 92),
        f"Current action: {scene.action}",
        fill=COLORS["green"],
        font=fonts["small_bold"],
    )
    draw.rounded_rectangle((x + 18, y + 112, x + w - 18, y + 117), radius=3, fill=COLORS["panel3"])
    draw.rounded_rectangle(
        (x + 18, y + 112, x + 18 + int((w - 36) * progress), y + 117),
        radius=3,
        fill=scene.accent,
    )


def _chat(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    chat: list[tuple[str, str]],
    accent: str,
) -> None:
    x, y = 80, 332
    for speaker, text in chat:
        color = COLORS["cyan"] if speaker in {"User", "Ops Lead"} else COLORS["green"]
        draw.rounded_rectangle((x, y, x + 498, y + 58), radius=8, fill="#0B1B1F", outline=color)
        draw.text(
            (x + 14, y + 10),
            speaker,
            fill=accent if speaker == "Assistant" else color,
            font=fonts["small_bold"],
        )
        _wrapped(draw, text, x + 96, y + 10, 380, fonts["small"], COLORS["ink"], 2)
        y += 68


def _bars(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    bars: list[tuple[str, float, str]],
) -> None:
    x, y = 704, 306
    for label, value, color in bars[:4]:
        draw.text((x, y), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.rounded_rectangle((x, y + 22, x + 458, y + 38), radius=8, fill=COLORS["panel3"])
        draw.rounded_rectangle((x, y + 22, x + int(458 * value), y + 38), radius=8, fill=color)
        draw.text((x + 472, y + 18), _pct(value), fill=COLORS["ink"], font=fonts["small"])
        y += 48


def _timeline(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    active: int,
    total_stages: int,
) -> None:
    labels = [
        "Policy",
        "Extract",
        "Preflight",
        "Optimize",
        "Review",
        "Evidence",
        "Controls",
        "Pattern",
    ]
    labels = labels[:total_stages]
    x, y = 126, 104
    for index, label in enumerate(labels, start=1):
        color = COLORS["green"] if index <= active else COLORS["faint"]
        draw.ellipse((x, y, x + 18, y + 18), fill=color)
        text_w = draw.textlength(label, font=fonts["small"])
        draw.text((x + 9 - text_w / 2, y + 24), label, fill=COLORS["muted"], font=fonts["small"])
        if index < len(labels):
            draw.line((x + 22, y + 9, x + 120, y + 9), fill=color, width=3)
        x += 130


def _transfer_rows(result) -> list[str]:
    rows = []
    for allocation in result.allocations[:4]:
        metadata = allocation.get("metadata", allocation)
        rows.append(
            f"{metadata['requirement_id']}: {_money(metadata['amount'])} "
            f"via {metadata['rail_id']} from {metadata['from_account_id']}"
        )
    return rows


def _assigned_rows(calls: list[dict]) -> list[str]:
    return [
        (
            f"{row['assigned_order']}. {row['call_id']} {row['counterparty']}: "
            f"{_money(row['amount'])}, {row['recommended_action']}"
        )
        for row in calls
    ]


def _deferred_rows(calls: list[dict]) -> list[str]:
    if not calls:
        return ["No deferred calls"]
    return [
        (
            f"{row['call_id']} {row['counterparty']}: {_money(row['amount'])}, "
            f"{row['recommended_action']}"
        )
        for row in calls
    ]


def _with_total_stages(scenes: list[Scene], total_stages: int) -> list[Scene]:
    return [replace(scene, total_stages=total_stages) for scene in scenes]


def _field_rows(ingestion, prefix: str) -> list[str]:
    rows = []
    for field in ingestion.extracted_fields:
        if field.applied and field.key.startswith(prefix):
            label = field.label.replace("Treasury ", "").replace("Margin ", "")
            rows.append(f"{label}: {_display_value(field.value)}")
    return rows[:6] or ["No supported fields extracted"]


def _display_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value >= 1_000_000:
            return _money(value)
        if 0 <= value <= 2:
            return f"{value:.2f}x" if value > 1 else _pct(value)
        return f"{value:g}"
    return str(value)


def _wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    fill: str,
    max_lines: int,
) -> None:
    chars = max(24, width // 8)
    for idx, line in enumerate(wrap(text, chars)[:max_lines]):
        draw.text((x, y + idx * 18), line, fill=fill, font=font)


def _scene_at(scenes: list[Scene], second: float) -> Scene:
    current = scenes[0]
    for scene in scenes:
        if second >= scene.start:
            current = scene
    return current


def _fonts() -> dict[str, ImageFont.ImageFont]:
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    regular = next((path for path in font_paths if Path(path).exists()), "")
    bold = next((path for path in bold_paths if Path(path).exists()), regular)

    def load(path: str, size: int) -> ImageFont.ImageFont:
        if path:
            return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()

    return {
        "title": load(bold, 25),
        "subhead": load(bold, 18),
        "metric": load(bold, 22),
        "body": load(regular, 16),
        "label": load(bold, 13),
        "small": load(regular, 14),
        "small_bold": load(bold, 13),
    }


def _encode_mp4(frames_dir: Path, output: Path) -> None:
    ffmpeg = _ffmpeg()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames_dir / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(output.relative_to(REPO_ROOT))


def _ffmpeg() -> str:
    candidates = [
        REPO_ROOT
        / "frontend"
        / "app"
        / "node_modules"
        / "@ffmpeg-installer"
        / "darwin-arm64"
        / "ffmpeg",
        REPO_ROOT
        / "frontend"
        / "app"
        / "node_modules"
        / "@ffmpeg-installer"
        / "darwin-x64"
        / "ffmpeg",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not found. Run npm install in frontend/app.")


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


if __name__ == "__main__":
    main()
