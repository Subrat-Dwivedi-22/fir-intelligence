from datetime import datetime

from pydantic import BaseModel, Field


class CreateActivityRequest(BaseModel):
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class ActivityResponse(BaseModel):
    activity_id: str
    case_id: str
    action: str
    actor: str
    timestamp: datetime
