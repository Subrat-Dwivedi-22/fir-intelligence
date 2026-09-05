from datetime import datetime

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    timestamp: datetime | None = None
    title: str
    description: str
    key_points: list[str] = Field(default_factory=list)
    entities_involved: list[str] = Field(default_factory=list)
