"""Schema-per-tenant tenancy, backed by SQLite.

Real Postgres schemas are simulated with prefixed tables
(tenant_<org>_projects, tenant_<org>_activity) — the shape and the
isolation guarantee are the same: code bound to one tenant's tables
cannot read another's.
"""
from __future__ import annotations

import sqlite3


class Tenancy:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT);
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS tenant_registry (
                org_id TEXT PRIMARY KEY, schema_name TEXT);
            CREATE TABLE IF NOT EXISTS memberships (
                user_id TEXT, org_id TEXT, PRIMARY KEY (user_id, org_id));
        """)

    def create_organization(self, org_id: str, name: str) -> str:
        """Create the org and its schema (its tables). The hook that makes
        isolation structural: no org exists without its own tables."""
        schema = f"tenant_{org_id}"
        self.conn.execute(
            "INSERT INTO organizations (id, name) VALUES (?, ?)", (org_id, name))
        self.conn.execute(
            "INSERT INTO tenant_registry (org_id, schema_name) VALUES (?, ?)",
            (org_id, schema))
        self.conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS {schema}_projects (
                id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS {schema}_activity (
                seq INTEGER PRIMARY KEY, text TEXT);
        """)
        self.conn.commit()
        return schema

    def for_organization(self, org_id: str) -> "TenantTables":
        row = self.conn.execute(
            "SELECT schema_name FROM tenant_registry WHERE org_id = ?",
            (org_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown organization: {org_id}")
        return TenantTables(self.conn, row["schema_name"])

    def add_user(self, user_id: str, email: str) -> None:
        self.conn.execute(
            "INSERT INTO users (id, email) VALUES (?, ?)", (user_id, email))
        self.conn.commit()

    def add_member(self, user_id: str, org_id: str) -> None:
        self.conn.execute(
            "INSERT INTO memberships (user_id, org_id) VALUES (?, ?)",
            (user_id, org_id))
        self.conn.commit()


class TenantTables:
    """Tables bound to one organization's schema. Nothing here can read
    another org's tables — the table names are fixed at construction."""

    def __init__(self, conn: sqlite3.Connection, schema: str):
        self.conn = conn
        self.schema = schema

    def add_project(self, name: str) -> int:
        cur = self.conn.execute(
            f"INSERT INTO {self.schema}_projects (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def list_projects(self) -> list[dict]:
        cur = self.conn.execute(
            f"SELECT id, name FROM {self.schema}_projects ORDER BY id")
        return [{"id": r["id"], "name": r["name"]} for r in cur]

    def add_activity(self, text: str) -> int:
        cur = self.conn.execute(
            f"INSERT INTO {self.schema}_activity (text) VALUES (?)", (text,))
        self.conn.commit()
        return cur.lastrowid

    def list_activity(self) -> list[dict]:
        cur = self.conn.execute(
            f"SELECT seq, text FROM {self.schema}_activity ORDER BY seq")
        return [{"seq": r["seq"], "text": r["text"]} for r in cur]
