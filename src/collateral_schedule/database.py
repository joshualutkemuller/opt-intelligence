"""SQLite- and Postgres-backed store for counterparty collateral schedules.

Pass a ``path`` (or nothing) to use SQLite.  Pass a ``dsn`` starting with
``postgresql://`` or ``postgres://`` to use Postgres via psycopg2.

SQLite is the default and requires no extra dependencies.  Postgres support
requires ``pip install psycopg2-binary`` (or ``psycopg2``).
"""

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
    superseded_at          TEXT,
    isin_invalid           TEXT
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
    "ALTER TABLE collateral_entries ADD COLUMN isin_invalid TEXT",
]


class CollateralDatabase:
    """Collateral schedule store backed by SQLite (default) or Postgres.

    Parameters
    ----------
    path:
        File path for the SQLite database.  Ignored when *dsn* is provided.
    dsn:
        Postgres connection string (``postgresql://user:pass@host/db``).
        Requires ``psycopg2`` to be installed.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        dsn: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._is_postgres = dsn is not None and dsn.startswith(("postgresql://", "postgres://"))
        # Placeholder style differs between SQLite (?) and Postgres (%s)
        self._ph = "%s" if self._is_postgres else "?"

        if not self._is_postgres:
            self._path = Path(path) if path else _DEFAULT_DB_PATH
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):  # type: ignore[return]
        if self._is_postgres:
            try:
                import psycopg2  # type: ignore[import-untyped]
                import psycopg2.extras  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Postgres support requires psycopg2: pip install psycopg2-binary"
                ) from exc
            conn = psycopg2.connect(self._dsn)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _tx(self) -> Generator[Any, None, None]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _exec(self, conn: Any, sql: str, params: tuple = ()) -> Any:
        """Execute SQL with the backend's placeholder style."""
        if self._is_postgres:
            sql = sql.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur

    def _init_db(self) -> None:
        if self._is_postgres:
            self._init_postgres()
        else:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        with self._tx() as conn:
            conn.executescript(_DDL)
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # column/index already exists on databases created post-migration

    def _init_postgres(self) -> None:
        # PRAGMA and CREATE INDEX IF NOT EXISTS are not valid in all Postgres versions;
        # split the DDL and skip SQLite-only statements.
        skip_prefixes = ("PRAGMA",)
        pg_ddl = _DDL.replace("INTEGER NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1")
        stmts = [s.strip() for s in pg_ddl.split(";") if s.strip()]
        with self._tx() as conn:
            cur = conn.cursor()
            for stmt in stmts:
                if any(stmt.upper().startswith(p) for p in skip_prefixes):
                    continue
                cur.execute(stmt)
            # Run migrations, ignoring "column already exists" errors
            for stmt in _MIGRATIONS:
                if any(stmt.upper().startswith(p) for p in skip_prefixes):
                    continue
                try:
                    cur.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()

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
            self._exec(
                conn,
                "INSERT INTO counterparties (id, name, lei, jurisdiction, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row_id, name, lei, jurisdiction, now),
            )
        return {"id": row_id, "name": name, "lei": lei, "jurisdiction": jurisdiction, "created_at": now}

    def get_counterparty(self, counterparty_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            cur = self._exec(conn, "SELECT * FROM counterparties WHERE id = ?", (counterparty_id,))
            row = cur.fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def list_counterparties(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = self._exec(conn, "SELECT * FROM counterparties ORDER BY name")
            rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def upsert_counterparty(
        self,
        name: str,
        lei: str | None = None,
        jurisdiction: str | None = None,
        counterparty_id: str | None = None,
    ) -> dict[str, Any]:
        if lei:
            conn = self._connect()
            try:
                cur = self._exec(conn, "SELECT * FROM counterparties WHERE lei = ?", (lei,))
                row = cur.fetchone()
            finally:
                conn.close()
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
            self._exec(
                conn,
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
        conn = self._connect()
        try:
            cur = self._exec(conn, "SELECT * FROM margin_agreements WHERE id = ?", (agreement_id,))
            row = cur.fetchone()
        finally:
            conn.close()
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
        conn = self._connect()
        try:
            cur = self._exec(
                conn,
                f"SELECT * FROM margin_agreements {where} ORDER BY created_at DESC",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
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
                self._exec(
                    conn,
                    "UPDATE collateral_entries SET superseded_at = ? "
                    "WHERE agreement_id = ? AND superseded_at IS NULL",
                    (now, agreement_id),
                )
                self._exec(
                    conn,
                    "UPDATE margin_agreements "
                    "SET schedule_version = schedule_version + 1 "
                    "WHERE id = ?",
                    (agreement_id,),
                )
            cur = self._exec(
                conn,
                "SELECT schedule_version FROM margin_agreements WHERE id = ?",
                (agreement_id,),
            )
            row = cur.fetchone()
            version = row["schedule_version"] if row else 1

            for i, entry in enumerate(entries):
                self._exec(
                    conn,
                    "INSERT INTO collateral_entries "
                    "(id, agreement_id, asset_class, isin, currency, rating_floor, "
                    " max_maturity_years, haircut_pct, concentration_limit_pct, "
                    " eligible, notes, source_row, created_at, schedule_version, isin_invalid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                        entry.get("isin_invalid"),
                    ),
                )
        return len(entries)

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Fetch a single collateral entry by its primary key."""
        conn = self._connect()
        try:
            cur = self._exec(conn, "SELECT * FROM collateral_entries WHERE id = ?", (entry_id,))
            row = cur.fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def update_entry(self, entry_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update editable fields of a single live collateral entry.

        Only whitelisted fields can be changed; ``id``, ``agreement_id``,
        ``created_at``, ``schedule_version``, and ``superseded_at`` are
        immutable.  Returns the updated row, or None if not found / superseded.
        """
        _EDITABLE = {
            "asset_class", "isin", "currency", "rating_floor",
            "max_maturity_years", "haircut_pct", "concentration_limit_pct",
            "eligible", "notes",
        }
        updates = {k: v for k, v in fields.items() if k in _EDITABLE}
        if not updates:
            return self.get_entry(entry_id)

        # Re-validate ISIN if it changed
        if "isin" in updates and updates["isin"]:
            from .models import validate_isin
            valid, reason = validate_isin(str(updates["isin"]))
            updates["isin_invalid"] = None if valid else reason
        elif "isin" in updates and not updates["isin"]:
            updates["isin_invalid"] = None

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]
        with self._tx() as conn:
            self._exec(
                conn,
                f"UPDATE collateral_entries SET {set_clause} "
                f"WHERE id = ? AND superseded_at IS NULL",
                tuple(values),
            )
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        """Hard-delete a single live collateral entry.

        Returns True if a row was deleted, False if not found or already superseded.
        """
        with self._tx() as conn:
            cur = self._exec(
                conn,
                "DELETE FROM collateral_entries WHERE id = ? AND superseded_at IS NULL",
                (entry_id,),
            )
        return (cur.rowcount or 0) > 0

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
        entries.
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
        conn = self._connect()
        try:
            cur = self._exec(
                conn,
                f"SELECT * FROM collateral_entries {where} "
                "ORDER BY schedule_version DESC, asset_class, haircut_pct",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def list_schedule_history(self, agreement_id: str) -> list[dict[str, Any]]:
        """Return a per-version audit summary of schedule ingestions."""
        conn = self._connect()
        try:
            cur = self._exec(
                conn,
                "SELECT schedule_version, "
                "       COUNT(*) AS entry_count, "
                "       MIN(created_at) AS ingested_at, "
                "       MAX(superseded_at) AS superseded_at "
                "FROM collateral_entries "
                "WHERE agreement_id = ? "
                "GROUP BY schedule_version "
                "ORDER BY schedule_version",
                (agreement_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def delete_entries(self, agreement_id: str) -> int:
        """Hard-delete all entries (live and historical) for an agreement."""
        with self._tx() as conn:
            cur = self._exec(
                conn,
                "DELETE FROM collateral_entries WHERE agreement_id = ?",
                (agreement_id,),
            )
        return cur.rowcount or 0

    def summary(self, agreement_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            cur = self._exec(
                conn,
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN eligible=1 THEN 1 ELSE 0 END) as eligible_count, "
                "MIN(haircut_pct) as min_haircut, MAX(haircut_pct) as max_haircut, "
                "AVG(haircut_pct) as avg_haircut "
                "FROM collateral_entries WHERE agreement_id = ? AND superseded_at IS NULL",
                (agreement_id,),
            )
            row = cur.fetchone()
            cur2 = self._exec(
                conn,
                "SELECT DISTINCT asset_class FROM collateral_entries "
                "WHERE agreement_id = ? AND eligible = 1 AND superseded_at IS NULL",
                (agreement_id,),
            )
            classes = cur2.fetchall()
        finally:
            conn.close()
        return {
            "total_entries": row["total"] or 0,
            "eligible_count": row["eligible_count"] or 0,
            "min_haircut_pct": row["min_haircut"],
            "max_haircut_pct": row["max_haircut"],
            "avg_haircut_pct": round(row["avg_haircut"], 4) if row["avg_haircut"] else None,
            "eligible_asset_classes": [r["asset_class"] for r in classes],
        }
