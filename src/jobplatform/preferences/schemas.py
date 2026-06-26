from pydantic import BaseModel


class PreferencesUpdate(BaseModel):
    target_roles: list[str] | None = None
    experience_level: str | None = None
    technologies: list[str] | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    locations: list[str] | None = None
    remote_preference: str | None = None
    notice_period_days: int | None = None
    employment_type: list[str] | None = None
    company_size: list[str] | None = None
    industries: list[str] | None = None
    excluded_companies: list[str] | None = None
    whitelisted_companies: list[str] | None = None
    application_daily_limit: int | None = None
    auto_apply: bool | None = None
    ai_provider_preference: str | None = None


class PreferencesResponse(BaseModel):
    user_id: int
    target_roles: list[str]
    experience_level: str
    technologies: list[str]
    salary_min: int | None
    salary_max: int | None
    currency: str
    locations: list[str]
    remote_preference: str
    notice_period_days: int | None
    employment_type: list[str]
    company_size: list[str]
    industries: list[str]
    excluded_companies: list[str]
    whitelisted_companies: list[str]
    application_daily_limit: int
    auto_apply: bool
    ai_provider_preference: str

    model_config = {"from_attributes": True, "use_enum_values": True}
