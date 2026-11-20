from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.evaluation import EvalTask, EvalRowResult

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/metrics")
def evaluation_metrics(db: Session = Depends(get_db)):
    """Return lightweight operational metrics for dashboards and probes."""
    task_counts = dict(
        db.query(EvalTask.status, func.count(EvalTask.id))
        .group_by(EvalTask.status)
        .all()
    )
    row_count = db.query(func.count(EvalRowResult.id)).scalar() or 0
    error_count = db.query(func.count(EvalRowResult.id)).filter(EvalRowResult.error.isnot(None)).scalar() or 0
    return {
        "evaluation_tasks": task_counts,
        "evaluation_rows": row_count,
        "evaluation_errors": error_count,
        "queue_workers": "configured via EVAL_QUEUE_WORKERS",
    }
