"""Portfolio drift monitoring — proactive alerting when holdings cross thresholds.

Usage::

    monitor = DriftMonitor()
    monitor.snapshot(workflow_result)          # record baseline after a run
    alerts = monitor.check(new_result)         # compare a later result against it
    for alert in alerts:
        print(alert.message, alert.severity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


@dataclass(frozen=True)
class DriftThreshold:
    """A single threshold rule applied to a named metric extracted from results."""

    name: str
    metric_key: str
    # Fraction of the cap/limit at which to fire (e.g. 0.9 = 90 % of cap).
    warn_fraction: float = 0.9
    # Absolute change in the metric that triggers a widening alert.
    delta_threshold: float | None = None
    domain: str | None = None  # None → applies to all domains
    description: str = ""


@dataclass(frozen=True)
class DriftAlert:
    threshold_name: str
    domain: str
    metric_key: str
    current_value: float
    baseline_value: float | None
    cap_value: float | None
    severity: Literal["warning", "critical"]
    message: str
    # Suggested domain to re-optimize (mirrors the originating step domain).
    reoptimize_domain: str
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "threshold_name": self.threshold_name,
            "domain": self.domain,
            "metric_key": self.metric_key,
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
            "cap_value": self.cap_value,
            "severity": self.severity,
            "message": self.message,
            "reoptimize_domain": self.reoptimize_domain,
            "detected_at": self.detected_at,
        }


_DEFAULT_THRESHOLDS: list[DriftThreshold] = [
    DriftThreshold(
        name="concentration_cap_proximity",
        metric_key="max_concentration_fraction",
        warn_fraction=0.9,
        description="Single-asset or single-fund allocation approaches its concentration cap.",
    ),
    DriftThreshold(
        name="objective_yield_gap",
        metric_key="objective_value",
        delta_threshold=-0.05,
        domain="money_market",
        description="Money-market yield drops more than 5 bps below baseline.",
    ),
    DriftThreshold(
        name="funding_coverage_shortfall",
        metric_key="objective_value",
        delta_threshold=-0.1,
        domain="financing",
        description="Financing coverage deteriorates by more than 10 % vs baseline.",
    ),
    DriftThreshold(
        name="collateral_cost_spike",
        metric_key="objective_value",
        delta_threshold=0.1,
        domain="collateral",
        description="Collateral funding cost increases more than 10 % vs baseline.",
    ),
    DriftThreshold(
        name="mvo_return_gap",
        metric_key="objective_value",
        delta_threshold=-0.05,
        domain="asset_allocation",
        description="MVO portfolio utility drops more than 5 % below baseline.",
    ),
]


class DriftMonitor:
    """Compare workflow results against a stored baseline and emit drift alerts.

    Parameters
    ----------
    thresholds:
        Override the default threshold set.  Pass an empty list to disable all
        built-in rules.
    """

    def __init__(
        self,
        thresholds: list[DriftThreshold] | None = None,
    ) -> None:
        self._thresholds = thresholds if thresholds is not None else list(_DEFAULT_THRESHOLDS)
        self._snapshots: dict[str, dict[str, Any]] = {}  # domain → metric dict
        self._snapshot_time: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self, workflow_result: dict[str, Any]) -> None:
        """Record the current result as the baseline for future drift checks."""
        self._snapshots = self._extract_metrics(workflow_result)
        self._snapshot_time = datetime.now(UTC).isoformat()

    def check(self, workflow_result: dict[str, Any]) -> list[DriftAlert]:
        """Compare *workflow_result* against the stored baseline.

        Returns an empty list when no baseline has been recorded or no thresholds
        are breached.
        """
        if not self._snapshots:
            return []
        current_metrics = self._extract_metrics(workflow_result)
        alerts: list[DriftAlert] = []
        for threshold in self._thresholds:
            for domain, metrics in current_metrics.items():
                if threshold.domain and threshold.domain != domain:
                    continue
                alert = self._evaluate(threshold, domain, metrics)
                if alert:
                    alerts.append(alert)
        return alerts

    def has_baseline(self) -> bool:
        return bool(self._snapshots)

    def baseline_time(self) -> str | None:
        return self._snapshot_time

    def configure_threshold(self, threshold: DriftThreshold) -> None:
        """Add or replace a threshold by name."""
        self._thresholds = [t for t in self._thresholds if t.name != threshold.name]
        self._thresholds.append(threshold)

    def remove_threshold(self, name: str) -> None:
        self._thresholds = [t for t in self._thresholds if t.name != name]

    def list_thresholds(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "metric_key": t.metric_key,
                "warn_fraction": t.warn_fraction,
                "delta_threshold": t.delta_threshold,
                "domain": t.domain,
                "description": t.description,
            }
            for t in self._thresholds
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        threshold: DriftThreshold,
        domain: str,
        metrics: dict[str, Any],
    ) -> DriftAlert | None:
        current = metrics.get(threshold.metric_key)
        if current is None:
            return None

        baseline_metrics = self._snapshots.get(domain, {})
        baseline = baseline_metrics.get(threshold.metric_key)

        # Cap proximity check (warn_fraction against a cap value in the metrics).
        cap_key = f"{threshold.metric_key}_cap"
        cap = metrics.get(cap_key)
        if cap is not None and cap > 0:
            fraction = current / cap
            if fraction >= threshold.warn_fraction:
                severity: Literal["warning", "critical"] = (
                    "critical" if fraction >= 0.98 else "warning"
                )
                pct = fraction * 100
                return DriftAlert(
                    threshold_name=threshold.name,
                    domain=domain,
                    metric_key=threshold.metric_key,
                    current_value=current,
                    baseline_value=baseline,
                    cap_value=cap,
                    severity=severity,
                    message=(
                        f"{domain}: {threshold.metric_key} is at {pct:.1f}% of cap "
                        f"({current:.4f} / {cap:.4f}). {threshold.description}"
                    ),
                    reoptimize_domain=domain,
                )

        # Delta check against baseline.
        if threshold.delta_threshold is not None and baseline is not None:
            delta = current - baseline
            # Positive delta_threshold → alert when value rises above it.
            # Negative delta_threshold → alert when value falls below it.
            breached = (
                (threshold.delta_threshold > 0 and delta >= threshold.delta_threshold)
                or (threshold.delta_threshold < 0 and delta <= threshold.delta_threshold)
            )
            if breached:
                direction = "increased" if delta > 0 else "decreased"
                return DriftAlert(
                    threshold_name=threshold.name,
                    domain=domain,
                    metric_key=threshold.metric_key,
                    current_value=current,
                    baseline_value=baseline,
                    cap_value=None,
                    severity="warning",
                    message=(
                        f"{domain}: {threshold.metric_key} has {direction} by "
                        f"{abs(delta):.4f} vs baseline ({baseline:.4f} → {current:.4f}). "
                        f"{threshold.description}"
                    ),
                    reoptimize_domain=domain,
                )

        return None

    def _extract_metrics(self, workflow_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Pull per-domain metric dicts out of a workflow result dict."""
        result = _record(workflow_result.get("result") or workflow_result)
        steps = [_record(s) for s in _list(result.get("step_results"))]
        domain_metrics: dict[str, dict[str, Any]] = {}
        for step in steps:
            domain = str(step.get("domain") or "unknown")
            step_result = _record(step.get("result"))
            metrics = self._metrics_from_result(step_result, domain)
            if metrics:
                domain_metrics[domain] = metrics
        # Also handle a flat single-step result (non-workflow call).
        if not domain_metrics:
            domain = str(result.get("domain") or "unknown")
            metrics = self._metrics_from_result(result, domain)
            if metrics:
                domain_metrics[domain] = metrics
        return domain_metrics

    @staticmethod
    def _metrics_from_result(result: dict[str, Any], domain: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        obj = result.get("objective_value")
        if obj is not None:
            metrics["objective_value"] = float(obj)

        # Concentration: the highest single-asset fraction in allocations.
        allocations = _list(result.get("allocations"))
        if allocations:
            fractions = [
                float(_record(a).get("allocated_fraction", 0)) for a in allocations
            ]
            if fractions:
                metrics["max_concentration_fraction"] = max(fractions)

        # Domain-specific caps surfaced in solver_metadata or context.
        solver_meta = _record(result.get("solver_metadata"))
        request_context = _record(
            _record(result.get("request", {})).get("context", {})
        )
        for source in (solver_meta, request_context):
            for cap_key in (
                "max_single_fund",
                "max_single_asset",
                "single_asset_cap",
                "max_prime_fraction",
            ):
                val = source.get(cap_key)
                if val is not None:
                    metrics["max_concentration_fraction_cap"] = float(val)
                    break

        return metrics


def _record(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []
