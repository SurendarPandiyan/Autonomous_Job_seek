from datetime import datetime
from typing import Any
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from jobplatform.database import Base


class ProfileSource(enum.Enum):
    resume = "resume"
    manual = "manual"
    linkedin_import = "linkedin_import"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    github_url: Mapped[str | None] = mapped_column(String(512))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    current_role: Mapped[str | None] = mapped_column(String(255))
    current_company: Mapped[str | None] = mapped_column(String(255))
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    certifications: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[ProfileSource] = mapped_column(SAEnum(ProfileSource), default=ProfileSource.manual)
