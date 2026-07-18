"""Load named demo data packets used by the browser and video POC."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

DEFAULT_DATA_PACKET_DIR = Path(__file__).resolve().parents[3] / "config" / "data_packets"


class DemoDataPacket(BaseModel):
    packet_id: str
    version: int = Field(ge=1)
    name: str
    description: str
    audience: str
    workflow_id: str
    preset_id: str
    source_type: str
    domains: list[str]
    files: dict[str, str]
    talking_points: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)

    def catalog_item(self) -> dict[str, Any]:
        return self.model_dump()


def load_demo_data_packet(path: str | Path) -> DemoDataPacket:
    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read demo data packet '{file_path}'.") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in demo data packet '{file_path}'.") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Demo data packet '{file_path}' must contain a mapping.")

    try:
        return DemoDataPacket.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid demo data packet '{file_path}': {exc}") from exc


def load_demo_data_packets(directory: str | Path = DEFAULT_DATA_PACKET_DIR) -> list[DemoDataPacket]:
    root = Path(directory)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError(f"Demo data packet path '{root}' is not a directory.")

    packets = [
        load_demo_data_packet(path)
        for path in sorted([*root.glob("*.yaml"), *root.glob("*.yml")])
    ]
    packet_ids = [packet.packet_id for packet in packets]
    if len(packet_ids) != len(set(packet_ids)):
        raise ValueError("Demo data packet packet_id values must be unique.")
    return packets
