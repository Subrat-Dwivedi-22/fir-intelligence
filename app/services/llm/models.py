from pydantic import BaseModel, Field


class RelationshipCandidate(BaseModel):
    subject: str
    subject_type: str

    predicate: str

    object: str
    object_type: str

    evidence: str


class IncidentAnalysis(BaseModel):
    summary: str | None = None

    key_points: list[str] = Field(
        default_factory=list
    )

    modus_operandi: list[str] = Field(
        default_factory=list
    )

    relationships: list[RelationshipCandidate] = Field(
        default_factory=list
    )
