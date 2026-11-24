"""Stable snapshots for reproducible evaluation runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SNAPSHOT_VERSION = "eval-snapshot/v2"
METRIC_ENGINE_VERSION = "agent-eval/v2"


def build_dataset_snapshot(dataset, rows: list[Any]) -> dict[str, Any]:
    payload = {
        "version": SNAPSHOT_VERSION,
        "dataset_id": dataset.id,
        "dataset_version": getattr(dataset, "version", 1),
        "name": dataset.name,
        "sample_type": dataset.sample_type,
        "field_schema": dataset.field_schema or [],
        "rows": [
            {"id": row.id, "row_index": row.row_index, "data": row.data or {}}
            for row in rows
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["content_hash"] = hashlib.sha256(encoded).hexdigest()
    return payload


def build_llm_config_snapshot(config) -> dict[str, Any]:
    payload = {
        "provider": config.provider,
        "llm_config_id": config.id,
        "llm_config_version": getattr(config, "version", 1),
        "api_base_url": config.api_base_url,
        "model_name": config.model_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "metric_engine_version": METRIC_ENGINE_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["content_hash"] = hashlib.sha256(encoded).hexdigest()
    return payload
