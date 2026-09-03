import re
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# Shared normalization helpers
# ============================================================

def normalize_string(value: Any) -> Any:
    """
    Normalize a scalar string value.

    Empty strings are converted to None.
    No information is invented.
    """

    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    return value


def normalize_string_list(value: Any) -> list[str]:
    """
    Normalize LLM-generated string collections.

    Supported input:

        None
            -> []

        "value"
            -> ["value"]

        ["value", "other"]
            -> ["value", "other"]

    This protects the application from harmless LLM
    variations such as null instead of [].
    """

    if value is None:
        return []

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        return [value]

    if isinstance(value, (list, tuple, set)):
        result: list[str] = []

        for item in value:
            if item is None:
                continue

            if isinstance(item, str):
                item = item.strip()

                if item:
                    result.append(item)
            else:
                item = str(item).strip()

                if item:
                    result.append(item)

        return result

    return [str(value).strip()]


def normalize_object_list(value: Any) -> list:
    """
    Normalize LLM-generated object collections.

    Supported input:

        None
            -> []

        {...}
            -> [{...}]

        [{...}, {...}]
            -> unchanged
    """

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        return [value]

    return []


# ============================================================
# Identifier
# ============================================================

class ExtractedIdentifier(BaseModel):
    """
    An identifier explicitly extracted from a document.

    Examples:

    FIR number
    Case number
    Complaint number
    GD/DD entry
    Account number
    Reference number
    Transaction identifier
    """

    model_config = ConfigDict(extra="ignore")

    type: str = "UNKNOWN"

    value: str

    evidence: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_identifier(cls, value):
        """
        Gemini may use semantically equivalent field names.

        Example:

            identifier_type
                -> type

        This normalization happens at the LLM boundary.
        """

        if not isinstance(value, dict):
            return value

        value = dict(value)

        if "type" not in value:
            for alias in (
                "identifier_type",
                "id_type",
                "identifierType",
                "idType",
            ):
                if alias in value:
                    value["type"] = value.pop(alias)
                    break

        if "value" not in value:
            for alias in (
                "identifier_value",
                "id_value",
                "identifierValue",
                "idValue",
            ):
                if alias in value:
                    value["value"] = value.pop(alias)
                    break

        return value

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value):
        if value is None:
            return "UNKNOWN"

        return str(value).strip().upper()

    @field_validator(
        "value",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        return normalize_string(value)


# ============================================================
# Person
# ============================================================

class ExtractedPerson(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str

    roles: list[str] = Field(
        default_factory=list
    )

    aliases: list[str] = Field(
        default_factory=list
    )

    phone_numbers: list[str] = Field(
        default_factory=list
    )

    email_addresses: list[str] = Field(
        default_factory=list
    )

    addresses: list[str] = Field(
        default_factory=list
    )

    father_or_husband_name: str | None = None

    age: str | None = None

    evidence: str | None = None

    @field_validator(
        "roles",
        "aliases",
        "phone_numbers",
        "email_addresses",
        "addresses",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value):
        return normalize_string_list(value)

    @field_validator(
        "father_or_husband_name",
        "age",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return normalize_string(value)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        value = normalize_string(value)

        if value is None:
            raise ValueError(
                "Extracted person name cannot be empty"
            )

        return value


# ============================================================
# Organization
# ============================================================

class ExtractedOrganization(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str

    organization_type: str | None = None

    aliases: list[str] = Field(
        default_factory=list
    )

    addresses: list[str] = Field(
        default_factory=list
    )

    evidence: str | None = None

    @field_validator(
        "aliases",
        "addresses",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value):
        return normalize_string_list(value)

    @field_validator(
        "organization_type",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return normalize_string(value)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        value = normalize_string(value)

        if value is None:
            raise ValueError(
                "Extracted organization name cannot be empty"
            )

        return value


# ============================================================
# Location
# ============================================================

class ExtractedLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    location_type: str | None = None
    address: str | None = None
    evidence: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_location(cls, value):
        if not isinstance(value, dict):
            return value

        value = dict(value)

        # Gemini may return the location only in `address`.
        if not value.get("name") and value.get("address"):
            value["name"] = value["address"]

        return value

    @field_validator(
        "name",
        "location_type",
        "address",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        return normalize_string(value)


# ============================================================
# Vehicle
# ============================================================

class ExtractedVehicle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    registration_number: str | None = None

    vehicle_type: str | None = None

    description: str | None = None

    evidence: str | None = None

    @field_validator(
        "registration_number",
        "vehicle_type",
        "description",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        return normalize_string(value)


# ============================================================
# Financial amount
# ============================================================

class ExtractedFinancialAmount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    amount: float | None = None

    currency: str | None = None

    original_text: str | None = None

    context: str | None = None

    evidence: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value):
        """
        Normalize common human-readable monetary values.

        Examples:

            18.5 Lakhs
                -> 1850000.0

            45 Lakhs
                -> 4500000.0

            2.5 Crores
                -> 25000000.0

            ₹18.5 Lakhs
                -> 1850000.0

            1,250,000
                -> 1250000.0

            5 million
                -> 5000000.0
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if not isinstance(value, str):
            return None

        raw = value.strip()

        if not raw:
            return None

        normalized = raw.lower().strip()

        # Currency prefixes.
        normalized = (
            normalized
            .replace("₹", "")
            .replace("rs.", "")
            .replace("rs ", "")
            .replace("inr", "")
            .strip()
        )

        # Thousands separators.
        normalized = normalized.replace(",", "")

        # Crores.
        match = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*"
            r"(?:crore|crores|cr)\b",
            normalized,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1)) * 10_000_000

        # Lakhs.
        match = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*"
            r"(?:lakh|lakhs|lac|lacs)\b",
            normalized,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1)) * 100_000

        # Millions.
        match = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*"
            r"(?:million|millions)\b",
            normalized,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1)) * 1_000_000

        # Billions.
        match = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*"
            r"(?:billion|billions)\b",
            normalized,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1)) * 1_000_000_000

        # Thousands.
        match = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*"
            r"(?:thousand|k)\b",
            normalized,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1)) * 1_000

        # Plain numeric value.
        match = re.search(
            r"[-+]?\d+(?:\.\d+)?",
            normalized,
        )

        if match:
            return float(match.group(0))

        return None

    @field_validator(
        "currency",
        "original_text",
        "context",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        return normalize_string(value)


# ============================================================
# Evidence
# ============================================================

class ExtractedEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    evidence_type: str = "OTHER"

    description: str

    quantity: str | None = None

    value: str | None = None

    evidence: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence(cls, value):
        if not isinstance(value, dict):
            return value

        value = dict(value)

        # Gemini may omit evidence_type.
        # Preserve the evidence rather than failing validation.
        if not value.get("evidence_type"):
            value["evidence_type"] = "OTHER"

        return value

    @field_validator(
        "evidence_type",
        "description",
        "quantity",
        "value",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value if value else None

        # Gemini may return numeric values such as:
        # value = 4500000
        #
        # The schema stores evidence.value as text because
        # evidence can contain arbitrary values.
        return str(value)


# ============================================================
# Incident
# ============================================================

class ExtractedIncident(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None

    description: str | None = None

    dates: list[str] = Field(
        default_factory=list
    )

    times: list[str] = Field(
        default_factory=list
    )

    locations: list[str] = Field(
        default_factory=list
    )

    crime_types: list[str] = Field(
        default_factory=list
    )

    key_points: list[str] = Field(
        default_factory=list
    )

    modus_operandi: list[str] = Field(
        default_factory=list
    )

    evidence: str | None = None

    @field_validator(
        "dates",
        "times",
        "locations",
        "crime_types",
        "key_points",
        "modus_operandi",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value):
        return normalize_string_list(value)

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value if value else None

        if isinstance(value, list):
            values = normalize_string_list(value)

            if not values:
                return None

            return "; ".join(values)

        return str(value)

    @field_validator(
        "title",
        "description",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return normalize_string(value)


# ============================================================
# Relationship
# ============================================================

class RelationshipCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str

    subject_type: str

    predicate: str

    object: str

    object_type: str

    evidence: str

    @field_validator(
        "subject",
        "subject_type",
        "predicate",
        "object",
        "object_type",
        "evidence",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value):
        return normalize_string(value)

    @field_validator(
        "subject_type",
        "object_type",
        mode="after",
    )
    @classmethod
    def normalize_entity_types(cls, value):
        if value is None:
            return value

        return value.upper()


# ============================================================
# Universal document extraction
# ============================================================

class DocumentExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: str = "UNKNOWN"

    identifiers: list[ExtractedIdentifier] = Field(
        default_factory=list
    )

    dates: list[str] = Field(
        default_factory=list
    )

    times: list[str] = Field(
        default_factory=list
    )

    phone_numbers: list[str] = Field(
        default_factory=list
    )

    email_addresses: list[str] = Field(
        default_factory=list
    )

    monetary_amounts: list[ExtractedFinancialAmount] = Field(
        default_factory=list
    )

    persons: list[ExtractedPerson] = Field(
        default_factory=list
    )

    organizations: list[ExtractedOrganization] = Field(
        default_factory=list
    )

    locations: list[ExtractedLocation] = Field(
        default_factory=list
    )

    vehicles: list[ExtractedVehicle] = Field(
        default_factory=list
    )

    evidence_items: list[ExtractedEvidence] = Field(
        default_factory=list
    )

    incidents: list[ExtractedIncident] = Field(
        default_factory=list
    )

    relationships: list[RelationshipCandidate] = Field(
        default_factory=list
    )

    summary: str | None = None

    @field_validator(
        "identifiers",
        "monetary_amounts",
        "persons",
        "organizations",
        "locations",
        "vehicles",
        "evidence_items",
        "incidents",
        "relationships",
        mode="before",
    )
    @classmethod
    def normalize_object_lists(cls, value):
        return normalize_object_list(value)

    @field_validator(
        "dates",
        "times",
        "phone_numbers",
        "email_addresses",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value):
        return normalize_string_list(value)

    @field_validator(
        "document_type",
        "summary",
        mode="before",
    )
    @classmethod
    def normalize_top_level_strings(cls, value):
        if value is None:
            return "UNKNOWN"

        return normalize_string(value)

    @field_validator("document_type", mode="after")
    @classmethod
    def normalize_document_type(cls, value):
        return value.upper()


# ============================================================
# Existing incident analysis
# ============================================================

class IncidentAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None

    key_points: list[str] = Field(
        default_factory=list
    )

    modus_operandi: list[str] = Field(
        default_factory=list
    )

    relationships: list[RelationshipCandidate] = Field(
        default_factory=list
    )

    @field_validator(
        "key_points",
        "modus_operandi",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value):
        return normalize_string_list(value)

    @field_validator(
        "relationships",
        mode="before",
    )
    @classmethod
    def normalize_relationships(cls, value):
        return normalize_object_list(value)

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value):
        return normalize_string(value)