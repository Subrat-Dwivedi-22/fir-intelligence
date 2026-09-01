from pydantic import BaseModel, Field


class InvestigationRecommendation(BaseModel):
    priority: str
    recommendation: str
    reason: str
    evidence_basis: list[str] = Field(
        default_factory=list
    )


class InvestigationAnalysisResponse(BaseModel):
    case_id: str
    summary: str
    key_findings: list[str] = Field(
        default_factory=list
    )
    unresolved_identities: list[str] = Field(
        default_factory=list
    )
    relationship_findings: list[str] = Field(
        default_factory=list
    )
    evidence_gaps: list[str] = Field(
        default_factory=list
    )
    investigation_recommendations: list[
        InvestigationRecommendation
    ] = Field(
        default_factory=list
    )
