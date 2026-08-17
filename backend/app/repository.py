from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY, supplier_id INTEGER NOT NULL, filename TEXT NOT NULL, document_type TEXT NOT NULL, status TEXT NOT NULL, policy_outcome TEXT, quality_score REAL, confidence REAL, extracted_text TEXT, explanation_json TEXT, findings_json TEXT, days_until_expiry INTEGER, created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, actor TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, action TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS evidence_supplier_index ON evidence(supplier_id);
CREATE INDEX IF NOT EXISTS audit_entity_index ON audit_events(entity_type, entity_id);
"""


class Repository:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def create_supplier(self, name: str) -> dict[str, Any]:
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO suppliers(name) VALUES (?)", (name,))
            return dict(connection.execute("SELECT * FROM suppliers WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def supplier(self, supplier_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
            return dict(row) if row else None

    def create_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = list(payload)
        values = [payload[field] for field in fields]
        placeholders = ",".join("?" for _ in fields)
        with self.connection() as connection:
            cursor = connection.execute(f"INSERT INTO evidence({','.join(fields)}) VALUES ({placeholders})", values)
            row = connection.execute("SELECT * FROM evidence WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return self._parse(dict(row)) if row else {}

    def evidence(self, evidence_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            return self._parse(dict(row)) if row else None

    def update_evidence(self, evidence_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        assignments = ",".join(f"{key} = ?" for key in payload)
        with self.connection() as connection:
            connection.execute(f"UPDATE evidence SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [*payload.values(), evidence_id])
        return self.evidence(evidence_id)

    def list_evidence(self, supplier_id: int | None = None) -> list[dict[str, Any]]:
        query, values = ("SELECT * FROM evidence ORDER BY updated_at DESC", []) if supplier_id is None else ("SELECT * FROM evidence WHERE supplier_id = ? ORDER BY updated_at DESC", [supplier_id])
        with self.connection() as connection:
            return [self._parse(dict(row)) for row in connection.execute(query, values).fetchall()]

    def audit(self, actor: str, entity_type: str, entity_id: int, action: str, description: str) -> None:
        with self.connection() as connection:
            connection.execute("INSERT INTO audit_events(actor, entity_type, entity_id, action, description) VALUES (?, ?, ?, ?, ?)", (actor, entity_type, str(entity_id), action, description))

    def list_audit(self, entity_type: str | None = None, entity_id: str | None = None) -> list[dict[str, Any]]:
        query, values = "SELECT * FROM audit_events", []
        if entity_type and entity_id:
            query += " WHERE entity_type = ? AND entity_id = ?"; values = [entity_type, entity_id]
        query += " ORDER BY created_at DESC"
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(query, values).fetchall()]

    @staticmethod
    def _parse(row: dict[str, Any]) -> dict[str, Any]:
        for key in ("explanation_json", "findings_json"):
            if row.get(key): row[key.removesuffix("_json")] = json.loads(row[key])
        return row
