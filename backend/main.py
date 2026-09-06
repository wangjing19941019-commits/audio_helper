import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.health import router as health_router
from api.upload import router as upload_router
from config import settings
from errors import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="语音约碰面地点", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


def _error_payload(request: Request, code: str, message: str, stage: str) -> dict:
    return {
        "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
        "error": {"code": code, "message": message, "stage": stage},
    }


def _stage_from_path(path: str) -> str:
    if path.startswith("/upload"):
        return "upload"
    if path.startswith("/health"):
        return "health"
    return "upload"


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    logging.getLogger(__name__).warning(
        "stage=%s code=%s status=%s",
        exc.stage,
        exc.code,
        exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, exc.code, exc.message, exc.stage),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request,
            "VALIDATION_ERROR",
            "请求缺少 file 字段，或字段类型不正确。",
            _stage_from_path(request.url.path),
        ),
    )


app.include_router(health_router)
app.include_router(upload_router)
