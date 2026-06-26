from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user
from jobplatform.resumes.schemas import ResumeResponse
from jobplatform.resumes.service import delete_resume, get_resume, list_resumes, upload_resume
from jobplatform.resumes.storage import FileStorage, get_storage

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeResponse, status_code=201)
async def upload(
    file: UploadFile = File(...),
    label: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
):
    return await upload_resume(db, storage, current_user.id, file, label)


@router.get("/", response_model=list[ResumeResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_resumes(db, current_user.id)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_one(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_resume(db, current_user.id, resume_id)


@router.delete("/{resume_id}", status_code=204)
async def delete_one(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
):
    await delete_resume(db, storage, current_user.id, resume_id)
    return Response(status_code=204)
