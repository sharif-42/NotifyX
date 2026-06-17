# -- Notification status state machine ---------------------------------------
# The three legal states for ``notifications.status``. Validated at the DB
# level by a CHECK constraint in the Notification model, and at the API
# level by the response schemas.
#
# Inherits from ``(str, Enum)`` so the members are also strings —
# convenient for direct use as column defaults (``default='pending'``)
# and so Pydantic V2 can serialise the enum to its ``.value`` in JSON
# responses without any custom encoder.

from enum import Enum


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# -- Failure-reason prefixes ------------------------------------------------
# When the worker marks a notification ``failed``, ``failure_reason`` is
# prefixed with one of these so the tenant's dashboard (or any future
# classifier) can distinguish permanent failures (bad recipient, invalid
# template) from transient ones (provider 5xx, network timeout, etc.).
#
# Phase 1 does not retry, but the prefix is recorded on the row so Phase 2
# can implement a retry policy on transient failures without a schema
# change.

FAILURE_REASON_PERMANENT_PREFIX = "permanent: "
FAILURE_REASON_TRANSIENT_PREFIX = "transient: "