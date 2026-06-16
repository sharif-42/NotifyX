"""Cross-cutting constants used across the application.

Layering: this module is *pure* (no I/O, no imports from the rest of the
app). Anything that wants to reference these constants — error
envelopes, worker logic, future dashboard / classifier code — imports
them from here so there is one canonical place to change them.
"""

from __future__ import annotations

from enum import Enum
import re


# -- App metadata ------------------------------------------------------------
APP_NAME = "NotifyX"
APP_VERSION = "0.1.0"


# Compiled once at import time. The DB CHECK uses the same expression.
TENANT_CODE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# -- Environments -----------------------------------------------------------
class Environment(str, Enum):
    """Runtime environment. Drives logging format and a few feature flags."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# -- Notification status state machine ---------------------------------------
# The three legal states for ``notifications.status``. Validated at the DB
# level by a CHECK constraint in the Notification model, and at the API
# level by the response schemas. Listed here as a tuple so callers can
# iterate or membership-check without importing the model module.

PENDING = "pending"
SENT = "sent"
FAILED = "failed"

class NotificationStatus(str, Enum):
    PENDING = PENDING
    SENT = SENT
    FAILED = FAILED


# -- Failure-reason prefixes ------------------------------------------------
# When the worker marks a notification ``failed``, ``failure_reason`` is
# prefixed with one of these so the tenant's dashboard (or any
# classifier) can distinguish permanent failures (bad recipient, invalid
# template) from transient ones (provider 5xx, network timeout, etc.).
#
# Phase 1 does not retry, but the prefix is recorded on the row so Phase 2
# can implement a retry policy on transient failures without a schema
# change.

FAILURE_REASON_PERMANENT_PREFIX = "permanent: "
FAILURE_REASON_TRANSIENT_PREFIX = "transient: "
