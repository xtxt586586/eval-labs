from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.sql import func

from app.core.database import Base


class JudgeCalibrationRun(Base):
    __tablename__ = "judge_calibration_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=False)
    metric_definition_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False)
    llm_config_version = Column(Integer, nullable=False, default=1)
    metric_definition_version = Column(Integer, nullable=False, default=1)
    engine_version = Column(String(50), nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    repeats = Column(Integer, nullable=False, default=1)
    mean_absolute_error = Column(Float, nullable=True)
    mean_score = Column(Float, nullable=True)
    score_variance = Column(Float, nullable=True)
    examples = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=func.now())
