from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user
from jobplatform.jobs.models import Job
from jobplatform.jobs.service import get_job  # noqa: F401  (kept per plan contract)
from jobplatform.matching.models import JobMatch
from jobplatform.matching.schemas import MatchResponse
from jobplatform.matching.service import (
    build_job_text,
    build_profile_text,
    compute_ats_score,
    compute_skill_gaps,
    find_similar_jobs,  # noqa: F401  (kept per plan contract)
    get_embedding,
    get_job_match,
    list_matches,
    upsert_match,
)
from jobplatform.preferences.models import JobPreferences
from jobplatform.profiles.models import Profile

router = APIRouter(tags=["matching"])


@router.get("/api/v1/matches/", response_model=list[MatchResponse])
async def list_matches_endpoint(
    limit: int = Query(default=50, le=200),
    cursor: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobMatch]:
    return await list_matches(db, current_user.id, limit=limit, cursor=cursor)


@router.get("/api/v1/jobs/{job_id}/match")
async def get_job_match_endpoint(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Branch 1: pre-computed match exists → return it
    match = await get_job_match(db, current_user.id, job_id)
    if match:
        return MatchResponse.model_validate(match)

    # Load job to determine if on-demand compute is possible
    job = await db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await db.scalar(select(Profile).where(Profile.user_id == current_user.id))

    # Branch 2: embeddings missing → return 202 pending
    if job.embedding is None or profile is None or profile.embedding is None:
        return JSONResponse(
            status_code=202,
            content={"status": "pending", "score": None, "job_id": job_id},
        )

    # Branch 3: both embeddings present → compute on-demand via pgvector DB query
    prefs = await db.scalar(
        select(JobPreferences).where(JobPreferences.user_id == current_user.id)
    )
    profile_text = build_profile_text(profile, prefs)
    profile_embedding = await get_embedding(profile_text)

    stmt = (
        select((1 - Job.embedding.cosine_distance(profile_embedding)).label("score"))
        .where(Job.id == job_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    score = float(row.score) if row else 0.0

    job_text = build_job_text(job)
    ats = compute_ats_score(profile.skills or [], job_text)
    gaps = compute_skill_gaps(profile.skills or [], job.requirements)

    await upsert_match(db, current_user.id, job_id, score, ats, gaps)
    await db.commit()

    match = await get_job_match(db, current_user.id, job_id)
    return MatchResponse.model_validate(match)
