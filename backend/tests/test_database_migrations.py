from sqlalchemy import create_engine, inspect, text

from app.core import database


def test_runtime_schema_adds_missing_metric_version_and_updated_at(tmp_path, monkeypatch):
    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE metric_definitions (id INTEGER PRIMARY KEY, created_at DATETIME)"
        ))
        connection.execute(text(
            "INSERT INTO metric_definitions (id, created_at) VALUES (1, '2026-01-01 00:00:00')"
        ))
        connection.execute(text(
            "CREATE TABLE eval_tasks (id INTEGER PRIMARY KEY, status VARCHAR(50), started_at DATETIME)"
        ))
    monkeypatch.setattr(database, "engine", legacy_engine)

    database.ensure_runtime_schema()

    columns = {item["name"] for item in inspect(legacy_engine).get_columns("metric_definitions")}
    assert {"version", "updated_at"}.issubset(columns)
    task_columns = {item["name"] for item in inspect(legacy_engine).get_columns("eval_tasks")}
    assert {"worker_id", "heartbeat_at"}.issubset(task_columns)
    with legacy_engine.connect() as connection:
        values = connection.execute(text(
            "SELECT version, updated_at FROM metric_definitions WHERE id = 1"
        )).one()
    assert values.version == 1
    assert values.updated_at == "2026-01-01 00:00:00"
    legacy_engine.dispose()
