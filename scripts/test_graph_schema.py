"""
Golden schema test.

Validates that the graph API response schema is structurally
compatible with the criminal-network-visualizer's NetworkData
TypeScript interface.

Usage:
    python scripts/test_graph_schema.py
"""

import json
import sys
from pathlib import Path


# Required top-level keys in NetworkData
REQUIRED_TOP_LEVEL = {"meta", "nodes", "edges", "hiddenLinks"}

# Required fields in CaseMeta
REQUIRED_META_FIELDS = {
    "caseId", "firNumber", "title", "policeStation",
    "district", "sections", "agency", "status",
    "registeredOn", "victim", "arrests", "classification",
}

# Required fields in GraphNode
REQUIRED_NODE_FIELDS = {"id", "type", "label", "risk", "cluster"}

# Valid node types
VALID_NODE_TYPES = {
    "person", "organisation", "phone",
    "vehicle", "account", "location",
}

# Valid edge types
VALID_EDGE_TYPES = {
    "call", "financial", "ownership", "association",
    "kinship", "employment", "location", "evidence",
}

# Valid risk levels
VALID_RISK_LEVELS = {
    "critical", "high", "medium", "low", "none",
}

# Valid clusters
VALID_CLUSTERS = {
    "execution", "financial", "corporate-political",
    "victim-witness", "infrastructure",
}

# Required fields in GraphEdge
REQUIRED_EDGE_FIELDS = {
    "id", "source", "target", "type",
    "label", "weight", "confidence",
}

# Valid person roles
VALID_PERSON_ROLES = {"suspect", "victim", "witness"}


def validate_schema(data: dict) -> list[str]:
    """Return a list of error messages. Empty = valid."""

    errors: list[str] = []

    # Top-level structure
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    if errors:
        return errors

    # Meta
    meta = data["meta"]
    if not isinstance(meta, dict):
        errors.append("'meta' must be an object")
    else:
        for field in REQUIRED_META_FIELDS:
            if field not in meta:
                errors.append(f"Missing meta field: {field}")

    # Nodes
    nodes = data["nodes"]
    if not isinstance(nodes, list):
        errors.append("'nodes' must be an array")
    else:
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"nodes[{i}]: must be an object")
                continue

            for field in REQUIRED_NODE_FIELDS:
                if field not in node:
                    errors.append(
                        f"nodes[{i}] (id={node.get('id', '?')}): "
                        f"missing field '{field}'"
                    )

            node_type = node.get("type")
            if node_type not in VALID_NODE_TYPES:
                errors.append(
                    f"nodes[{i}] (id={node.get('id', '?')}): "
                    f"invalid type '{node_type}'. "
                    f"Must be one of {VALID_NODE_TYPES}"
                )

            risk = node.get("risk")
            if risk not in VALID_RISK_LEVELS:
                errors.append(
                    f"nodes[{i}] (id={node.get('id', '?')}): "
                    f"invalid risk '{risk}'. "
                    f"Must be one of {VALID_RISK_LEVELS}"
                )

            cluster = node.get("cluster")
            if cluster not in VALID_CLUSTERS:
                errors.append(
                    f"nodes[{i}] (id={node.get('id', '?')}): "
                    f"invalid cluster '{cluster}'. "
                    f"Must be one of {VALID_CLUSTERS}"
                )

            # Person-specific validation
            if node_type == "person":
                person_role = node.get("personRole")
                if (
                    person_role is not None
                    and person_role not in VALID_PERSON_ROLES
                ):
                    errors.append(
                        f"nodes[{i}] (id={node.get('id', '?')}): "
                        f"invalid personRole '{person_role}'"
                    )

            # Metrics validation
            metrics = node.get("metrics")
            if metrics is not None:
                if not isinstance(metrics, dict):
                    errors.append(
                        f"nodes[{i}] (id={node.get('id', '?')}): "
                        f"metrics must be an object"
                    )
                else:
                    for mf in ["degreeCentrality", "betweennessCentrality", "threatScore"]:
                        if mf not in metrics:
                            errors.append(
                                f"nodes[{i}] (id={node.get('id', '?')}): "
                                f"metrics missing '{mf}'"
                            )

    # Edges
    edges = data["edges"]
    if not isinstance(edges, list):
        errors.append("'edges' must be an array")
    else:
        node_ids = {n.get("id") for n in nodes}

        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(f"edges[{i}]: must be an object")
                continue

            for field in REQUIRED_EDGE_FIELDS:
                if field not in edge:
                    errors.append(
                        f"edges[{i}] (id={edge.get('id', '?')}): "
                        f"missing field '{field}'"
                    )

            edge_type = edge.get("type")
            if edge_type not in VALID_EDGE_TYPES:
                errors.append(
                    f"edges[{i}] (id={edge.get('id', '?')}): "
                    f"invalid type '{edge_type}'. "
                    f"Must be one of {VALID_EDGE_TYPES}"
                )

            # Endpoints must be string IDs, not objects
            for endpoint in ("source", "target"):
                val = edge.get(endpoint)
                if isinstance(val, dict):
                    errors.append(
                        f"edges[{i}] (id={edge.get('id', '?')}): "
                        f"'{endpoint}' must be a string ID, not an object"
                    )

            # Weight range (1-10)
            weight = edge.get("weight")
            if weight is not None:
                if not (0 <= weight <= 11):
                    errors.append(
                        f"edges[{i}] (id={edge.get('id', '?')}): "
                        f"weight {weight} outside expected range [0, 10]"
                    )

    # HiddenLinks
    hidden = data["hiddenLinks"]
    if not isinstance(hidden, list):
        errors.append("'hiddenLinks' must be an array")

    return errors


def main():
    """
    Validate the sample data file against the schema.
    """

    sample_path = (
        Path(__file__).parent.parent
        / "criminal-network-visualizer(4)"
        / "data"
        / "netra-network.json"
    )

    if not sample_path.exists():
        print(f"✗ Sample data not found: {sample_path}")
        sys.exit(1)

    with open(sample_path) as f:
        data = json.load(f)

    errors = validate_schema(data)

    if errors:
        print(f"✗ Schema validation FAILED ({len(errors)} errors):\n")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    else:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        hidden = data.get("hiddenLinks", [])

        print(f"✓ Schema validation PASSED")
        print(f"  Nodes: {len(nodes)}")
        print(f"  Edges: {len(edges)}")
        print(f"  Hidden links: {len(hidden)}")
        print(f"  Node types: {set(n['type'] for n in nodes)}")
        print(f"  Edge types: {set(e['type'] for e in edges)}")

    sys.exit(0)


if __name__ == "__main__":
    main()
