"""
Initialize Supabase connection and backend tables.

Uses Supabase REST (service role key) for verification.
Attempts direct Postgres migration when pooler access works.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


def verify_rest_connection() -> tuple[bool, int]:
    from app.integrations.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is None:
        print("[FAIL] Supabase REST is not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY.")
        return False, 0

    response = client.table("hackathons").select("id", count="exact").limit(1).execute()
    total = response.count or 0
    print(f"[OK] Supabase REST connected. Hackathons in database: {total}")
    return True, total


def missing_tables() -> list[str]:
    from app.integrations.supabase_client import get_supabase_client

    client = get_supabase_client()
    missing: list[str] = []
    for table in REQUIRED_TABLES:
        try:
            client.table(table).select("*", count="exact").limit(1).execute()
            print(f"[OK] table exists: {table}")
        except Exception:
            missing.append(table)
            print(f"[MISSING] table: {table}")
    return missing


def try_apply_schema_with_postgres() -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.database_configured:
        return False

    sql_file = ROOT / "database" / "backend_schema.sql"
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        import psycopg2

        print("[INFO] Attempting direct Postgres migration...")
        connection = psycopg2.connect(db_url, connect_timeout=15)
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(sql_file.read_text(encoding="utf-8"))
        connection.close()
        print("[OK] Backend schema applied via Postgres.")
        return True
    except Exception as exc:
        print(f"[WARN] Postgres migration unavailable: {exc}")
        return False


def main() -> int:
    print("=== HackathonFeed Supabase Initialization ===\n")

    ok, _ = verify_rest_connection()
    if not ok:
        return 1

    missing = missing_tables()
    if not missing:
        try:
            from app.integrations.supabase_client import get_supabase_client

            client = get_supabase_client()
            client.table("users").select("avatar_url").limit(1).execute()
            print("[OK] users.avatar_url")
        except Exception:
            print("[MISSING] users.avatar_url column")
            print(f"\nRun in Supabase SQL Editor: {ROOT / 'database' / 'add_user_avatar_url.sql'}")
            return 1
        print("\nAll backend tables are ready.")
        return 0

    if try_apply_schema_with_postgres():
        missing = missing_tables()
        if not missing:
            try:
                from app.integrations.supabase_client import get_supabase_client

                client = get_supabase_client()
                client.table("users").select("avatar_url").limit(1).execute()
                print("[OK] users.avatar_url")
            except Exception:
                print("[MISSING] users.avatar_url column")
                print(f"\nRun in Supabase SQL Editor: {ROOT / 'database' / 'add_user_avatar_url.sql'}")
                return 1
            print("\nAll backend tables are ready.")
            return 0

    print("\nAction required:")
    print("1. Open Supabase Dashboard -> SQL Editor")
    tracked_only = [t for t in missing if t.startswith("tracked_")]
    if tracked_only and len(tracked_only) == len(missing):
        print(f"2. Run the SQL file: {ROOT / 'database' / 'tracked_projects_schema.sql'}")
    else:
        print(f"2. Run the SQL file: {ROOT / 'database' / 'backend_schema.sql'}")
        if tracked_only:
            print(f"   (or tracked tables only: {ROOT / 'database' / 'tracked_projects_schema.sql'})")
    print(f"3. Run profile photo setup: {ROOT / 'database' / 'add_user_avatar_url.sql'}")
    print("4. Re-run: uv run python scripts/init_supabase.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
