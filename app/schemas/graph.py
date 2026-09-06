from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    entity_type: str | None = None
    roles: list[str] = []


class GraphEdge(BaseModel):
    id: str
    from_: dict = Field(alias="from")
    to: dict = Field(alias="to")
    type: str
    evidence: str | None = None
    confidence: float | None = None
    weight: float = 0.50

    model_config = {
        "populate_by_name": True,
    }


class CaseGraphResponse(BaseModel):
    case_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]