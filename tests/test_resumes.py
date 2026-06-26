import os
import tempfile

from jobplatform.resumes.storage import LocalFileStorage


async def test_local_storage_save_and_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalFileStorage(tmpdir)
        content = b"PDF content here"
        path = await storage.save(content, "resume.pdf")
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        url = storage.url(path)
        assert url.startswith("/uploads/")
        await storage.delete(path)
        assert not os.path.exists(path)


async def test_local_storage_delete_nonexistent_is_noop():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalFileStorage(tmpdir)
        await storage.delete("/nonexistent/path.pdf")  # must not raise
