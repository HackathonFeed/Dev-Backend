from app.models.bookmark_model import Bookmark
from app.schemas.bookmark_schema import BookmarkResponse
from app.utils.hackathon_mapper import to_hackathon_response


def to_bookmark_response(bookmark: Bookmark) -> BookmarkResponse:
    hackathon = None
    if getattr(bookmark, "hackathon", None) is not None:
        hackathon = to_hackathon_response(bookmark.hackathon)

    return BookmarkResponse(
        id=bookmark.id,
        user_id=bookmark.user_id,
        hackathon_id=bookmark.hackathon_id,
        created_at=bookmark.created_at,
        hackathon=hackathon,
    )
