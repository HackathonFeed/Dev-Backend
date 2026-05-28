from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class SubscriptionPlan(StrEnum):
    HACKER = "hacker"      # Free – 50 pts on signup, no auto-refill
    BUILDER = "builder"    # $9/mo – 500 pts refreshed monthly
    CHAMPION = "champion"  # $29/mo – unlimited (-1 sentinel)


# Points granted per plan (−1 = unlimited)
PLAN_POINTS: dict[str, int] = {
    SubscriptionPlan.HACKER: 50,
    SubscriptionPlan.BUILDER: 500,
    SubscriptionPlan.CHAMPION: -1,
}

# Cost in points per AI chat message
AI_MESSAGE_COST = 5

# Cost in points per project detail view
PROJECT_VIEW_COST = 10


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
