"""`GET /api/health`: liveness probe that also reports the running version."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from kairos import __version__

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", operation_id="get_health")
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
