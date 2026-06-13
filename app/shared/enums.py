from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class TenantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TenantPlan(str, Enum):
    FREE = "FREE"
    STANDARD = "STANDARD"
    ENTERPRISE = "ENTERPRISE"


class TemplateChannel(str, Enum):
    EMAIL = "EMAIL"


class NotificationType(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationAttemptStatus(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"


class RetryJobStatus(str, Enum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
