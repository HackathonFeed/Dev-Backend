import asyncio
import uuid
from pathlib import Path
from time import time

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.integrations.supabase_client import get_supabase_client, is_supabase_configured

MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
EXTENSION_TO_CONTENT_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
AVATAR_BUCKET = "avatars"

BACKEND_ROOT = Path(__file__).resolve().parents[2]
AVATARS_DIR = BACKEND_ROOT / "uploads" / "avatars"


def uses_supabase_storage() -> bool:
    settings = get_settings()
    return settings.use_supabase_data_layer and is_supabase_configured()


def ensure_avatar_dir() -> Path:
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    return AVATARS_DIR


def _avatar_glob(user_id: uuid.UUID) -> list[Path]:
    ensure_avatar_dir()
    return list(AVATARS_DIR.glob(f"{user_id}.*"))


def _delete_local_avatar_files(user_id: uuid.UUID) -> None:
    for path in _avatar_glob(user_id):
        path.unlink(missing_ok=True)


def _delete_supabase_avatar_files(user_id: uuid.UUID) -> None:
    client = get_supabase_client()
    if client is None:
        return

    bucket = client.storage.from_(AVATAR_BUCKET)
    paths = [f"{user_id}{extension}" for extension in ALLOWED_CONTENT_TYPES.values()]
    try:
        bucket.remove(paths)
    except Exception:
        pass


def delete_user_avatar_files(user_id: uuid.UUID) -> None:
    if uses_supabase_storage():
        _delete_supabase_avatar_files(user_id)
    else:
        _delete_local_avatar_files(user_id)


def _save_local_avatar(user_id: uuid.UUID, content: bytes, extension: str) -> str:
    delete_user_avatar_files(user_id)
    ensure_avatar_dir()
    destination = AVATARS_DIR / f"{user_id}{extension}"
    destination.write_bytes(content)
    return f"/uploads/avatars/{user_id}{extension}?v={int(time())}"


async def _save_supabase_avatar(
    user_id: uuid.UUID,
    content: bytes,
    extension: str,
    content_type: str,
) -> str:
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase storage is not configured",
        )

    storage_path = f"{user_id}{extension}"

    def _upload() -> str:
        _delete_supabase_avatar_files(user_id)
        bucket = client.storage.from_(AVATAR_BUCKET)
        try:
            bucket.upload(
                storage_path,
                content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        except Exception as exc:
            message = str(exc)
            if "Bucket not found" in message or "bucket" in message.lower():
                raise RuntimeError(
                    "Supabase avatars bucket is missing. "
                    "Run database/add_user_avatar_url.sql in the Supabase SQL Editor."
                ) from exc
            raise RuntimeError("Could not upload profile photo to Supabase Storage") from exc

        public_url = bucket.get_public_url(storage_path)
        return f"{public_url}?v={int(time())}"

    try:
        return await asyncio.to_thread(_upload)
    except RuntimeError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "bucket is missing" in detail.lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


async def save_user_avatar(user_id: uuid.UUID, file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    extension = ALLOWED_CONTENT_TYPES.get(content_type)

    if extension is None and file.filename:
        suffix = Path(file.filename).suffix.lower()
        inferred_type = EXTENSION_TO_CONTENT_TYPE.get(suffix)
        if inferred_type:
            content_type = inferred_type
            extension = ALLOWED_CONTENT_TYPES[inferred_type]

    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only JPEG, PNG, WebP, or GIF images are allowed",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be 5 MB or smaller",
        )

    if uses_supabase_storage():
        return await _save_supabase_avatar(user_id, content, extension, content_type)

    return _save_local_avatar(user_id, content, extension)
