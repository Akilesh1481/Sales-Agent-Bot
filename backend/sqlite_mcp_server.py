from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("SQLite Readonly MCP Server")

DB_PATH = os.getenv("DB_PATH", os.path.abspath("sales.db"))

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|replace|pragma|vacuum|reindex|truncate)\b",
    re.I,
)


def is_safe_select(sql: str) -> tuple[bool, str]:
    q = sql.strip()

    if not q.lower().startswith("select"):
        return False, "Only SELECT queries are allowed."

    if FORBIDDEN_SQL.search(q):
        return False, "Blocked SQL keyword found."

    if ";" in q.rstrip(";"):
        return False, "Multiple SQL statements are not allowed."

    return True, "safe"


def connect_readonly() -> sqlite3.Connection:
    uri = f"file:{os.path.abspath(DB_PATH)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def run_readonly_sql(sql: str) -> List[Dict[str, Any]]:
    """
    Execute a safe read-only SQLite SELECT query.

    This MCP tool is the only place where SQL is sent to the database.
    It blocks INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, and other write operations.
    """
    safe, reason = is_safe_select(sql)

    if not safe:
        raise ValueError(reason)

    conn = connect_readonly()

    try:
        cur = conn.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        return rows

    finally:
        conn.close()


@mcp.tool()
def get_database_schema() -> str:
    """
    Return database schema as text.
    This helps the backend and agents understand available tables and columns.
    """
    conn = connect_readonly()

    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        chunks: List[str] = []

        for table in tables:
            table_name = table[0]
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            col_text = ", ".join([f"{c['name']} {c['type']}" for c in cols])
            chunks.append(f"{table_name}({col_text})")

        return "\n".join(chunks)

    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()