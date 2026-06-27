from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    score: float | None
    ats_score: float | None
    skill_gaps: list[str] | None
    status: str
    created_at: datetime
    updated_at: datetime
