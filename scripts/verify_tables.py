"""Verify backend tables exist in Supabase and print setup instructions if missing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrations.supabase_client import get_supabase_client

REQUIRED_TABLES = (
    "users",
    "bookmarks",
    "analytics_events",
    "search_logs",
    "tracked_projects",
    "tracked_project_steps",
    "tracked_project_timeline_events",
    "tracked_project_milestones",
    "tracked_project_team_members",
)


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
        tracked_only = [t for t in missing if t.startswith("tracked_")]
        if tracked_only and len(tracked_only) == len(missing):
            print(f"\nRun this SQL in Supabase SQL Editor:\n  {ROOT / 'database' / 'tracked_projects_schema.sql'}")
        else:
            print(f"\nRun this SQL in Supabase SQL Editor:\n  {ROOT / 'database' / 'backend_schema.sql'}")
            if tracked_only:
                print(f"  Tracked tables only: {ROOT / 'database' / 'tracked_projects_schema.sql'}")
        print(f"\nFor profile photos, also run:\n  {ROOT / 'database' / 'add_user_avatar_url.sql'}")
        return 1

    try:
        client.table("users").select("avatar_url").limit(1).execute()
        print("[OK] users.avatar_url")
    except Exception:
        print("[MISSING] users.avatar_url column")
        print(f"\nRun this SQL in Supabase SQL Editor:\n  {ROOT / 'database' / 'add_user_avatar_url.sql'}")
        return 1

    print("\nAll backend tables are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
