from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import task_queue
from app.models.evaluation import EvalTask


def _task_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}")
    EvalTask.__table__.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _task(task_id: int, status: str, started_at, heartbeat_at=None):
    return EvalTask(
        id=task_id,
        name=f"task-{task_id}",
        dataset_id=1,
        scenario_id=1,
        llm_config_id=1,
        status=status,
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        worker_id=f"worker-{task_id}" if status == "running" else None,
    )


def test_recovery_only_marks_expired_worker_leases(tmp_path, monkeypatch):
    engine, sessions = _task_engine(tmp_path)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        db.add_all([
            _task(1, "running", now - timedelta(hours=1), now - timedelta(hours=1)),
            _task(2, "running", now - timedelta(hours=1), now - timedelta(minutes=1)),
        ])
        db.commit()
    monkeypatch.setattr(task_queue.settings, "EVAL_TASK_LEASE_TIMEOUT_SECONDS", 900)

    recovered = task_queue.recover_interrupted_evaluations(sessions)
    snapshot = task_queue.queue_snapshot(sessions)

    assert recovered == 1
    assert snapshot["active_count"] == 1
    assert snapshot["active_worker_count"] == 1
    with sessions() as db:
        assert db.get(EvalTask, 1).status == "failed"
        assert db.get(EvalTask, 1).worker_id is None
        assert db.get(EvalTask, 2).status == "running"
    engine.dispose()


def test_task_attempt_counter_increments_once_when_claimed(tmp_path, monkeypatch):
    engine, sessions = _task_engine(tmp_path)
    with sessions() as db:
        db.add(_task(1, "pending", None))
        db.commit()

    class InlineExecutor:
        def submit(self, callback):
            callback()

    async def run_evaluation(_task_id, _session_factory):
        return None

    monkeypatch.setattr(task_queue, "_executor", InlineExecutor())
    monkeypatch.setattr("app.core.evaluation_engine.run_evaluation", run_evaluation)
    monkeypatch.setattr(task_queue, "_active_task_ids", set())

    assert task_queue.submit_evaluation(1, sessions) is True
    with sessions() as db:
        claimed = db.get(EvalTask, 1)
        assert claimed.queue_attempts == 1
        assert claimed.status == "running"
        assert claimed.worker_id
        assert claimed.heartbeat_at
    engine.dispose()
