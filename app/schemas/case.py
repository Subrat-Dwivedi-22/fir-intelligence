from enum import Enum

from pydantic import BaseModel, Field


class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CreateCaseRequest(BaseModel):
    case_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    case_type: str = Field(min_length=1)
    priority: CasePriority = CasePriority.MEDIUM
    synopsis: str | None = None
    police_station: str | None = None
    district: str | None = None


class CreateCaseResponse(BaseModel):
    case_id: str
    case_number: str
    title: str
    case_type: str
    priority: CasePriority
    synopsis: str | None = None
    status: CaseStatus


class CaseListItem(BaseModel):
    case_id: str
    case_number: str | None = None
    title: str | None = None
    case_type: str | None = None
    priority: CasePriority | None = None
    synopsis: str | None = None
    police_station: str | None = None
    status: CaseStatus
    created_at: object | None = None


class CaseSummaryResponse(BaseModel):
    case_id: str
    case_number: str
    title: str
    case_type: str | None = None
    priority: CasePriority | None = None
    synopsis: str | None = None
    police_station: str | None = None
    status: CaseStatus
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
