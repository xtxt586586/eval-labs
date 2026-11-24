from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

database_url = make_url(settings.DATABASE_URL)
engine_options = {"pool_pre_ping": True}
if database_url.drivername.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_options)


if database_url.drivername.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_runtime_schema() -> None:
    """Apply tiny SQLite-compatible schema additions for existing local DBs."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    version_columns = {
        "datasets": ("version", "ALTER TABLE datasets ADD COLUMN version INTEGER NOT NULL DEFAULT 1"),
        "llm_configs": ("version", "ALTER TABLE llm_configs ADD COLUMN version INTEGER NOT NULL DEFAULT 1"),
        "metric_definitions": ("version", "ALTER TABLE metric_definitions ADD COLUMN version INTEGER NOT NULL DEFAULT 1"),
    }
    with engine.begin() as connection:
        current_tables = set(inspect(engine).get_table_names())
        for table, (column, statement) in version_columns.items():
            if table not in current_tables:
                continue
            columns = {item["name"] for item in inspect(engine).get_columns(table)}
            if column not in columns:
                connection.execute(text(statement))

    if not engine.dialect.name.startswith("sqlite"):
        return
    if "metric_definitions" in table_names:
        metric_columns = {column["name"] for column in inspector.get_columns("metric_definitions")}
        if "updated_at" not in metric_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE metric_definitions ADD COLUMN updated_at DATETIME"))
                if "created_at" in metric_columns:
                    connection.execute(text("UPDATE metric_definitions SET updated_at = created_at WHERE updated_at IS NULL"))
    if "eval_tasks" not in table_names:
        return

    eval_task_columns = {column["name"] for column in inspector.get_columns("eval_tasks")}
    eval_task_additions = {
        "scenario_snapshot": "ALTER TABLE eval_tasks ADD COLUMN scenario_snapshot JSON",
        "evaluation_mode": "ALTER TABLE eval_tasks ADD COLUMN evaluation_mode VARCHAR(50) DEFAULT 'offline'",
        "endpoint_target_id": "ALTER TABLE eval_tasks ADD COLUMN endpoint_target_id INTEGER",
        "target_config": "ALTER TABLE eval_tasks ADD COLUMN target_config JSON",
        "response_mapping": "ALTER TABLE eval_tasks ADD COLUMN response_mapping JSON",
        "result_save_mode": "ALTER TABLE eval_tasks ADD COLUMN result_save_mode VARCHAR(50) DEFAULT 'task_only'",
        "dataset_snapshot": "ALTER TABLE eval_tasks ADD COLUMN dataset_snapshot JSON",
        "llm_config_snapshot": "ALTER TABLE eval_tasks ADD COLUMN llm_config_snapshot JSON",
        "queue_attempts": "ALTER TABLE eval_tasks ADD COLUMN queue_attempts INTEGER DEFAULT 0",
        "worker_id": "ALTER TABLE eval_tasks ADD COLUMN worker_id VARCHAR(200)",
        "heartbeat_at": "ALTER TABLE eval_tasks ADD COLUMN heartbeat_at DATETIME",
        "trace_id": "ALTER TABLE eval_tasks ADD COLUMN trace_id VARCHAR(100)",
    }
    missing_eval_task_sql = [
        sql for name, sql in eval_task_additions.items() if name not in eval_task_columns
    ]
    if missing_eval_task_sql:
        with engine.begin() as connection:
            for sql in missing_eval_task_sql:
                connection.execute(text(sql))

    if "rag_dataset_jobs" in table_names:
        rag_job_columns = {column["name"] for column in inspector.get_columns("rag_dataset_jobs")}
        additions = {
            "target_endpoint_url": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_endpoint_url VARCHAR(1000)",
            "target_transport_mode": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_transport_mode VARCHAR(50) DEFAULT 'sse'",
            "target_authorization": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_authorization TEXT",
            "target_extra_headers": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_extra_headers TEXT",
            "target_request_body_template": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_request_body_template TEXT",
        }
        missing_sql = [sql for name, sql in additions.items() if name not in rag_job_columns]
        if missing_sql:
            with engine.begin() as connection:
                for sql in missing_sql:
                    connection.execute(text(sql))

    if "eval_row_results" in table_names:
        row_result_columns = {column["name"] for column in inspector.get_columns("eval_row_results")}
        additions = {
            "manual_status": "ALTER TABLE eval_row_results ADD COLUMN manual_status VARCHAR(50)",
            "manual_score": "ALTER TABLE eval_row_results ADD COLUMN manual_score FLOAT",
            "manual_tags": "ALTER TABLE eval_row_results ADD COLUMN manual_tags JSON",
            "manual_note": "ALTER TABLE eval_row_results ADD COLUMN manual_note TEXT",
            "reviewed_at": "ALTER TABLE eval_row_results ADD COLUMN reviewed_at DATETIME",
            "endpoint_trace": "ALTER TABLE eval_row_results ADD COLUMN endpoint_trace JSON",
        }
        missing_sql = [sql for name, sql in additions.items() if name not in row_result_columns]
        if missing_sql:
            with engine.begin() as connection:
                for sql in missing_sql:
                    connection.execute(text(sql))

    if "scenario_metrics" in table_names:
        scenario_metric_columns = {column["name"] for column in inspector.get_columns("scenario_metrics")}
        if "prompt_override" not in scenario_metric_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE scenario_metrics ADD COLUMN prompt_override TEXT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
