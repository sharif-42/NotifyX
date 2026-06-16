"""Health-check endpoint placeholder (filled in at Step 14)."""

from __future__ import annotations

from fastapi import APIRouter

# Empty placeholder router so ``app.api.v1.router`` can import it
# without exploding. Step 14 will add ``GET /v1/health/live`` and
# ``GET /v1/health/ready`` here.
router = APIRouter(prefix="/health", tags=["health"])
