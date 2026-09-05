from pydantic import BaseModel, Field


class CreateRelationshipRequest(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class RelationshipResponse(BaseModel):
    relationship_id: str
    case_id: str
    source: str
    target: str
    type: str
    evidence: str | None = None
