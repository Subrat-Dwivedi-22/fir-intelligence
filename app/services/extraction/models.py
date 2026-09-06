from dataclasses import dataclass, field


@dataclass
class ExtractedPerson:
    name: str
    role: str | None = None
    confidence: float = 0.0

    father_name: str | None = None
    aliases: list[str] = field(
        default_factory=list
    )

    date_of_birth: str | None = None
    approximate_age: str | None = None

    phone_numbers: list[str] = field(
        default_factory=list
    )

    addresses: list[str] = field(
        default_factory=list
    )

    occupation: str | None = None

    source_section: str | None = None


@dataclass
class ExtractedIncident:
    occurred_at: str | None = None

    location: str | None = None

    summary: str | None = None

    key_points: list[str] = field(
        default_factory=list
    )

    modus_operandi: list[str] = field(
        default_factory=list
    )

    source_section: str | None = None


@dataclass
class ExtractedProperty:
    category: str
    description: str

    registration_number: str | None = None

    estimated_value: float | None = None

    source_section: str | None = None


@dataclass
class ExtractedFIR:
    fir_number: str | None = None

    police_station: str | None = None
    district: str | None = None

    registration_date: str | None = None
    registration_time: str | None = None

    occurrence_date: str | None = None
    occurrence_time: str | None = None

    gd_entry_number: str | None = None

    legal_sections: list[dict] = field(
        default_factory=list
    )

    complainant: ExtractedPerson | None = None

    accused: list[ExtractedPerson] = field(
        default_factory=list
    )

    incident: ExtractedIncident = field(
        default_factory=ExtractedIncident
    )

    properties: list[ExtractedProperty] = field(
        default_factory=list
    )