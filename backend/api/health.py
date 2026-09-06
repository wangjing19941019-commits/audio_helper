import uuid

from fastapi import APIRouter

from schemas import HealthData, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(
        request_id=str(uuid.uuid4()),
        data=HealthData(status="ok"),
    )
