import json
from datetime import datetime, timezone

import structlog

from jobplatform.config import settings

logger = structlog.get_logger()


def _safe_str(obj: object) -> str:
    try:
        return str(obj)
    except Exception:
        return type(obj).__name__


def publish_log(task_id: str, level: str, message: str, progress_pct: float = 0.0) -> None:
    try:
        import redis as _redis
        r = _redis.from_url(settings.redis_url)
        event = json.dumps({
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "progress_pct": progress_pct,
        })
        r.publish(f"task:{task_id}:logs", event)
    except Exception as exc:
        logger.warning("publish_log.failed", task_id=task_id, error=str(exc))


def get_task_status(task_id: str) -> dict:
    from jobplatform.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "error": _safe_str(result.result) if result.failed() else None,
    }
