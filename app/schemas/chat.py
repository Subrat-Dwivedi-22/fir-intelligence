from pydantic import BaseModel, Field


class CaseChatRequest(BaseModel):
    message: str = Field(min_length=1)


class CaseChatResponse(BaseModel):
    case_id: str
    answer: str
