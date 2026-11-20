import statistics
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.evaluation_engine import OpenAIJudgeClient, build_metric
from app.models.llm_config import LLMConfig
from app.models.metric_definition import MetricDefinition
from app.schemas.evaluation import JudgeCalibrationRequest, JudgeCalibrationResponse

router = APIRouter(prefix="/calibration", tags=["Judge Calibration"])


@router.post("/judge", response_model=JudgeCalibrationResponse)
async def calibrate_judge(payload: JudgeCalibrationRequest, db: Session = Depends(get_db)):
    if not payload.examples:
        raise HTTPException(status_code=422, detail="至少需要一个校准样本")
    repeats = max(1, min(payload.repeats, 3))
    llm_config = db.query(LLMConfig).filter(LLMConfig.id == payload.llm_config_id).first()
    metric_def = db.query(MetricDefinition).filter(MetricDefinition.id == payload.metric_definition_id).first()
    if not llm_config or not metric_def:
        raise HTTPException(status_code=404, detail="LLM 配置或指标不存在")

    kind, metric = build_metric(metric_def, scenario_metric=SimpleNamespace(weight=1.0, pass_threshold=None))
    judge = OpenAIJudgeClient(llm_config)
    samples = []
    scores = []
    for index, example in enumerate(payload.examples):
        observed = []
        for _ in range(repeats):
            result = await metric.ascore(dict(example.sample), judge)
            if isinstance(result.value, (int, float)):
                observed.append(float(result.value))
        if not observed:
            continue
        scores.extend(observed)
        mean = sum(observed) / len(observed)
        samples.append({
            "index": index,
            "expected_score": example.expected_score,
            "observed_scores": [round(value, 4) for value in observed],
            "mean_absolute_error": round(abs(mean - example.expected_score), 4),
        })

    return JudgeCalibrationResponse(
        metric_name=metric_def.name,
        sample_count=len(samples),
        repeats=repeats,
        mean_absolute_error=(
            round(sum(item["mean_absolute_error"] for item in samples) / len(samples), 4)
            if samples else None
        ),
        mean_score=round(sum(scores) / len(scores), 4) if scores else None,
        score_variance=round(statistics.pvariance(scores), 6) if len(scores) > 1 else 0.0 if scores else None,
        samples=samples,
    )
