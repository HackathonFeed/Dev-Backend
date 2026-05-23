"""
Apply backend schema to Supabase.

Tries direct Postgres first, then falls back to Supabase SQL API patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "database" / "backend_schema.sql"


def apply_with_postgres(db_url: str) -> bool:
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    print("[INFO] Applying schema via Postgres...")
    connection = psycopg2.connect(db_url, connect_timeout=20)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(SQL_FILE.read_text(encoding="utf-8"))
        print("[OK] Schema applied via Postgres.")
        return True
    finally:
        connection.close()


def apply_with_supabase_sql_api(project_ref: str, service_key: str, sql: str) -> bool:
    """Best-effort attempt via Supabase platform endpoints."""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    endpoints = [
        f"https://{project_ref}.supabase.co/platform/pg-meta/default/query",
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
    ]
    for endpoint in endpoints:
        try:
            response = httpx.post(
                endpoint,
                headers=headers,
                json={"query": sql},
                timeout=30,
            )
            if response.status_code < 400:
                print(f"[OK] Schema applied via {endpoint}")
                return True
        except Exception:
            continue
    return False


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from app.core.config import get_settings

    settings = get_settings()
    sql = SQL_FILE.read_text(encoding="utf-8")

    if settings.database_configured:
        try:
            if apply_with_postgres(settings.database_url):
                return 0
        except Exception as exc:
            print(f"[WARN] Postgres migration failed: {exc}")

    if settings.supabase_url and settings.effective_supabase_key:
        project_ref = settings.supabase_url.rstrip("/").split("//")[-1].split(".")[0]
        if apply_with_supabase_sql_api(project_ref, settings.effective_supabase_key, sql):
            return 0

    print("[FAIL] Could not apply schema automatically.")
    print(f"Run manually in Supabase SQL Editor: {SQL_FILE}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
