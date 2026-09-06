from pydantic import BaseModel, ConfigDict, Field


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


class AsrRequest(BaseModel):
    audio_id: str


class AsrData(BaseModel):
    text: str


class AsrResponse(BaseModel):
    request_id: str
    data: AsrData


class ExtractRequest(BaseModel):
    text: str
    city: str = Field(examples=["杭州"])


class ExtractData(BaseModel):
    city_a: str
    address_a: str
    city_b: str
    address_b: str
    category: str


class ExtractResponse(BaseModel):
    request_id: str
    data: ExtractData


class ExtractModelOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    city_a: str | None
    address_a: str | None
    city_b: str | None
    address_b: str | None
    category: str | None
    party_count: int | None
    incomplete_reason: str | None
