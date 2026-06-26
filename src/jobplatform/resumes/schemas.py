from datetime import datetime

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    version: int
    label: str
    is_default: bool
    file_type: str
    performance_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}
