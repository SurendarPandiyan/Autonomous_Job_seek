import os

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.resumes.models import FileType, Resume
from jobplatform.resumes.storage import FileStorage

_ALLOWED_EXTS = {".pdf": FileType.pdf, ".docx": FileType.docx}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf": FileType.pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.docx,
}


async def upload_resume(
    db: AsyncSession,
    storage: FileStorage,
    user_id: int,
    file: UploadFile,
    label: str = "",
) -> Resume:
    ext = os.path.splitext(file.filename or "")[1].lower()
    file_type = _ALLOWED_EXTS.get(ext) or _ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if file_type is None:
        raise HTTPException(400, "Only PDF and DOCX files are accepted")
    content = await file.read()
    path = await storage.save(content, file.filename or "resume")
    existing_count = await db.scalar(
        select(func.count()).select_from(Resume).where(Resume.user_id == user_id)
    )
    is_default = (existing_count or 0) == 0
    version = (existing_count or 0) + 1
    resume = Resume(
        user_id=user_id,
        version=version,
        label=label,
        is_default=is_default,
        file_path=path,
        file_type=file_type,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


async def list_resumes(db: AsyncSession, user_id: int) -> list[Resume]:
    result = await db.scalars(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
    )
    return list(result.all())


async def get_resume(db: AsyncSession, user_id: int, resume_id: int) -> Resume:
    resume = await db.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    if not resume:
        raise HTTPException(404, "Resume not found")
    return resume


async def delete_resume(
    db: AsyncSession, storage: FileStorage, user_id: int, resume_id: int
) -> None:
    resume = await get_resume(db, user_id, resume_id)
    await storage.delete(resume.file_path)
    await db.delete(resume)
    await db.commit()
