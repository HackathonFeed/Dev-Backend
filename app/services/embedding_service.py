"""
Embedding service — generates and stores Amazon Titan Embed v2 vectors
for devfolio_projects rows that have no embedding yet.

Called from:
  • POST /admin/generate-embeddings  (FastAPI background task)
  • The scraper pipeline after inserting new projects
  • scripts/generate_project_embeddings.py  (one-time bootstrap)
"""
import asyncio
import logging

from app.integrations.supabase_client import get_supabase_client
from app.services.ai_validator_service import get_bedrock_embedding

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50   # rows fetched per Supabase query
_CONCURRENCY = 5  # parallel Bedrock calls per batch


def _project_to_text(row: dict) -> str:
    """Combine project fields into a single string for embedding."""
    parts: list[str] = []
    if row.get("title"):
        parts.append(row["title"])
    if row.get("tagline"):
        parts.append(row["tagline"])
    techs = row.get("technologies") or []
    if techs:
        parts.append("Technologies: " + ", ".join(techs[:10]))
    if row.get("hackathon_name"):
        parts.append("Hackathon: " + row["hackathon_name"])
    if row.get("prize"):
        parts.append("Prize: " + row["prize"])
    return ". ".join(p.strip() for p in parts if p.strip())


async def _embed_and_store(client, row: dict) -> bool:
    """Generate embedding for one project and update Supabase. Returns success."""
    text = _project_to_text(row)
    if not text.strip():
        logger.debug("Skipping %s — no text content", row["id"])
        return False

    embedding = await get_bedrock_embedding(text)
    if not embedding:
        logger.warning("Embedding failed for project %s", row["id"])
        return False

    def _update():
        client.table("devfolio_projects").update(
            {"embedding": embedding}
        ).eq("id", row["id"]).execute()

    await asyncio.to_thread(_update)
    return True


async def generate_missing_embeddings() -> dict:
    """
    Fetch all projects where embedding IS NULL and generate embeddings.
    Safe to call repeatedly — only processes un-embedded rows.
    Returns a summary dict: {processed, skipped, errors, total}.
    """
    client = get_supabase_client()
    if client is None:
        logger.error("Supabase not configured — cannot generate embeddings")
        return {"processed": 0, "skipped": 0, "errors": 0, "total": 0}

    # Collect all un-embedded project IDs + minimal fields
    rows: list[dict] = []
    offset = 0
    while True:
        def _fetch(off=offset):
            return (
                client.table("devfolio_projects")
                .select("id, title, tagline, technologies, hackathon_name, prize")
                .is_("embedding", "null")
                .range(off, off + _PAGE_SIZE - 1)
                .execute()
            )

        resp = await asyncio.to_thread(_fetch)
        page = resp.data or []
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    total = len(rows)
    logger.info("Found %d projects needing embeddings", total)

    if total == 0:
        return {"processed": 0, "skipped": 0, "errors": 0, "total": 0}

    processed = errors = skipped = 0

    # Process in concurrent batches of _CONCURRENCY
    for i in range(0, total, _CONCURRENCY):
        batch = rows[i : i + _CONCURRENCY]
        results = await asyncio.gather(
            *[_embed_and_store(client, row) for row in batch],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                logger.exception("Unexpected error during embedding: %s", result)
            elif result is True:
                processed += 1
            else:
                skipped += 1

        logger.info(
            "Progress: %d/%d processed, %d errors",
            processed + skipped,
            total,
            errors,
        )

    return {"processed": processed, "skipped": skipped, "errors": errors, "total": total}
