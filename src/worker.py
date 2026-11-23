"""Event queue + per-organization entity.

Events live in the database, so a crash loses nothing. Each org has one
entity that handles its messages one at a time, in order, writing numbered
activity rows back into that org's schema.
"""
from __future__ import annotations

import json
import sqlite3

from .tenancy import Tenancy, TenantTables


class Entity:
    """One long-lived object per organization. Handles messages one at a
    time, in order. Stateless across restarts — the state is the queue."""

    def __init__(self, tables: TenantTables):
        self.tables = tables

    def handle(self, event: dict) -> None:
        if event["kind"] == "project-created":
            self.tables.add_activity(
                f"Project '{event['name']}' was created.")


class Worker:
    def __init__(self, tenancy: Tenancy):
        self.tenancy = tenancy
        self.conn = tenancy.conn
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS event_queue (
                id INTEGER PRIMARY KEY, org_id TEXT,
                event_json TEXT, state TEXT DEFAULT 'pending');
        """)
        self.conn.commit()
        self._entities: dict[str, Entity] = {}

    def enqueue(self, org_id: str, event: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO event_queue (org_id, event_json) VALUES (?, ?)",
            (org_id, json.dumps(event)))
        self.conn.commit()
        return cur.lastrowid

    def _entity(self, org_id: str) -> Entity:
        if org_id not in self._entities:
            self._entities[org_id] = Entity(
                self.tenancy.for_organization(org_id))
        return self._entities[org_id]

    def run_once(self) -> int:
        """Process every pending event, in order. Returns the count."""
        cur = self.conn.execute(
            "SELECT id, org_id, event_json FROM event_queue "
            "WHERE state = 'pending' ORDER BY id")
        rows = cur.fetchall()
        for row in rows:
            self._entity(row["org_id"]).handle(json.loads(row["event_json"]))
            self.conn.execute(
                "UPDATE event_queue SET state = 'done' WHERE id = ?",
                (row["id"],))
        self.conn.commit()
        return len(rows)

    def pending_count(self) -> int:
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM event_queue WHERE state = 'pending'")
        return cur.fetchone()[0]
