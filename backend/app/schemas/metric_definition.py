from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class MetricCreate(BaseModel):
    name: str
    display_name: str
    metric_type: str
    config: Dict = {}
    category: str = "custom"


class MetricUpdate(BaseModel):
    name: str
    display_name: str
    metric_type: str
    config: Dict = {}
    category: str = "custom"


class MetricResponse(BaseModel):
    id: int
    name: str
    display_name: str
    metric_type: str
    config: Optional[Dict] = None
    category: Optional[str] = None
    is_builtin: bool
    version: int = 1
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
