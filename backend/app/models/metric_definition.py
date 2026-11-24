from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    metric_type = Column(String(50), nullable=False)
    config = Column(JSON, nullable=True)
    category = Column(String(100), nullable=True)
    is_builtin = Column(Boolean, default=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
