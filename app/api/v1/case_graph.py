"""
Graph API endpoint.

Produces a ``NetworkData``-compatible JSON response that the
criminal-network-visualizer can consume directly.

Reference:
    criminal-network-visualizer(4)/lib/netra/types.ts
    criminal-network-visualizer(4)/data/netra-network.json
"""

from collections import defaultdict
from math import log

from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.api.serialization import serialize_mongo
from app.schemas.graph import CaseGraphResponse


router = APIRouter(
    prefix="/cases",
    tags=["Case Graph"],
)


# ============================================================
# EDGE TYPE MAPPING
#
# Backend predicates → visualizer edge categories.
# ============================================================

_EDGE_TYPE_MAP: dict[str, str] = {
    # Call / communication
    "CALLED": "call",
    "CONTACTED": "call",

    # Financial
    "TRANSFERRED_FUNDS_TO": "financial",
    "RECEIVED_FUNDS_FROM": "financial",
    "PAID": "financial",
    "WITHDREW_FROM": "financial",

    # Ownership / control
    "OWNS": "ownership",
    "CONTROLS": "ownership",
    "BENEFICIAL_OWNER_OF": "ownership",
    "HAS_PHONE": "ownership",
    "HAS_ACCOUNT": "ownership",
    "HAS_VEHICLE": "ownership",
    "REGISTERED_TO": "ownership",

    # Association
    "ASSOCIATED_WITH": "association",
    "COLLUDED_WITH": "association",
    "ARRANGED_MEETING_WITH": "association",
    "INTRODUCED_TO": "association",
    "THREATENED": "association",
    "DELIVERED_TO": "association",
    "FOLLOWED": "association",

    # Kinship
    "SPOUSE": "kinship",
    "SIBLING": "kinship",
    "PARENT": "kinship",
    "CHILD": "kinship",
    "FAMILY": "kinship",

    # Employment
    "WORKS_FOR": "employment",
    "OPERATES": "employment",

    # Location / spatial
    "LOCATED_AT": "location",
    "OCCURRED_AT": "location",
    "LOCATED_WITH": "location",

    # Evidence links
    "POSSESSED": "evidence",
    "USED": "evidence",
    "WITNESS_TO": "evidence",
    "PARTICIPATED_IN": "evidence",
}


def _map_edge_type(backend_type: str) -> str:
    """Map a backend predicate to a visualizer edge category."""
    return _EDGE_TYPE_MAP.get(
        backend_type.strip().upper(),
        "association",
    )


# ============================================================
# ENTITY TYPE MAPPING
# ============================================================

_ENTITY_TYPE_MAP: dict[str, str] = {
    "ORGANIZATION": "organisation",
    "ORGANISATION": "organisation",
    "LOCATION": "location",
    "VEHICLE": "vehicle",
    "PHONE": "phone",
    "ACCOUNT": "account",
    "PROPERTY": "location",
    "WEAPON": "location",
    "OTHER": "location",
}


def _map_entity_type(backend_type: str) -> str:
    """Map a backend entity type to a visualizer node type."""
    return _ENTITY_TYPE_MAP.get(
        backend_type.strip().upper(),
        "location",
    )


# ============================================================
# RISK COMPUTATION
# ============================================================

_ROLE_RISK: dict[str, str] = {
    "ACCUSED": "high",
    "SUSPECT": "high",
    "KEY_OPERATOR": "critical",
    "COMPLAINANT": "none",
    "INFORMANT": "none",
    "VICTIM": "none",
    "WITNESS": "none",
    "OFFICER": "low",
    "OTHER": "medium",
    "UNKNOWN": "medium",
}


def _compute_person_risk(
    roles: list[str],
    degree: int,
) -> str:
    """Deterministic risk from role + connectivity."""

    best = "none"
    risk_order = ["none", "low", "medium", "high", "critical"]

    for role in roles:
        r = _ROLE_RISK.get(
            role.strip().upper(),
            "medium",
        )
        if risk_order.index(r) > risk_order.index(best):
            best = r

    # High-degree accused → critical
    if best == "high" and degree >= 4:
        best = "critical"

    return best


def _compute_entity_risk(
    entity_type: str,
    degree: int,
) -> str:
    """Risk for non-person entities based on connectivity."""
    if degree >= 5:
        return "critical"
    if degree >= 3:
        return "high"
    if degree >= 1:
        return "medium"
    return "low"


# ============================================================
# CLUSTER COMPUTATION
# ============================================================


def _compute_person_cluster(
    roles: list[str],
    connected_types: set[str],
) -> str:
    """Simple heuristic cluster assignment."""

    role_set = {
        r.strip().upper() for r in roles
    }

    if role_set & {"VICTIM", "WITNESS", "COMPLAINANT", "INFORMANT"}:
        return "victim-witness"

    # If connected to financial entities, → financial
    if connected_types & {"ACCOUNT"}:
        return "financial"

    if connected_types & {"ORGANIZATION", "ORGANISATION"}:
        return "corporate-political"

    if role_set & {"ACCUSED", "SUSPECT", "KEY_OPERATOR"}:
        return "execution"

    return "infrastructure"


def _compute_entity_cluster(
    entity_type: str,
) -> str:
    """Cluster for non-person entities."""
    mapping = {
        "ACCOUNT": "financial",
        "PHONE": "infrastructure",
        "VEHICLE": "execution",
        "ORGANIZATION": "corporate-political",
        "ORGANISATION": "corporate-political",
        "LOCATION": "infrastructure",
    }
    return mapping.get(
        entity_type.strip().upper(),
        "infrastructure",
    )


# ============================================================
# PERSON ROLE MAPPING
# ============================================================


def _map_person_role(roles: list[str]) -> str | None:
    """Map backend roles to visualizer PersonRole."""
    role_set = {
        r.strip().upper() for r in roles
    }

    if role_set & {"VICTIM"}:
        return "victim"
    if role_set & {"WITNESS", "COMPLAINANT", "INFORMANT"}:
        return "witness"
    if role_set & {"ACCUSED", "SUSPECT", "KEY_OPERATOR", "UNKNOWN"}:
        return "suspect"
    return "suspect"


# ============================================================
# GRAPH METRICS
# ============================================================


def _compute_graph_metrics(
    node_ids: set[str],
    adjacency: dict[str, list[str]],
    role_weights: dict[str, float],
) -> dict[str, dict]:
    """
    Compute degree centrality, betweenness centrality, and
    a deterministic threat score for each node.

    The threat score is a composite of:
    - Normalized degree centrality (0-1) × 40
    - Normalized betweenness centrality (0-1) × 40
    - Role weight × 20
    """

    n = len(node_ids)
    if n <= 1:
        return {
            nid: {
                "degreeCentrality": 0.0,
                "betweennessCentrality": 0.0,
                "threatScore": 0.0,
            }
            for nid in node_ids
        }

    # Degree centrality
    degrees: dict[str, int] = {}
    for nid in node_ids:
        degrees[nid] = len(adjacency.get(nid, []))

    max_degree = max(degrees.values()) if degrees else 1
    degree_centrality = {
        nid: degrees[nid] / max(max_degree, 1)
        for nid in node_ids
    }

    # Betweenness centrality (approximate via BFS from each node)
    betweenness: dict[str, float] = {
        nid: 0.0 for nid in node_ids
    }

    node_list = list(node_ids)

    # Only compute for graphs up to 500 nodes to avoid perf issues.
    if n <= 500:
        for source in node_list:
            # BFS
            dist: dict[str, int] = {source: 0}
            paths: dict[str, float] = {source: 1.0}
            queue = [source]
            stack = []
            predecessors: dict[str, list[str]] = defaultdict(list)

            head = 0
            while head < len(queue):
                v = queue[head]
                head += 1
                stack.append(v)

                for w in adjacency.get(v, []):
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)

                    if dist.get(w) == dist[v] + 1:
                        paths[w] = paths.get(w, 0.0) + paths[v]
                        predecessors[w].append(v)

            delta: dict[str, float] = {
                nid: 0.0 for nid in node_ids
            }

            while stack:
                w = stack.pop()
                for v in predecessors.get(w, []):
                    ratio = paths.get(v, 1.0) / max(paths.get(w, 1.0), 1e-10)
                    delta[v] = delta.get(v, 0.0) + ratio * (1.0 + delta.get(w, 0.0))

                if w != source:
                    betweenness[w] = betweenness.get(w, 0.0) + delta.get(w, 0.0)

    # Normalize betweenness
    max_betweenness = max(betweenness.values()) if betweenness else 1.0
    max_betweenness = max(max_betweenness, 1e-10)

    betweenness_centrality = {
        nid: betweenness[nid] / max_betweenness
        for nid in node_ids
    }

    # Threat score
    result: dict[str, dict] = {}

    for nid in node_ids:
        dc = degree_centrality.get(nid, 0.0)
        bc = betweenness_centrality.get(nid, 0.0)
        rw = role_weights.get(nid, 0.5)

        threat = round(
            dc * 40 + bc * 40 + rw * 20
        )
        threat = max(0, min(100, threat))

        result[nid] = {
            "degreeCentrality": round(dc, 2),
            "betweennessCentrality": round(bc, 2),
            "threatScore": threat,
        }

    return result


# ============================================================
# MAIN ENDPOINT
# ============================================================


@router.get(
    "/{case_id}/graph",
    response_model=CaseGraphResponse,
)
def get_case_graph(case_id: str):

    # ==========================================
    # CASE
    # ==========================================

    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 0},
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    # ==========================================
    # GATHER RAW DATA
    # ==========================================

    persons = list(
        db.case_persons.aggregate([
            {
                "$match": {
                    "case_id": case_id,
                }
            },
            {
                "$lookup": {
                    "from": "persons",
                    "localField": "person_id",
                    "foreignField": "person_id",
                    "as": "person",
                }
            },
            {
                "$unwind": "$person",
            },
            {
                "$project": {
                    "_id": 0,
                    "person_id": "$person.person_id",
                    "name": "$person.identity.name",
                    "aliases": "$person.identity.aliases",
                    "father_name": "$person.identity.father_name",
                    "approximate_age": "$person.identity.approximate_age",
                    "gender": "$person.identity.gender",
                    "phones": "$person.contact.phones",
                    "emails": "$person.contact.emails",
                    "addresses": "$person.addresses",
                    "occupation": "$person.occupation",
                    "roles": 1,
                    "extraction_confidence": "$person.extraction_confidence",
                }
            },
        ])
    )

    unknowns = list(
        db.unknown_identities.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    entities = list(
        db.entities.find(
            {"case_ids": case_id},
            {"_id": 0},
        )
    )

    relationships = list(
        db.relationships.find(
            {"context.case_id": case_id},
            {"_id": 0},
        )
    )

    hidden_link_findings = list(
        db.hidden_link_findings.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    # ==========================================
    # BUILD NODE INDEX
    # ==========================================

    all_node_ids: set[str] = set()
    node_roles: dict[str, list[str]] = {}

    # Person nodes
    person_index: dict[str, dict] = {}
    for person in persons:
        pid = person["person_id"]
        person_index[pid] = person
        all_node_ids.add(pid)
        node_roles[pid] = person.get("roles", [])

    # Unknown nodes → treated as person/suspect
    unknown_index: dict[str, dict] = {}
    for unknown in unknowns:
        uid = unknown["unknown_id"]
        unknown_index[uid] = unknown
        all_node_ids.add(uid)
        node_roles[uid] = unknown.get("roles", ["UNKNOWN"])

    # Entity nodes
    entity_index: dict[str, dict] = {}
    for entity in entities:
        eid = entity["entity_id"]
        entity_index[eid] = entity
        all_node_ids.add(eid)

    # ==========================================
    # BUILD ADJACENCY + GATHER EDGE DATA
    # ==========================================

    adjacency: dict[str, list[str]] = defaultdict(list)
    connected_entity_types: dict[str, set[str]] = defaultdict(set)

    for rel in relationships:
        from_id = rel["from"]["id"]
        to_id = rel["to"]["id"]

        adjacency[from_id].append(to_id)
        adjacency[to_id].append(from_id)

        # Track what entity types each node connects to
        from_type = rel["from"]["type"]
        to_type = rel["to"]["type"]
        connected_entity_types[from_id].add(to_type)
        connected_entity_types[to_id].add(from_type)

    # ==========================================
    # COMPUTE METRICS
    # ==========================================

    # Role weights for threat score
    _ROLE_WEIGHT: dict[str, float] = {
        "ACCUSED": 0.9,
        "SUSPECT": 0.9,
        "KEY_OPERATOR": 1.0,
        "UNKNOWN": 0.6,
        "OTHER": 0.5,
        "WITNESS": 0.1,
        "COMPLAINANT": 0.05,
        "INFORMANT": 0.05,
        "VICTIM": 0.0,
        "OFFICER": 0.2,
    }

    role_weights: dict[str, float] = {}
    for nid in all_node_ids:
        roles = node_roles.get(nid, [])
        if roles:
            best = max(
                _ROLE_WEIGHT.get(r.strip().upper(), 0.5)
                for r in roles
            )
            role_weights[nid] = best
        elif nid in entity_index:
            # Non-person entities get moderate weight
            et = entity_index[nid].get("type", "").upper()
            if et == "ACCOUNT":
                role_weights[nid] = 0.7
            elif et == "PHONE":
                role_weights[nid] = 0.5
            elif et in {"ORGANIZATION", "ORGANISATION"}:
                role_weights[nid] = 0.6
            else:
                role_weights[nid] = 0.3
        else:
            role_weights[nid] = 0.5

    metrics = _compute_graph_metrics(
        node_ids=all_node_ids,
        adjacency=dict(adjacency),
        role_weights=role_weights,
    )

    # ==========================================
    # BUILD GRAPH NODES
    # ==========================================

    nodes = []

    # ------------------------------------------
    # PERSON NODES
    # ------------------------------------------

    for person in persons:
        pid = person["person_id"]
        roles = person.get("roles", [])
        degree = len(adjacency.get(pid, []))

        # Build contact string
        phones = person.get("phones", [])
        contact = phones[0] if phones else None

        # Age
        age_str = person.get("approximate_age")
        age = None
        if age_str:
            try:
                age = int(str(age_str).strip().split()[0])
            except (ValueError, IndexError):
                pass

        # Address
        addresses = person.get("addresses", [])
        address = addresses[0] if addresses else None

        # Aliases
        aliases = person.get("aliases", [])
        alias = aliases[0] if aliases else None

        node = {
            "id": pid,
            "type": "person",
            "label": person.get("name") or "Unknown Person",
            "name": person.get("name"),
            "alias": alias,
            "age": age,
            "gender": person.get("gender"),
            "contact": contact,
            "occupation": person.get("occupation"),
            "address": address,
            "personRole": _map_person_role(roles),
            "risk": _compute_person_risk(roles, degree),
            "cluster": _compute_person_cluster(
                roles,
                connected_entity_types.get(pid, set()),
            ),
            "status": None,
            "metrics": metrics.get(pid),
            "confidence": person.get("extraction_confidence"),
        }

        nodes.append(node)

    # ------------------------------------------
    # UNKNOWN IDENTITY NODES → person/suspect
    # ------------------------------------------

    for unknown in unknowns:
        uid = unknown["unknown_id"]
        degree = len(adjacency.get(uid, []))

        node = {
            "id": uid,
            "type": "person",
            "label": unknown.get("label") or uid,
            "name": unknown.get("label"),
            "personRole": "suspect",
            "risk": "medium",
            "cluster": "execution",
            "metrics": metrics.get(uid),
        }

        nodes.append(node)

    # ------------------------------------------
    # ENTITY NODES
    # ------------------------------------------

    for entity in entities:
        eid = entity["entity_id"]
        entity_type = entity.get("type", "OTHER")
        degree = len(adjacency.get(eid, []))
        viz_type = _map_entity_type(entity_type)
        metadata = entity.get("metadata", {})

        node = {
            "id": eid,
            "type": viz_type,
            "label": entity.get("value") or entity_type,
            "risk": _compute_entity_risk(entity_type, degree),
            "cluster": _compute_entity_cluster(entity_type),
            "metrics": metrics.get(eid),
        }

        # Build attributes from metadata
        attrs = []
        if metadata:
            for key, val in metadata.items():
                if val is not None and str(val).strip():
                    attrs.append({
                        "label": key.replace("_", " ").title(),
                        "value": str(val),
                        "mono": key in {
                            "registration_number",
                            "account_number",
                            "phone_number",
                            "number",
                            "imei",
                        },
                    })

        if attrs:
            node["attributes"] = attrs

        # caseRole from first relationship evidence
        for rel in relationships:
            if (
                rel["from"]["id"] == eid
                or rel["to"]["id"] == eid
            ):
                evidence = rel.get("evidence")
                if evidence:
                    node["caseRole"] = evidence
                    break

        nodes.append(node)

    # ==========================================
    # BUILD GRAPH EDGES
    # ==========================================

    edges = []

    for rel in relationships:
        from_id = rel["from"]["id"]
        to_id = rel["to"]["id"]
        backend_type = rel.get("type", "ASSOCIATED_WITH")
        viz_edge_type = _map_edge_type(backend_type)
        metadata = rel.get("metadata", {})

        # Determine label
        label = backend_type.replace("_", " ").title()

        # Override label for specific metadata
        if metadata.get("call_count"):
            count = metadata["call_count"]
            label = f"{count} calls" if count > 1 else "1 call"

        if metadata.get("amount"):
            amount = metadata["amount"]
            if amount >= 10_000_000:
                label = f"Rs. {amount / 10_000_000:.2f} Cr"
            elif amount >= 100_000:
                label = f"Rs. {amount / 100_000:.2f} L"
            else:
                label = f"Rs. {amount:,.0f}"

        edge = {
            "id": rel.get("relationship_id", f"{from_id}-{to_id}"),
            "source": from_id,
            "target": to_id,
            "type": viz_edge_type,
            "label": label,
            "weight": rel.get("weight", 5),
            "confidence": rel.get("confidence", 0.0) or 0.0,
            "basis": rel.get("evidence"),
            "date": metadata.get("date") or rel.get("date"),
            "directed": viz_edge_type in {
                "financial", "ownership", "employment",
            },
        }

        # Financial metadata
        if metadata.get("amount"):
            edge["amount"] = metadata["amount"]

        # Call metadata
        if metadata.get("call_count"):
            edge["callCount"] = metadata["call_count"]

        # Hidden links (inferred, low confidence)
        derivation = rel.get("derivation", "DIRECT")
        if derivation == "EVENT_DERIVED":
            edge["hidden"] = True
        elif rel.get("confidence") and rel["confidence"] < 0.5:
            edge["hidden"] = True

        edges.append(edge)

    # ==========================================
    # SCALE WEIGHTS to 1-10 range
    # ==========================================

    if edges:
        raw_weights = [
            e.get("weight", 0.5) for e in edges
        ]
        min_w = min(raw_weights)
        max_w = max(raw_weights)
        span = max_w - min_w if max_w > min_w else 1.0

        for edge in edges:
            raw = edge.get("weight", 0.5)
            scaled = 1 + ((raw - min_w) / span) * 9
            edge["weight"] = round(scaled, 1)

    # ==========================================
    # BUILD META
    # ==========================================

    # Try to get extraction data for FIR metadata
    extraction = db.extractions.find_one(
        {"case_id": case_id},
        {"_id": 0},
    )

    meta = {
        "caseId": case_id,
        "firNumber": "",
        "title": case.get("title", ""),
        "policeStation": "",
        "district": "",
        "sections": [],
        "agency": "",
        "status": case.get("status", ""),
        "registeredOn": "",
        "victim": "",
        "arrests": 0,
        "classification": "",
    }

    if extraction:
        meta["firNumber"] = extraction.get(
            "fir_number", ""
        ) or ""
        meta["policeStation"] = extraction.get(
            "police_station", ""
        ) or ""
        meta["district"] = extraction.get(
            "district", ""
        ) or ""
        meta["sections"] = extraction.get(
            "legal_sections", []
        ) or []
        meta["registeredOn"] = extraction.get(
            "registration_date", ""
        ) or ""

    # Count arrests (accused persons)
    meta["arrests"] = sum(
        1 for p in persons
        if "ACCUSED" in {
            r.strip().upper()
            for r in p.get("roles", [])
        }
    )

    # ==========================================
    # BUILD HIDDEN LINK FINDINGS
    # ==========================================

    hidden_links = []

    for finding in hidden_link_findings:

        hidden_entity_ids = [
            entity.get("id")
            for entity in finding.get("entities", [])
            if entity.get("id")
        ]

        hidden_edge_ids = [
            edge.get("relationship_id")
            for edge in finding.get("edges", [])
            if edge.get("relationship_id")
        ]

        hidden_links.append({
            "id": finding.get("hidden_link_id"),
            "title": finding.get("title"),
            "entities": hidden_entity_ids,
            "edges": hidden_edge_ids,
            "confidence": finding.get("confidence"),
            "rationale": finding.get("rationale"),
            "severity": finding.get("severity"),
        })

    # ==========================================
    # RESPONSE
    # ==========================================

    return serialize_mongo({
        "meta": meta,
        "nodes": nodes,
        "edges": edges,
        "hiddenLinks": hidden_links,
    })