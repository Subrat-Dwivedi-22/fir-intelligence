RELATIONSHIP_WEIGHTS = {
    # Ownership / control
    "OWNS": 1.00,
    "CONTROLS": 1.00,
    "BENEFICIAL_OWNER_OF": 0.95,
    "HAS_PHONE": 0.95,
    "HAS_ACCOUNT": 0.95,
    "HAS_VEHICLE": 0.90,
    "REGISTERED_TO": 0.90,

    # Organization
    "WORKS_FOR": 0.70,
    "OPERATES": 0.85,

    # Communication
    "CALLED": 0.85,
    "CONTACTED": 0.75,

    # Financial
    "TRANSFERRED_FUNDS_TO": 0.95,
    "RECEIVED_FUNDS_FROM": 0.95,
    "PAID": 0.95,
    "WITHDREW_FROM": 0.90,

    # Operational
    "POSSESSED": 0.90,
    "USED": 0.90,
    "DELIVERED_TO": 0.90,
    "INTRODUCED_TO": 0.70,
    "THREATENED": 0.85,
    "ARRANGED_MEETING_WITH": 0.80,
    "COLLUDED_WITH": 0.90,

    # Spatial / event
    "LOCATED_AT": 0.60,
    "OCCURRED_AT": 0.65,
    "PARTICIPATED_IN": 0.75,
    "WITNESS_TO": 0.70,
    "LOCATED_WITH": 0.55,

    # General / weak
    "ASSOCIATED_WITH": 0.40,
}


def relationship_weight(relationship_type: str) -> float:
    return RELATIONSHIP_WEIGHTS.get(
        relationship_type.strip().upper(),
        0.50,
    )