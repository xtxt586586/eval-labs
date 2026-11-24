import hashlib
import json
import statistics
from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.evaluation_engine import OpenAIJudgeClient, build_metric
from app.core.snapshots import METRIC_ENGINE_VERSION
from app.models.calibration import JudgeCalibrationRun
from app.models.llm_config import LLMConfig
from app.models.metric_definition import MetricDefinition
from app.schemas.evaluation import JudgeCalibrationRequest, JudgeCalibrationResponse

router = APIRouter(prefix="/calibration", tags=["Judge Calibration"])


def _calibration_response(run: JudgeCalibrationRun, metric_name: str) -> JudgeCalibrationResponse:
    return JudgeCalibrationResponse(
        id=run.id,
        metric_name=metric_name,
        llm_config_version=run.llm_config_version,
        metric_definition_version=run.metric_definition_version,
        engine_version=run.engine_version,
        requested_sample_count=run.sample_count,
        sample_count=sum(1 for item in run.examples or [] if "observed_scores" in item),
        error_count=sum(1 for item in run.examples or [] if "error" in item),
        repeats=run.repeats,
        mean_absolute_error=run.mean_absolute_error,
        mean_score=run.mean_score,
        score_variance=run.score_variance,
        samples=run.examples or [],
    )


@router.get("/judge", response_model=list[JudgeCalibrationResponse])
def list_judge_calibrations(limit: int = 50, db: Session = Depends(get_db)):
    runs = (
        db.query(JudgeCalibrationRun, MetricDefinition.name)
        .join(MetricDefinition, MetricDefinition.id == JudgeCalibrationRun.metric_definition_id)
        .order_by(JudgeCalibrationRun.created_at.desc(), JudgeCalibrationRun.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [_calibration_response(run, metric_name) for run, metric_name in runs]


@router.post("/judge", response_model=JudgeCalibrationResponse)
async def calibrate_judge(payload: JudgeCalibrationRequest, db: Session = Depends(get_db)):
    llm_config = db.query(LLMConfig).filter(LLMConfig.id == payload.llm_config_id).first()
    metric_def = db.query(MetricDefinition).filter(MetricDefinition.id == payload.metric_definition_id).first()
    if not llm_config or not metric_def:
        raise HTTPException(status_code=404, detail="LLM 配置或指标不存在")

    kind, metric = build_metric(metric_def, scenario_metric=SimpleNamespace(weight=1.0, pass_threshold=None))
    if kind != "llm":
        raise HTTPException(status_code=400, detail="Judge 校准仅适用于 LLM 评判指标")

    judge = OpenAIJudgeClient(llm_config)
    sample_results = []
    all_scores = []
    absolute_errors = []
    repeat_variances = []
    for index, example in enumerate(payload.examples):
        observed = []
        error = None
        attempted_requests = 0
        for _ in range(payload.repeats):
            attempted_requests += 1
            try:
                result = await metric.ascore(dict(example.sample), judge)
                if isinstance(result.value, (int, float)):
                    observed.append(float(result.value))
                else:
                    error = result.reason or "Judge 未返回数值分数"
                    break
            except Exception as exc:
                error = str(exc)[:500]
                break

        fingerprint = hashlib.sha256(
            json.dumps(example.sample, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if error or not observed:
            sample_results.append({
                "index": index,
                "sample_hash": fingerprint,
                "expected_score": example.expected_score,
                "error": error or "未得到可用分数",
                "attempted_requests": attempted_requests,
            })
            continue
        mean = sum(observed) / len(observed)
        repeat_variance = statistics.pvariance(observed) if len(observed) > 1 else 0.0
        absolute_error = abs(mean - example.expected_score)
        all_scores.extend(observed)
        absolute_errors.append(absolute_error)
        repeat_variances.append(repeat_variance)
        sample_results.append({
            "index": index,
            "sample_hash": fingerprint,
            "expected_score": example.expected_score,
            "observed_scores": [round(value, 4) for value in observed],
            "mean_absolute_error": round(absolute_error, 4),
            "repeat_score_variance": round(repeat_variance, 6),
            "attempted_requests": attempted_requests,
        })

    run = JudgeCalibrationRun(
        llm_config_id=llm_config.id,
        metric_definition_id=metric_def.id,
        llm_config_version=getattr(llm_config, "version", 1),
        metric_definition_version=getattr(metric_def, "version", 1),
        engine_version=METRIC_ENGINE_VERSION,
        sample_count=len(payload.examples),
        repeats=payload.repeats,
        mean_absolute_error=round(sum(absolute_errors) / len(absolute_errors), 4) if absolute_errors else None,
        mean_score=round(sum(all_scores) / len(all_scores), 4) if all_scores else None,
        score_variance=round(sum(repeat_variances) / len(repeat_variances), 6) if repeat_variances else None,
        examples=sample_results,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _calibration_response(run, metric_def.name)
