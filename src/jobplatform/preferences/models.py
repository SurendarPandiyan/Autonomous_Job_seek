import enum

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from jobplatform.database import Base


class ExperienceLevel(enum.Enum):
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    any = "any"


class RemotePreference(enum.Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    any = "any"


class AIProviderPreference(enum.Enum):
    claude = "claude"
    openai = "openai"
    gemini = "gemini"


class JobPreferences(Base):
    __tablename__ = "job_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SAEnum(ExperienceLevel), default=ExperienceLevel.any
    )
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    locations: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    remote_preference: Mapped[RemotePreference] = mapped_column(
        SAEnum(RemotePreference), default=RemotePreference.any
    )
    notice_period_days: Mapped[int | None] = mapped_column(Integer)
    employment_type: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    company_size: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    industries: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    excluded_companies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    whitelisted_companies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    application_daily_limit: Mapped[int] = mapped_column(Integer, default=10)
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider_preference: Mapped[AIProviderPreference] = mapped_column(
        SAEnum(AIProviderPreference), default=AIProviderPreference.claude
    )
