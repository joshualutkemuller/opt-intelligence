"""Registry for discoverable workflow templates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_loader import WorkflowTemplateConfig, load_workflow_configs
from .library import (
    COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
    FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
    LIQUIDITY_STRESS_WORKFLOW_ID,
    build_collateral_liquidity_review_workflow,
    build_funding_capacity_shock_workflow,
    build_liquidity_stress_funding_workflow,
)
from .types import WorkflowPlan

WorkflowBuilder = Callable[..., WorkflowPlan]
DEFAULT_WORKFLOW_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "workflows"


@dataclass(frozen=True)
class WorkflowTemplate:
    """Metadata plus builder for a workflow plan template."""

    workflow_id: str
    name: str
    description: str
    domains: tuple[str, ...]
    builder: WorkflowBuilder
    tags: tuple[str, ...] = ()
    default_context: dict[str, Any] = field(default_factory=dict)

    def build(
        self,
        *,
        portfolio_id: str = "PORT_001",
        seed: int = 42,
        context: dict[str, Any] | None = None,
    ) -> WorkflowPlan:
        merged_context = {**self.default_context, **(context or {})}
        return self.builder(
            portfolio_id=portfolio_id,
            seed=seed,
            context=merged_context,
        )

    def catalog_item(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "domains": list(self.domains),
            "tags": list(self.tags),
            "default_context": self.default_context,
        }


class WorkflowRegistry:
    """In-memory registry for deterministic workflow templates."""

    def __init__(self) -> None:
        self._templates: dict[str, WorkflowTemplate] = {}

    def register(self, template: WorkflowTemplate) -> None:
        if template.workflow_id in self._templates:
            raise ValueError(f"Workflow '{template.workflow_id}' is already registered.")
        self._templates[template.workflow_id] = template

    def get(self, workflow_id: str) -> WorkflowTemplate:
        try:
            return self._templates[workflow_id]
        except KeyError as exc:
            available = ", ".join(self.list_ids()) or "none"
            raise KeyError(
                f"Unknown workflow '{workflow_id}'. Available workflows: {available}"
            ) from exc

    def build(
        self,
        workflow_id: str,
        *,
        portfolio_id: str = "PORT_001",
        seed: int = 42,
        context: dict[str, Any] | None = None,
    ) -> WorkflowPlan:
        return self.get(workflow_id).build(
            portfolio_id=portfolio_id,
            seed=seed,
            context=context,
        )

    def list_ids(self) -> list[str]:
        return sorted(self._templates)

    def list_catalog(self) -> list[dict[str, Any]]:
        return [
            self._templates[workflow_id].catalog_item()
            for workflow_id in self.list_ids()
        ]


def build_default_workflow_registry() -> WorkflowRegistry:
    registry = WorkflowRegistry()
    builder_map = _default_builder_map()
    for config in load_workflow_configs(DEFAULT_WORKFLOW_CONFIG_DIR):
        registry.register(_template_from_config(config, builder_map))
    return registry


def _default_builder_map() -> dict[str, WorkflowBuilder]:
    return {
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID: build_collateral_liquidity_review_workflow,
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID: build_funding_capacity_shock_workflow,
        LIQUIDITY_STRESS_WORKFLOW_ID: build_liquidity_stress_funding_workflow,
    }


def _template_from_config(
    config: WorkflowTemplateConfig,
    builder_map: dict[str, WorkflowBuilder],
) -> WorkflowTemplate:
    try:
        builder = builder_map[config.workflow_id]
    except KeyError as exc:
        raise ValueError(
            f"No workflow builder registered for config workflow_id '{config.workflow_id}'."
        ) from exc

    return WorkflowTemplate(
        workflow_id=config.workflow_id,
        name=config.name,
        description=config.description,
        domains=tuple(config.domains),
        tags=tuple(config.tags),
        default_context=dict(config.default_context),
        builder=builder,
    )


DEFAULT_WORKFLOW_REGISTRY = build_default_workflow_registry()
