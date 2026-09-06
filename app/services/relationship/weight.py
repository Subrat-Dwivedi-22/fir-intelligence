RELATIONSHIP_WEIGHTS = {
    "OWNS": 1.00,
    "CONTROLS": 1.00,
    "TRANSFERRED_FUNDS_TO": 0.95,
    "PAID": 0.95,
    "POSSESSED": 0.90,
    "USED": 0.90,
    "DELIVERED_TO": 0.90,
    "INTRODUCED_TO": 0.70,
    "THREATENED": 0.85,
    "ARRANGED_MEETING_WITH": 0.80,
    "COLLUDED_WITH": 0.90,
    "ASSOCIATED_WITH": 0.40,
    "LOCATED_AT": 0.60,
}


def relationship_weight(relationship_type: str) -> float:
    return RELATIONSHIP_WEIGHTS.get(
        relationship_type.strip().upper(),
        0.50,
    )
