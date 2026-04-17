from fastapi import APIRouter

from app.api.auth_routes import router as auth_router
from app.api.critical_actions_routes import router as critical_actions_router
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


router.include_router(auth_router)
router.include_router(critical_actions_router)
