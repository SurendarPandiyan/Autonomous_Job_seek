from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: int
    portal: str
    external_id: str
    url: str
    title: str
    company: str
    location: str
    description: str | None
    salary_min: int | None
    salary_max: int | None
    employment_type: str | None
    posted_at: datetime | None
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}
