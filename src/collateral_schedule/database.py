"""SQLite-backed store for counterparty collateral schedules."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator

_DEFAULT_DB_PATH = Path.home() / ".decision_intelligence" / "collateral.db"

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS counterparties (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    lei         TEXT,
    jurisdiction TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS margin_agreements (
    id               TEXT PRIMARY KEY,
    counterparty_id  TEXT NOT NULL REFERENCES counterparties(id),
    margin_type      TEXT NOT NULL,
    agreement_ref    TEXT,
    base_currency    TEXT NOT NULL DEFAULT 'USD',
    threshold_amount REAL NOT NULL DEFAULT 0.0,
    mta_amount       REAL NOT NULL DEFAULT 0.0,
    rounding_amount  REAL NOT NULL DEFAULT 0.0,
    governing_law    TEXT,
    effective_date   TEXT,
    created_at       TEXT NOT NULL,
    schedule_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS collateral_entries (
    id                     TEXT PRIMARY KEY,
    agreement_id           TEXT NOT NULL REFERENCES margin_agreements(id),
    asset_class            TEXT NOT NULL,
    isin                   TEXT,
    currency               TEXT,
    rating_floor           TEXT,
    max_maturity_years     REAL,
    haircut_pct            REAL NOT NULL DEFAULT 0.0,
    concentration_limit_pct REAL,
    eligible               INTEGER NOT NULL DEFAULT 1,
    notes                  TEXT,
    source_row             INTEGER,
    created_at             TEXT NOT NULL,
    schedule_version       INTEGER NOT NULL DEFAULT 1,
    superseded_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_agreement ON collateral_entries(agreement_id);
CREATE INDEX IF NOT EXISTS idx_agreements_counterparty ON margin_agreements(counterparty_id);
CREATE INDEX IF NOT EXISTS idx_entries_live ON collateral_entries(agreement_id, superseded_at);
"""

# Applied once to databases created before schedule versioning was added.
_MIGRATIONS = [
    "ALTER TABLE margin_agreements ADD COLUMN schedule_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE collateral_entries ADD COLUMN schedule_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE collateral_entries ADD COLUMN superseded_at TEXT",
    "CREATE INDEX IF NOT EXISTS idx_entries_live ON collateral_entries(agreement_id, superseded_at)",
]


class CollateralDatabase:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DEFAULT_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._tx() as conn:
            conn.executescript(_DDL)
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # column/index already exists on databases created post-migration

    # ── Counterparties ────────────────────────────────────────────────────────

    def create_counterparty(
        self,
        name: str,
        lei: str | None = None,
        jurisdiction: str | None = None,
        counterparty_id: str | None = None,
    ) -> dict[str, Any]:
        row_id = counterparty_id or f"cp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO counterparties (id, name, lei, jurisdiction, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row_id, name, lei, jurisdiction, now),
            )
        return {"id": row_id, "name": name, "lei": lei, "jurisdiction": jurisdiction, "created_at": now}

    def get_counterparty(self, counterparty_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM counterparties WHERE id = ?", (counterparty_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_counterparties(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM counterparties ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_counterparty(
        self,
        name: str,
        lei: str | None = None,
        jurisdiction: str | None = None,
        counterparty_id: str | None = None,
    ) -> dict[str, Any]:
        # Match by LEI if provided, else by name
        if lei:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM counterparties WHERE lei = ?", (lei,)
                ).fetchone()
            if row:
                return dict(row)
        return self.create_counterparty(name, lei, jurisdiction, counterparty_id)

    # ── Margin agreements ─────────────────────────────────────────────────────

    def create_agreement(
        self,
        counterparty_id: str,
        margin_type: str,
        agreement_ref: str | None = None,
        base_currency: str = "USD",
        threshold_amount: float = 0.0,
        mta_amount: float = 0.0,
        rounding_amount: float = 0.0,
        governing_law: str | None = None,
        effective_date: str | None = None,
        agreement_id: str | None = None,
    ) -> dict[str, Any]:
        row_id = agreement_id or f"agr_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO margin_agreements "
                "(id, counterparty_id, margin_type, agreement_ref, base_currency, "
                " threshold_amount, mta_amount, rounding_amount, governing_law, "
                " effective_date, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id, counterparty_id, margin_type, agreement_ref,
                    base_currency, threshold_amount, mta_amount, rounding_amount,
                    governing_law, effective_date, now,
                ),
            )
        return {
            "id": row_id, "counterparty_id": counterparty_id,
            "margin_type": margin_type, "agreement_ref": agreement_ref,
            "base_currency": base_currency, "threshold_amount": threshold_amount,
            "mta_amount": mta_amount, "rounding_amount": rounding_amount,
            "governing_law": governing_law, "effective_date": effective_date,
            "created_at": now, "schedule_version": 1,
        }

    def get_agreement(self, agreement_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM margin_agreements WHERE id = ?", (agreement_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_agreements(
        self,
        counterparty_id: str | None = None,
        margin_type: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if counterparty_id:
            clauses.append("counterparty_id = ?")
            params.append(counterparty_id)
        if margin_type:
            clauses.append("margin_type = ?")
            params.append(margin_type)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM margin_agreements {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Collateral entries ────────────────────────────────────────────────────

    def insert_entries(
        self,
        agreement_id: str,
        entries: list[dict[str, Any]],
        replace: bool = False,
    ) -> int:
        """Insert collateral entries for an agreement.

        When *replace* is True the current live entries are soft-superseded
        (``superseded_at`` is stamped) and the agreement's ``schedule_version``
        is incremented, preserving the full history for audit.
        """
        now = datetime.now(UTC).isoformat()
        with self._tx() as conn:
            if replace:
                # Supersede live entries and bump the agreement version atomically.
                conn.execute(
                    "UPDATE collateral_entries SET superseded_at = ? "
                    "WHERE agreement_id = ? AND superseded_at IS NULL",
                    (now, agreement_id),
                )
                conn.execute(
                    "UPDATE margin_agreements "
                    "SET schedule_version = schedule_version + 1 "
                    "WHERE id = ?",
                    (agreement_id,),
                )
            # Fetch the current version number to tag incoming rows.
            row = conn.execute(
                "SELECT schedule_version FROM margin_agreements WHERE id = ?",
                (agreement_id,),
            ).fetchone()
            version = row["schedule_version"] if row else 1

            for i, entry in enumerate(entries):
                conn.execute(
                    "INSERT INTO collateral_entries "
                    "(id, agreement_id, asset_class, isin, currency, rating_floor, "
                    " max_maturity_years, haircut_pct, concentration_limit_pct, "
                    " eligible, notes, source_row, created_at, schedule_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"ce_{uuid.uuid4().hex[:12]}",
                        agreement_id,
                        entry.get("asset_class", "OTHER"),
                        entry.get("isin"),
                        entry.get("currency"),
                        entry.get("rating_floor"),
                        entry.get("max_maturity_years"),
                        float(entry.get("haircut_pct", 0.0)),
                        entry.get("concentration_limit_pct"),
                        int(bool(entry.get("eligible", True))),
                        entry.get("notes"),
                        entry.get("source_row", i + 1),
                        now,
                        version,
                    ),
                )
        return len(entries)

    def list_entries(
        self,
        agreement_id: str,
        asset_class: str | None = None,
        eligible_only: bool = False,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        """Return collateral entries for an agreement.

        By default only the current (live) entries are returned.  Pass
        ``include_history=True`` to retrieve all versions including superseded
        entries; each row carries ``schedule_version`` and ``superseded_at``
        for audit purposes.
        """
        clauses = ["agreement_id = ?"]
        params: list[Any] = [agreement_id]
        if not include_history:
            clauses.append("superseded_at IS NULL")
        if asset_class:
            clauses.append("asset_class = ?")
            params.append(asset_class)
        if eligible_only:
            clauses.append("eligible = 1")
        where = "WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM collateral_entries {where} "
                "ORDER BY schedule_version DESC, asset_class, haircut_pct",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def list_schedule_history(self, agreement_id: str) -> list[dict[str, Any]]:
        """Return a summary of each schedule version for an agreement.

        Each item describes one version: when it was ingested, how many entries
        it contained, and (for superseded versions) when it was replaced.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT schedule_version, "
                "       COUNT(*) AS entry_count, "
                "       MIN(created_at) AS ingested_at, "
                "       MAX(superseded_at) AS superseded_at "
                "FROM collateral_entries "
                "WHERE agreement_id = ? "
                "GROUP BY schedule_version "
                "ORDER BY schedule_version",
                (agreement_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_entries(self, agreement_id: str) -> int:
        """Hard-delete all entries (live and historical) for an agreement."""
        with self._tx() as conn:
            cur = conn.execute(
                "DELETE FROM collateral_entries WHERE agreement_id = ?",
                (agreement_id,),
            )
        return cur.rowcount

    def summary(self, agreement_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN eligible=1 THEN 1 ELSE 0 END) as eligible_count, "
                "MIN(haircut_pct) as min_haircut, MAX(haircut_pct) as max_haircut, "
                "AVG(haircut_pct) as avg_haircut "
                "FROM collateral_entries WHERE agreement_id = ?",
                (agreement_id,),
            ).fetchone()
            classes = conn.execute(
                "SELECT DISTINCT asset_class FROM collateral_entries "
                "WHERE agreement_id = ? AND eligible = 1",
                (agreement_id,),
            ).fetchall()
        return {
            "total_entries": row["total"] or 0,
            "eligible_count": row["eligible_count"] or 0,
            "min_haircut_pct": row["min_haircut"],
            "max_haircut_pct": row["max_haircut"],
            "avg_haircut_pct": round(row["avg_haircut"], 4) if row["avg_haircut"] else None,
            "eligible_asset_classes": [r["asset_class"] for r in classes],
        }
