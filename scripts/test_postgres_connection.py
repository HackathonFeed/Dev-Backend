"""Test Supabase Postgres connectivity with exact credentials."""

import asyncio

import asyncpg
import psycopg2

PASSWORD = "HackathonFeedSourceData@#$"
PROJECT_REF = "yxjeyplqbftoerfrrxqp"

CONNECTIONS = [
    {
        "label": "direct",
        "host": f"db.{PROJECT_REF}.supabase.co",
        "port": 5432,
        "user": "postgres",
    },
    {
        "label": "direct-transaction",
        "host": f"db.{PROJECT_REF}.supabase.co",
        "port": 6543,
        "user": "postgres",
    },
    {
        "label": "pooler-session-aws0",
        "host": "aws-0-ap-south-1.pooler.supabase.com",
        "port": 5432,
        "user": f"postgres.{PROJECT_REF}",
    },
    {
        "label": "pooler-session-aws1",
        "host": "aws-1-ap-south-1.pooler.supabase.com",
        "port": 5432,
        "user": f"postgres.{PROJECT_REF}",
    },
]


def test_psycopg2(params: dict) -> str:
    try:
        conn = psycopg2.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=PASSWORD,
            dbname="postgres",
            sslmode="require",
            connect_timeout=15,
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM hackathons")
        count = cur.fetchone()[0]
        conn.close()
        return f"OK ({count} hackathons)"
    except Exception as exc:
        return f"FAIL: {exc}"


async def test_asyncpg(params: dict) -> str:
    try:
        conn = await asyncpg.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=PASSWORD,
            database="postgres",
            ssl="require",
            timeout=15,
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM hackathons")
        await conn.close()
        return f"OK ({count} hackathons)"
    except Exception as exc:
        return f"FAIL: {exc}"


async def main() -> None:
    print("Password length:", len(PASSWORD))
    for params in CONNECTIONS:
        print(f"\n[{params['label']}] psycopg2 -> {test_psycopg2(params)}")
        print(f"[{params['label']}] asyncpg  -> {await test_asyncpg(params)}")


if __name__ == "__main__":
    asyncio.run(main())
