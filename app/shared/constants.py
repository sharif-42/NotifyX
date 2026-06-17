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


# -- Environments -----------------------------------------------------------
class Environment(str, Enum):
    """Runtime environment. Drives logging format and a few feature flags."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# Practical email regex: a single ``@`` between a local part
# (``[a-zA-Z0-9._%+-]+``) and a domain with at least one dot and a
# 2+ char TLD. Not RFC 5321 perfect — the real spec is much wider — but
# it catches the common cases (typos, missing @, missing TLD) and is
# what most production systems use as the first line of defence. The
# provider (SendGrid) is the authoritative validator; this is just to
# give API callers a clean 422 before a round-trip.
RECIPIENT_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# E.164 international phone format: leading ``+`` (no ``00`` prefix),
# first digit 1-9 (no leading zero), then 1-14 more digits, total 2-15.
# Matches the ITU-T E.164 spec and the Twilio docs' "best practice"
# recommendation. The DB column is ``String(20)`` which is comfortably
# above E.164's 15-digit max — leftover room for future format
# variations.
RECIPIENT_PHONE_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")


class Channel(str, Enum):
    """Delivery channel for a template / notification.

    Mirrored on the ``channel`` column of ``templates`` and
    ``notifications`` (both ``String(10)``). The DB does NOT carry a
    CHECK for the channel value — that lets new channels (push, in-app)
    be added without a migration. Pydantic validators on the request
    schemas enforce the enum at the API boundary.
    """

    EMAIL = "email"
    SMS = "sms"
