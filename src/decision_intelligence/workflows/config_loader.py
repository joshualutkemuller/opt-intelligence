"""Load workflow template configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from .types import DependencyRuleType

InputType = Literal["string", "integer", "number", "currency", "fraction", "percent"]
ObjectiveDirectionName = Literal["minimize", "maximize"]


class WorkflowInputConfig(BaseModel):
    key: str
    label: str
    type: InputType
    default: Any = None
    required: bool = True


class WorkflowDependencyRuleConfig(BaseModel):
    source_step_id: str
    rule_type: DependencyRuleType
    target_context_keys: list[str]
    description: str = ""

    @field_validator("target_context_keys")
    @classmethod
    def _target_context_keys_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("target_context_keys must contain at least one key")
        return value


class WorkflowStepConfig(BaseModel):
    step_id: str
    domain: str
    name: str
    objective_metric: str
    objective_direction: ObjectiveDirectionName
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    dependency_rules: list[WorkflowDependencyRuleConfig] = Field(default_factory=list)


class WorkflowTemplateConfig(BaseModel):
    workflow_id: str
    version: int = Field(ge=1)
    name: str
    description: str
    domains: list[str]
    tags: list[str] = Field(default_factory=list)
    default_context: dict[str, Any] = Field(default_factory=dict)
    inputs: list[WorkflowInputConfig] = Field(default_factory=list)
    steps: list[WorkflowStepConfig]

    @field_validator("domains", "steps")
    @classmethod
    def _non_empty(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("must contain at least one item")
        return value

    @field_validator("steps")
    @classmethod
    def _unique_step_ids(cls, value: list[WorkflowStepConfig]) -> list[WorkflowStepConfig]:
        step_ids = [step.step_id for step in value]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")
        known = set(step_ids)
        for step in value:
            missing = [dep for dep in step.depends_on if dep not in known]
            if missing:
                raise ValueError(
                    f"step '{step.step_id}' depends on unknown step ids: {missing}"
                )
            for rule in step.dependency_rules:
                if rule.source_step_id not in known:
                    raise ValueError(
                        f"step '{step.step_id}' dependency rule references unknown "
                        f"source step '{rule.source_step_id}'"
                    )
        return value


def load_workflow_config(path: str | Path) -> WorkflowTemplateConfig:
    """Load and validate one YAML workflow template config."""

    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read workflow config '{file_path}'.") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in workflow config '{file_path}'.") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Workflow config '{file_path}' must contain a mapping.")

    try:
        return WorkflowTemplateConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid workflow config '{file_path}': {exc}") from exc


def load_workflow_configs(directory: str | Path) -> list[WorkflowTemplateConfig]:
    """Load all YAML workflow configs from a directory."""

    root = Path(directory)
    if not root.exists():
        raise ValueError(f"Workflow config directory '{root}' does not exist.")
    if not root.is_dir():
        raise ValueError(f"Workflow config path '{root}' is not a directory.")

    configs = [
        load_workflow_config(path)
        for path in sorted([*root.glob("*.yaml"), *root.glob("*.yml")])
    ]
    workflow_ids = [config.workflow_id for config in configs]
    if len(workflow_ids) != len(set(workflow_ids)):
        raise ValueError("Workflow config workflow_id values must be unique.")
    return configs
