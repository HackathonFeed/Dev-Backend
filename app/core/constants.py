from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class EventMode(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class RegistrationStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UPCOMING = "upcoming"
    ENDED = "ended"


class HackathonSort(StrEnum):
    DEADLINE = "deadline"
    REGISTRATIONS = "registrations"
    SCRAPED_AT = "scraped_at"
    START_DATE = "start_date"


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
