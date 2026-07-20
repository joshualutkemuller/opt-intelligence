"""Persistent local evidence store for production optimizer runs."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from decision_intelligence.contracts import OptimizationRequest

from .contracts import NormalizedOptimizerResult, ProductionOptimizerEvidence


@dataclass(frozen=True)
class EvidenceManifest:
    """File manifest returned after local evidence persistence."""

    run_id: str
    root: str
    files: dict[str, str]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "root": self.root,
            "files": self.files,
            "created_at": self.created_at,
        }


class LocalProductionEvidenceStore:
    """Write production optimizer evidence into a durable local run directory."""

    def __init__(self, root: str | Path = "artifacts/evidence") -> None:
        self.root = Path(root)

    def persist(
        self,
        *,
        request: OptimizationRequest,
        normalized_result: NormalizedOptimizerResult,
    ) -> EvidenceManifest:
        evidence = normalized_result.evidence
        if evidence is None:
            raise ValueError(
                "Cannot persist production evidence because result.evidence is missing."
            )

        run_id = _run_id(request, evidence)
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        evidence_payload = evidence.model_dump(mode="json")
        result_payload = normalized_result.model_dump(mode="json")
        summary_rows = _summary_rows(request, normalized_result, evidence)
        allocation_rows = _allocation_rows(normalized_result)

        files = {
            "evidence_json": "evidence.json",
            "normalized_result_json": "normalized_result.json",
            "summary_csv": "summary.csv",
            "allocations_csv": "allocations.csv",
            "summary_xlsx": "summary.xlsx",
        }
        _write_json(run_dir / files["evidence_json"], evidence_payload)
        _write_json(run_dir / files["normalized_result_json"], result_payload)
        _write_csv(run_dir / files["summary_csv"], summary_rows)
        _write_csv(run_dir / files["allocations_csv"], allocation_rows)
        _write_xlsx(
            run_dir / files["summary_xlsx"],
            {
                "summary": summary_rows,
                "allocations": allocation_rows,
            },
        )

        manifest = EvidenceManifest(
            run_id=run_id,
            root=str(run_dir),
            files=files,
            created_at=datetime.now(UTC).isoformat(),
        )
        _write_json(run_dir / "manifest.json", manifest.as_dict())
        return manifest


def _run_id(request: OptimizationRequest, evidence: ProductionOptimizerEvidence) -> str:
    fingerprint = evidence.reproducibility_fingerprint or request.request_id
    return _slug(f"{request.request_id}-{evidence.optimizer_id}-{fingerprint[:12]}")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned[:160] or "production-run"


def _summary_rows(
    request: OptimizationRequest,
    result: NormalizedOptimizerResult,
    evidence: ProductionOptimizerEvidence,
) -> list[dict[str, Any]]:
    return [
        {"field": "request_id", "value": request.request_id},
        {"field": "portfolio_id", "value": request.portfolio_id},
        {"field": "domain", "value": request.domain},
        {"field": "optimizer_id", "value": evidence.optimizer_id},
        {"field": "model_version", "value": evidence.model_version},
        {"field": "config_version", "value": evidence.config_version},
        {"field": "data_snapshot_id", "value": evidence.data_snapshot_id},
        {"field": "solver_version", "value": evidence.solver_version},
        {"field": "fingerprint", "value": evidence.reproducibility_fingerprint},
        {"field": "status", "value": result.status},
        {"field": "objective_value", "value": result.objective_value},
        {"field": "baseline_value", "value": result.baseline_value},
        {"field": "allocation_count", "value": len(result.allocations)},
    ]


def _allocation_rows(result: NormalizedOptimizerResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, allocation in enumerate(result.allocations, start=1):
        row = {"row": index}
        row.update(_flatten(allocation))
        rows.append(row)
    return rows


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            row.update(_flatten(item, name))
        elif isinstance(item, list | tuple):
            row[name] = json.dumps(item, sort_keys=True)
        else:
            row[name] = item
    return row


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row}) or ["empty"]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _write_xlsx(path: Path, sheets: dict[str, list[dict[str, Any]]]) -> None:
    with ZipFile(path, "w", ZIP_DEFLATED) as workbook:
        sheet_names = list(sheets)
        _write_workbook_static_files(workbook, sheet_names)
        for index, rows in enumerate(sheets.values(), start=1):
            workbook.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet_xml(rows),
            )


def _write_workbook_static_files(workbook: ZipFile, sheet_names: list[str]) -> None:
    workbook.writestr(
        "[Content_Types].xml",
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="'
            'application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        )
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index, _ in enumerate(sheet_names, start=1)
        )
        + "</Types>",
    )
    workbook.writestr(
        "_rels/.rels",
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="'
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
    )
    workbook.writestr(
        "xl/workbook.xml",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>"""
        + "".join(
            f'<sheet name="{_xml_escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(sheet_names, start=1)
        )
        + "</sheets></workbook>",
    )
    workbook.writestr(
        "xl/_rels/workbook.xml.rels",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"""
        + "".join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index, _ in enumerate(sheet_names, start=1)
        )
        + "</Relationships>",
    )


def _worksheet_xml(rows: list[dict[str, Any]]) -> str:
    headers = sorted({key for row in rows for key in row}) or ["empty"]
    matrix = [headers] + [[row.get(header, "") for header in headers] for row in rows]
    body = []
    for row_index, values in enumerate(matrix, start=1):
        cells = []
        for column_index, value in enumerate(values, start=1):
            ref = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(str(value))}</t></is></c>'
            )
        body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(body)}</sheetData></worksheet>'
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
