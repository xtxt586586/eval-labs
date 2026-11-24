"""Database-backed task state with bounded local workers and restart recovery."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, update

from app.core.config import settings

logger = logging.getLogger(__name__)
_worker_count = max(int(settings.EVAL_QUEUE_WORKERS), 1)
_executor = ThreadPoolExecutor(max_workers=_worker_count, thread_name_prefix="eval-queue")
_active_lock = threading.Lock()
_active_task_ids: set[int] = set()
_worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def submit_evaluation(task_id: int, session_factory) -> bool:
    """Submit a pending task once and atomically claim it before execution."""
    with _active_lock:
        if task_id in _active_task_ids:
            return False
        _active_task_ids.add(task_id)

    def runner() -> None:
        db = session_factory()
        claimed = False
        try:
            from app.models.evaluation import EvalTask

            result = db.execute(
                update(EvalTask)
                .where(EvalTask.id == task_id, EvalTask.status == "pending")
                .values(
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    queue_attempts=func.coalesce(EvalTask.queue_attempts, 0) + 1,
                    worker_id=_worker_id,
                    heartbeat_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
            claimed = result.rowcount == 1
        except Exception:
            db.rollback()
            logger.exception("Could not claim queued evaluation %s", task_id)
        finally:
            db.close()

        if not claimed:
            with _active_lock:
                _active_task_ids.discard(task_id)
            return

        try:
            from app.core.evaluation_engine import run_evaluation

            asyncio.run(run_evaluation(task_id, session_factory))
        except Exception:
            logger.exception("Evaluation queue worker failed for task %s", task_id)
        finally:
            with _active_lock:
                _active_task_ids.discard(task_id)

    try:
        _executor.submit(runner)
    except Exception:
        with _active_lock:
            _active_task_ids.discard(task_id)
        raise
    return True


def recover_interrupted_evaluations(session_factory) -> int:
    """Recover only expired worker leases; live work on another instance is untouched."""
    from app.models.evaluation import EvalTask

    lease_seconds = max(int(settings.EVAL_TASK_LEASE_TIMEOUT_SECONDS), 60)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)
    db = session_factory()
    try:
        tasks = db.query(EvalTask).filter(
            EvalTask.status.in_(["running", "cancelling"]),
            (
                EvalTask.heartbeat_at < cutoff
            ) | (
                EvalTask.heartbeat_at.is_(None) & (EvalTask.started_at < cutoff)
            ),
        ).all()
        for task in tasks:
            task.status = "failed"
            task.error_message = "评测 worker 租约已过期，任务被标记为可重试失败。"
            task.finished_at = datetime.now(timezone.utc)
            task.worker_id = None
            task.heartbeat_at = None
        db.commit()
        return len(tasks)
    finally:
        db.close()


def resume_pending_evaluations(session_factory) -> int:
    """Resubmit all persisted pending work after application startup."""
    from app.models.evaluation import EvalTask

    db = session_factory()
    try:
        task_ids = [row[0] for row in db.query(EvalTask.id).filter(EvalTask.status == "pending").order_by(EvalTask.created_at, EvalTask.id).all()]
    finally:
        db.close()
    return sum(1 for task_id in task_ids if submit_evaluation(task_id, session_factory))


def queue_snapshot(session_factory) -> dict:
    from app.models.evaluation import EvalTask

    db = session_factory()
    try:
        pending = db.query(EvalTask).filter(EvalTask.status == "pending").count()
        running = db.query(EvalTask).filter(EvalTask.status.in_(["running", "cancelling"])).count()
        worker_ids = [row[0] for row in db.query(EvalTask.worker_id).filter(
            EvalTask.status.in_(["running", "cancelling"]), EvalTask.worker_id.isnot(None)
        ).distinct().all()]
        oldest = db.query(EvalTask.created_at).filter(EvalTask.status == "pending").order_by(EvalTask.created_at).first()
        queued_seconds = None
        if oldest and oldest[0]:
            created = oldest[0]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            queued_seconds = max(0, round((datetime.now(timezone.utc) - created).total_seconds(), 2))
        return {
            "worker_count": _worker_count,
            "active_count": running,
            "active_worker_count": len(worker_ids),
            "pending_count": pending,
            "oldest_pending_seconds": queued_seconds,
        }
    finally:
        db.close()
