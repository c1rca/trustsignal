from fastapi import APIRouter

from app.core.config import settings
from app.schemas.api_responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)
