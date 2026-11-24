from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.task_queue import queue_snapshot
from app.models.evaluation import EvalTask, EvalRowResult

router = APIRouter(prefix="/observability", tags=["Observability"])


def _duration_ms(started_at, finished_at):
    if not started_at or not finished_at:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=timezone.utc)
    return max(0.0, (finished_at - started_at).total_seconds() * 1000)


@router.get("/health")
def observability_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok", "queue": queue_snapshot(SessionLocal)}


@router.get("/metrics")
def evaluation_metrics(db: Session = Depends(get_db)):
    task_counts = dict(
        db.query(EvalTask.status, func.count(EvalTask.id))
        .group_by(EvalTask.status)
        .all()
    )
    row_count = db.query(func.count(EvalRowResult.id)).scalar() or 0
    row_error_count = db.query(func.count(EvalRowResult.id)).filter(EvalRowResult.error.isnot(None)).scalar() or 0
    row_pass_count = db.query(func.count(EvalRowResult.id)).filter(EvalRowResult.is_pass.is_(True)).scalar() or 0
    row_fail_count = db.query(func.count(EvalRowResult.id)).filter(EvalRowResult.is_pass.is_(False)).scalar() or 0
    recent_tasks = (
        db.query(EvalTask.started_at, EvalTask.finished_at)
        .filter(EvalTask.status == "completed", EvalTask.started_at.isnot(None), EvalTask.finished_at.isnot(None))
        .order_by(EvalTask.finished_at.desc())
        .limit(500)
        .all()
    )
    durations = sorted(value for start, finish in recent_tasks if (value := _duration_ms(start, finish)) is not None)
    percentile = lambda p: round(durations[min(int((len(durations) - 1) * p), len(durations) - 1)], 2) if durations else None
    return {
        "evaluation_tasks": task_counts,
        "evaluation_rows": row_count,
        "evaluation_errors": row_error_count,
        "evaluation_pass_rows": row_pass_count,
        "evaluation_fail_rows": row_fail_count,
        "task_latency_ms": {
            "count": len(durations),
            "mean": round(sum(durations) / len(durations), 2) if durations else None,
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "max": round(durations[-1], 2) if durations else None,
        },
        "queue": queue_snapshot(SessionLocal),
    }


@router.get("/traces")
def evaluation_traces(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    tasks = db.query(EvalTask).order_by(EvalTask.created_at.desc(), EvalTask.id.desc()).limit(limit).all()
    return [
        {
            "trace_id": task.trace_id,
            "task_id": task.id,
            "name": task.name,
            "status": task.status,
            "evaluation_mode": task.evaluation_mode,
            "dataset_id": task.dataset_id,
            "scenario_id": task.scenario_id,
            "progress": task.progress or 0,
            "total_rows": task.total_rows or 0,
            "completed_rows": task.completed_rows or 0,
            "queue_attempts": task.queue_attempts or 0,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "duration_ms": _duration_ms(task.started_at, task.finished_at),
            "error": task.error_message,
        }
        for task in tasks
    ]
