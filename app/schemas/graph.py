"""
Graph API response schemas.

These models match the criminal-network-visualizer's
TypeScript ``NetworkData`` interface exactly so that the
frontend can consume backend responses without transformation.

Reference:
    criminal-network-visualizer(4)/lib/netra/types.ts
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# Shared types (match the visualizer constants)
# ============================================================

EntityType = Literal[
    "person",
    "organisation",
    "phone",
    "vehicle",
    "account",
    "location",
]

PersonRole = Literal[
    "suspect",
    "victim",
    "witness",
]

RiskLevel = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "none",
]

Cluster = Literal[
    "execution",
    "financial",
    "corporate-political",
    "victim-witness",
    "infrastructure",
]

EdgeType = Literal[
    "call",
    "financial",
    "ownership",
    "association",
    "kinship",
    "employment",
    "location",
    "evidence",
]


# ============================================================
# Attribute rows (inspector detail lines)
# ============================================================


class AttributeRow(BaseModel):
    label: str
    value: str
    mono: bool | None = None


# ============================================================
# Graph metrics
# ============================================================


class GraphMetrics(BaseModel):
    degreeCentrality: float = 0.0
    betweennessCentrality: float = 0.0
    threatScore: float = 0.0


# ============================================================
# Graph node — matches visualizer GraphNode
# ============================================================


class GraphNode(BaseModel):
    id: str
    type: str  # EntityType
    label: str

    # ---- Person / suspect record fields --------------------
    suspectId: str | None = None
    firNumber: str | None = None
    name: str | None = None
    alias: str | None = None
    age: int | None = None
    gender: str | None = None
    contact: str | None = None
    occupation: str | None = None
    address: str | dict | None = None
    personRole: str | None = None  # PersonRole

    # ---- Case context --------------------------------------
    caseRole: str | None = None
    risk: str = "none"  # RiskLevel
    cluster: str = "infrastructure"  # Cluster
    status: str | None = None
    criminalHistory: list[str] | None = None
    sections: list[str] | None = None

    # ---- Non-person specifics ------------------------------
    attributes: list[AttributeRow] | None = None

    # ---- Analytics -----------------------------------------
    metrics: GraphMetrics | None = None

    notes: str | None = None


# ============================================================
# Graph edge — matches visualizer GraphEdge
# ============================================================


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # EdgeType
    label: str = ""
    weight: float = 5.0
    confidence: float = 0.0
    hidden: bool | None = None
    directed: bool | None = None
    date: str | None = None
    basis: str | None = None
    amount: float | None = None
    callCount: int | None = None


# ============================================================
# Hidden link finding
# ============================================================


class HiddenLinkFinding(BaseModel):
    id: str
    title: str
    entities: list[str] = Field(default_factory=list)
    edges: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""
    severity: str = "medium"


# ============================================================
# Case metadata
# ============================================================


class CaseMeta(BaseModel):
    caseId: str = ""
    firNumber: str = ""
    title: str = ""
    policeStation: str = ""
    district: str = ""
    sections: list[str] = Field(default_factory=list)
    agency: str = ""
    status: str = ""
    registeredOn: str = ""
    victim: str = ""
    arrests: int = 0
    classification: str = ""


# ============================================================
# Top-level response — matches visualizer NetworkData
# ============================================================


class CaseGraphResponse(BaseModel):
    meta: CaseMeta = Field(default_factory=CaseMeta)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    hiddenLinks: list[HiddenLinkFinding] = Field(
        default_factory=list
    )