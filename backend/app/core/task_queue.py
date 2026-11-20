"""Small durable-state task queue abstraction.

The queue keeps execution outside request handlers and persists status in the
database.  It is intentionally replaceable by Celery/Temporal later; the
public API does not depend on the execution backend.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(
    max_workers=max(int(os.getenv("EVAL_QUEUE_WORKERS", "2")), 1),
    thread_name_prefix="eval-queue",
)


def submit_evaluation(task_id: int, session_factory) -> None:
    from app.core.evaluation_engine import run_evaluation

    def runner() -> None:
        try:
            asyncio.run(run_evaluation(task_id, session_factory))
        except Exception:
            logger.exception("Evaluation queue worker failed for task %s", task_id)

    _executor.submit(runner)


def recover_interrupted_evaluations(session_factory) -> int:
    """Mark tasks left running by a process restart as retryable failures."""
    from app.models.evaluation import EvalTask

    db = session_factory()
    try:
        tasks = db.query(EvalTask).filter(EvalTask.status == "running").all()
        for task in tasks:
            task.status = "failed"
            task.error_message = "评测进程重启，任务被标记为可重试失败。"
            task.finished_at = datetime.now(timezone.utc)
        db.commit()
        return len(tasks)
    finally:
        db.close()
