from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    HEAD = "head"
    AGENT = "agent"


class InterestStatus(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class DealType(StrEnum):
    RENT = "rent"
    SALE = "sale"


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"


class AuditEntity(StrEnum):
    PROPERTY = "property"
    MEDIA = "media"
    USER = "user"
    DISTRICT = "district"
