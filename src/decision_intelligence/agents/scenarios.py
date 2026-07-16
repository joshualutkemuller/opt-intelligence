"""Scenario suggestion agent."""

from __future__ import annotations

from .types import ScenarioSuggestion


class ScenarioAgent:
    """Suggest relevant deterministic scenarios for a domain and prompt."""

    def suggest(
        self,
        *,
        domain: str | None,
        text: str = "",
        selected: list[str] | None = None,
    ) -> list[ScenarioSuggestion]:
        selected_set = set(selected or [])
        normalized = text.lower()
        suggestions = _base_suggestions(domain)
        if "credit" in normalized:
            selected_set.add("credit_stress")
        if "stress" in normalized or "liquidity" in normalized:
            selected_set.add("stress")
        if "downside" in normalized:
            selected_set.add("downside")
        if "inventory" in normalized or "squeeze" in normalized:
            selected_set.add("inventory")
        return [
            item.model_copy(update={"selected": item.name in selected_set})
            for item in suggestions
        ]


def _base_suggestions(domain: str | None) -> list[ScenarioSuggestion]:
    if domain == "money_market":
        return [
            ScenarioSuggestion(
                name="stress",
                reason="Tests higher daily and weekly liquidity requirements.",
            ),
            ScenarioSuggestion(
                name="credit_stress",
                reason="Tests higher liquidity needs and lower fund yields.",
            ),
            ScenarioSuggestion(
                name="downside",
                reason="Tests a broad lower-yield environment.",
            ),
        ]
    if domain == "financing":
        return [
            ScenarioSuggestion(
                name="stress",
                reason="Tests wider spreads and reduced counterparty capacity.",
            ),
            ScenarioSuggestion(
                name="downside",
                reason="Tests moderate spread pressure and capacity reduction.",
            ),
        ]
    if domain == "collateral":
        return [
            ScenarioSuggestion(
                name="stress",
                reason="Tests increased obligations under collateral pressure.",
            ),
            ScenarioSuggestion(
                name="inventory",
                reason="Tests reduced collateral inventory availability.",
            ),
        ]
    return []
