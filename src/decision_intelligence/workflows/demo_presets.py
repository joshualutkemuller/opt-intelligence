"""Load repeatable stakeholder demo presets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class DemoPresetConfig(BaseModel):
    preset_id: str
    version: int = Field(ge=1)
    name: str
    description: str
    audience: str
    workflow_id: str
    portfolio_id: str = "PORT_001"
    seed: int = 42
    duration_minutes: int = Field(default=5, ge=1)
    context: dict[str, Any] = Field(default_factory=dict)
    talking_points: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)

    @field_validator("talking_points", "success_criteria")
    @classmethod
    def _non_empty_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("must contain at least one item")
        return value

    def catalog_item(self) -> dict[str, Any]:
        return self.model_dump()


def load_demo_preset(path: str | Path) -> DemoPresetConfig:
    """Load and validate one YAML demo preset config."""

    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read demo preset '{file_path}'.") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in demo preset '{file_path}'.") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Demo preset '{file_path}' must contain a mapping.")

    try:
        return DemoPresetConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid demo preset '{file_path}': {exc}") from exc


def load_demo_presets(
    directory: str | Path,
    *,
    known_workflow_ids: set[str] | None = None,
) -> list[DemoPresetConfig]:
    """Load all YAML demo presets from a directory."""

    root = Path(directory)
    if not root.exists():
        raise ValueError(f"Demo preset directory '{root}' does not exist.")
    if not root.is_dir():
        raise ValueError(f"Demo preset path '{root}' is not a directory.")

    presets = [
        load_demo_preset(path)
        for path in sorted([*root.glob("*.yaml"), *root.glob("*.yml")])
    ]
    preset_ids = [preset.preset_id for preset in presets]
    if len(preset_ids) != len(set(preset_ids)):
        raise ValueError("Demo preset preset_id values must be unique.")

    if known_workflow_ids is not None:
        unknown = sorted(
            {
                preset.workflow_id
                for preset in presets
                if preset.workflow_id not in known_workflow_ids
            }
        )
        if unknown:
            raise ValueError(
                "Demo presets reference unknown workflow_id values: "
                f"{unknown}"
            )

    return presets
