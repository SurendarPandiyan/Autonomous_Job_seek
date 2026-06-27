from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: int | None = None  # None → resolve default resume in service


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    resume_id: int | None
    status: str
    tailored_resume_text: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
