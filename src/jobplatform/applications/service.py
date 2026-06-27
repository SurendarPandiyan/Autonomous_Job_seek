import logging

import structlog
from anthropic import AsyncAnthropic, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jobplatform.config import settings
from jobplatform.resumes.models import Resume

# Patch target for tests: "jobplatform.applications.service.AsyncAnthropic"
logger = structlog.get_logger()

TAILOR_PROMPT = """\
You are a professional resume writer. Tailor the following resume to the job description.
Preserve all factual content. Emphasize matching skills and experience.
Return ONLY the tailored resume text, no preamble.

JOB DESCRIPTION:
{job_description}

ORIGINAL RESUME:
{resume_text}
"""


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def tailor_resume(resume_text: str, job_description: str) -> str:
    """Call Claude claude-haiku-4-5 to tailor resume_text to job_description.

    Retries up to 5 times on RateLimitError with exponential backoff (2s–60s).
    Returns the tailored resume as a plain string.
    """
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": TAILOR_PROMPT.format(
                    job_description=job_description,
                    resume_text=resume_text,
                ),
            }
        ],
    )
    return response.content[0].text


def extract_resume_text(resume: Resume) -> str:
    """Extract resume text from Resume.parsed_data (JSONB dict → string).

    Falls back to empty string if parsed_data is None, and logs a warning so
    the Celery task can still proceed (it will store a placeholder and mark applied).
    """
    if resume.parsed_data is None:
        logger.warning(
            "extract_resume_text.no_parsed_data",
            resume_id=resume.id,
        )
        return ""
    return str(resume.parsed_data)
