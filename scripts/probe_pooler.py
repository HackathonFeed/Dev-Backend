"""Probe Supabase Postgres pooler connectivity."""

import asyncio

import asyncpg

PASSWORD = "HackathonFeedSourceData@#$"
PROJECT_REF = "yxjeyplqbftoerfrrxqp"
USER = f"postgres.{PROJECT_REF}"

REGIONS = [
    "ap-south-1",
    "ap-southeast-1",
    "ap-northeast-1",
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "eu-central-2",
    "ca-central-1",
    "sa-east-1",
]


async def try_host(prefix: str, region: str, port: int) -> None:
    host = f"{prefix}-{region}.pooler.supabase.com"
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=USER,
            password=PASSWORD,
            database="postgres",
            ssl="require",
            timeout=8,
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM hackathons")
        await conn.close()
        print(f"SUCCESS {host}:{port} hackathons={count}")
    except Exception as exc:
        message = str(exc)
        if "tenant" not in message.lower() and "enotfound" not in message.lower():
            print(f"INTERESTING {host}:{port} -> {message[:160]}")


async def main() -> None:
    for region in REGIONS:
        for prefix in ("aws-0", "aws-1"):
            for port in (5432, 6543):
                await try_host(prefix, region, port)


if __name__ == "__main__":
    asyncio.run(main())
