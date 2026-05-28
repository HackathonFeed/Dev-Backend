"""
One-time / on-demand script: generate embeddings for all projects missing them.
Uses the same EmbeddingService as the FastAPI endpoint.

Usage (from project root, with venv active):
    python scripts/generate_project_embeddings.py

Safe to re-run — only processes rows where embedding IS NULL.
"""
import asyncio
import sys
import os

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.embedding_service import generate_missing_embeddings


async def main():
    print("Starting embedding generation …")
    result = await generate_missing_embeddings()
    print(
        f"\nDone.\n"
        f"  Processed : {result['processed']}\n"
        f"  Skipped   : {result['skipped']}  (no text content)\n"
        f"  Errors    : {result['errors']}\n"
        f"  Total     : {result['total']}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
