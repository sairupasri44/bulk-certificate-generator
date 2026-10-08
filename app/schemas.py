from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RecipientCreate(BaseModel):
    name: Annotated[NonEmptyText, Field(max_length=200)]


class JobCreate(BaseModel):
    event_name: Annotated[NonEmptyText, Field(max_length=200)]
    course_name: Annotated[NonEmptyText, Field(max_length=200)]
    date: date
    recipients: Annotated[list[RecipientCreate], Field(min_length=1)]


class JobCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total: int
    successful: int
    failed: int


class JobStatus(BaseModel):
    job_id: int
    status: str
    total: int
    successful: int
    failed: int
    completed: int
    progress_percent: float


class CertificateResult(BaseModel):
    certificate_id: int
    recipient_name: str
    status: str
    download_url: str | None
    error_message: str | None