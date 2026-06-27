import json

from openai import AsyncOpenAI, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from jobplatform.config import settings
from jobplatform.jobs.models import Job
from jobplatform.profiles.models import Profile
from jobplatform.preferences.models import JobPreferences


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def get_embedding(text: str) -> list[float]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(model="text-embedding-3-small", input=text)
    return list(response.data[0].embedding)


def build_job_text(job: Job) -> str:
    parts: list[str] = [f"{job.title} at {job.company} in {job.location}"]
    if job.description:
        parts.append(job.description[:3000])
    if job.requirements:
        parts.append(f"Requirements: {json.dumps(job.requirements)[:1000]}")
    return "\n".join(parts)


def build_profile_text(profile: Profile, prefs: JobPreferences | None) -> str:
    parts: list[str] = []
    if profile.current_role:
        parts.append(f"Current role: {profile.current_role}")
    if profile.years_experience:
        parts.append(f"Years of experience: {profile.years_experience}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if profile.experience:
        roles = [
            f"{e.get('title', '')} at {e.get('company', '')}"
            for e in profile.experience
            if e.get("title")
        ]
        if roles:
            parts.append(f"Experience: {'; '.join(roles)}")
    if prefs and prefs.target_roles:
        parts.append(f"Target roles: {', '.join(prefs.target_roles)}")
    if prefs and prefs.technologies:
        parts.append(f"Technologies: {', '.join(prefs.technologies)}")
    if prefs and prefs.locations:
        parts.append(f"Preferred locations: {', '.join(prefs.locations)}")
    return "\n".join(parts)


def compute_ats_score(profile_skills: list[str], job_text: str) -> float:
    if not profile_skills:
        return 0.0
    job_lower = job_text.lower()
    matched = sum(1 for s in profile_skills if s.lower() in job_lower)
    return round(matched / len(profile_skills), 4)


def compute_skill_gaps(
    profile_skills: list[str], requirements: dict | None
) -> list[str]:
    if not requirements:
        return []
    req_skills_raw = requirements.get("skills")
    if isinstance(req_skills_raw, list):
        req_skills: list[str] = req_skills_raw
    else:
        req_skills = [
            v for v in requirements.values() if isinstance(v, str) and len(v) < 60
        ]
    profile_lower = {s.lower() for s in profile_skills}
    return [s for s in req_skills if s.lower() not in profile_lower]
