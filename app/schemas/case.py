from pydantic import BaseModel


class CreateCaseRequest(BaseModel):
    case_number: str
    title: str
    police_station: str | None = None
    district: str | None = None


class CreateCaseResponse(BaseModel):
    case_id: str
    case_number: str
    title: str
    status: str


class CaseListItem(BaseModel):
    case_id: str
    case_number: str | None = None
    title: str | None = None
    police_station: str | None = None
    status: str
    created_at: object | None = None


class CaseSummaryResponse(BaseModel):
    case_id: str
    case_number: str
    title: str
    police_station: str | None = None
    status: str
    document_count: int
    person_count: int
    unknown_identity_count: int
    incident_count: int
    entity_count: int
    relationship_count: int
    analysis_available: bool


class CaseDetailResponse(BaseModel):
    case: dict
    persons: list[dict]
    unknown_identities: list[dict]
    incidents: list[dict]
    entities: list[dict]
    relationships: list[dict]
    documents: list[dict]
    ingestion_jobs: list[dict]