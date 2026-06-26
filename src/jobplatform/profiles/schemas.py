from typing import Any
from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    years_experience: int | None = None
    current_role: str | None = None
    current_company: str | None = None
    skills: list[str] | None = None
    education: list[dict[str, Any]] | None = None
    experience: list[dict[str, Any]] | None = None
    certifications: list[dict[str, Any]] | None = None


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    github_url: str | None
    years_experience: int | None
    current_role: str | None
    current_company: str | None
    skills: list[str]
    education: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    certifications: list[dict[str, Any]]
    source: str

    model_config = {"from_attributes": True, "use_enum_values": True}
