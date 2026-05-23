"""Verify backend tables exist in Supabase and print setup instructions if missing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrations.supabase_client import get_supabase_client

REQUIRED_TABLES = ("users", "bookmarks", "analytics_events", "search_logs")


def main() -> int:
    client = get_supabase_client()
    if client is None:
        print("Supabase is not configured in .env")
        return 1

    missing = []
    for table in REQUIRED_TABLES:
        try:
            client.table(table).select("*", count="exact").limit(1).execute()
            print(f"[OK] {table}")
        except Exception:
            missing.append(table)
            print(f"[MISSING] {table}")

    if missing:
        print("\nRun this SQL in Supabase SQL Editor:")
        print(f"  {ROOT / 'database' / 'backend_schema.sql'}")
        return 1

    print("\nAll backend tables are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
