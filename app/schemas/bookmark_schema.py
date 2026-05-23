import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.hackathon_schema import HackathonResponse


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    hackathon_id: uuid.UUID
    created_at: datetime
    hackathon: HackathonResponse | None = None
