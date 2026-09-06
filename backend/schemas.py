from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: str = Field(examples=["ok"])


class HealthResponse(BaseModel):
    request_id: str
    data: HealthData


class ErrorBody(BaseModel):
    code: str
    message: str
    stage: str


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorBody


class UploadData(BaseModel):
    audio_id: str


class UploadResponse(BaseModel):
    request_id: str
    data: UploadData
