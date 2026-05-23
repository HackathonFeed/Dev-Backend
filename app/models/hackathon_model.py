import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import EventMode, RegistrationStatus
from app.core.database import Base


class Hackathon(Base):
    """Maps to the existing hackathons table created by the scraper pipeline."""

    __tablename__ = "hackathons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    platform_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    organizer: Mapped[str] = mapped_column(Text, default="Unknown")
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    prize_pool: Mapped[str] = mapped_column(Text, default="Not specified")
    mode: Mapped[EventMode] = mapped_column(
        Enum(EventMode, name="event_mode", create_type=False),
        default=EventMode.UNKNOWN,
    )
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RegistrationStatus | None] = mapped_column(
        Enum(RegistrationStatus, name="registration_status", create_type=False),
        nullable=True,
    )
    registrations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligibility: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    team_size: Mapped[str] = mapped_column(Text, default="Not specified")
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    sponsors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    source_platform: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
