from app.services.llm.factory import get_llm_service


narrative = """
Today on 15/05/2025 at around 5:30 pm, when I was returning
from Fergusson College towards my home on my Pulsar Bike
(MH 12 AB 1234), near Vaibhav Restaurant, 4 persons on two
bikes blocked my way. The accused Rakesh @ Raka threatened me
with a knife and demanded money. When I refused, they abused me,
hurt me on my hand and took my bike, mobile, cash and watch and
ran away. I had never seen them before.
"""

known_persons = [
    "Rohit Anil Deshmukh",
    "Rakesh @ Raka",
    "Mangesh",
]

llm = get_llm_service()

result = llm.analyze_incident(
    narrative=narrative,
    known_persons=known_persons,
)

print("\nSUMMARY")
print(result.summary)

print("\nKEY POINTS")

for point in result.key_points:
    print("-", point)

print("\nMODUS OPERANDI")

for item in result.modus_operandi:
    print("-", item)

print("\nRELATIONSHIPS")

for relationship in result.relationships:
    print(
        relationship.subject,
        "→",
        relationship.predicate,
        "→",
        relationship.object,
    )

    print(
        "Evidence:",
        relationship.evidence,
    )