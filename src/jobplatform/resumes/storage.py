import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import aiofiles


class FileStorage(ABC):
    @abstractmethod
    async def save(self, content: bytes, filename: str) -> str:
        """Persist content; return storage path."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file; silently ignore if missing."""

    @abstractmethod
    def url(self, path: str) -> str:
        """Return access URL for the given storage path."""


class LocalFileStorage(FileStorage):
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        dest = self._base / f"{uuid.uuid4().hex}{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
        return str(dest)

    async def delete(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()

    def url(self, path: str) -> str:
        return f"/uploads/{Path(path).name}"


def get_storage() -> FileStorage:
    from jobplatform.config import settings

    return LocalFileStorage(settings.upload_dir)
