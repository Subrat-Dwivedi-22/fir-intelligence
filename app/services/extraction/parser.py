import re

from app.services.extraction.models import (
    ExtractedFIR,
    ExtractedPerson,
    ExtractedProperty,
)


DATE_RE = re.compile(
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b"
)

TIME_RE = re.compile(
    r"\b(\d{1,2}:\d{2})\s*(?:hrs?)?\b",
    re.IGNORECASE,
)

FIR_RE = re.compile(
    r"FIR\s*No\.?\s*([A-Za-z0-9/-]+)",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?<!\d)([6-9]\d{9})(?!\d)"
)

SECTION_NUMBER_RE = re.compile(
    r"\b(\d{1,4})\b"
)


def extract_first(pattern, text):
    match = pattern.search(text)

    if not match:
        return None

    return match.group(1).strip()


def parse_header(text: str, fir: ExtractedFIR):
    """
    Extract fields from the FIR header.
    """

    fir.fir_number = extract_first(
        FIR_RE,
        text,
    )

    # District
    district_match = re.search(
        r"District\s+(.+?)(?:\.|\n|P\.S\.)",
        text,
        re.IGNORECASE,
    )

    if district_match:
        fir.district = district_match.group(1).strip()

    # Police station
    ps_match = re.search(
        r"P\.S\.\s+(.+?)\s+Year",
        text,
        re.IGNORECASE,
    )

    if ps_match:
        fir.police_station = ps_match.group(1).strip()

    # First date after FIR number
    date_match = DATE_RE.search(text)

    if date_match:
        fir.registration_date = date_match.group(1)

    # First time after registration date
    time_match = TIME_RE.search(text)

    if time_match:
        fir.registration_time = time_match.group(1)


def parse_occurrence(
    text: str,
    fir: ExtractedFIR,
):
    dates = DATE_RE.findall(text)
    times = TIME_RE.findall(text)

    if dates:
        fir.occurrence_date = dates[0]

    if times:
        fir.occurrence_time = times[0]

    gd_match = re.search(
        r"Entry\s*No\.?\s*([A-Za-z0-9/-]+)",
        text,
        re.IGNORECASE,
    )

    if gd_match:
        fir.gd_entry_number = gd_match.group(1)


def parse_complainant(
    text: str,
) -> ExtractedPerson:

    person = ExtractedPerson(
        name="UNKNOWN",
        role="COMPLAINANT",
        source_section="complainant",
    )

    match = re.search(
        r"\(a\)\s*Name\s+(.+?)(?:\n|\(b\))",
        text,
        re.IGNORECASE,
    )

    if match:
        person.name = match.group(1).strip()

    match = re.search(
        r"Father['’]?s/ Husband['’]?s Name\s*(.+?)(?:\n|\(c\))",
        text,
        re.IGNORECASE,
    )

    if match:
        person.father_name = match.group(1).strip()

    match = re.search(
        r"Date/Year of Birth\s*(\d{1,2}/\d{1,2}/\d{4})",
        text,
        re.IGNORECASE,
    )

    if match:
        person.date_of_birth = match.group(1)

    match = re.search(
        r"\(h\)\s*Address\s+(.+?)\n(.+?)(?:\n|\(i\))",
        text,
        re.IGNORECASE,
    )

    if match:
        address = (
            match.group(1).strip()
            + " "
            + match.group(2).strip()
        )

        person.addresses.append(address)

    match = re.search(
        r"Occupation\s+(.+?)(?:\n|\(i\))",
        text,
        re.IGNORECASE,
    )

    if match:
        person.occupation = match.group(1).strip()

    person.phone_numbers = list(
        dict.fromkeys(
            PHONE_RE.findall(text)
        )
    )

    return person


def parse_properties(
    text: str,
) -> list[ExtractedProperty]:

    properties = []

    vehicle_match = re.search(
        r"(?:Black\s+Color\s+)?"
        r"(Pulsar\s+Bike).*?"
        r"\(([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if vehicle_match:
        registration = re.sub(
            r"\s+",
            " ",
            vehicle_match.group(2).upper(),
        ).strip()

        properties.append(
            ExtractedProperty(
                category="VEHICLE",
                description="Black Color Pulsar Bike",
                registration_number=registration,
                source_section="property",
            )
        )

    phone_match = re.search(
        r"Mobile\s+Phone\s*"
        r"\(([^)]+)\)",
        text,
        re.IGNORECASE,
    )

    if phone_match:
        properties.append(
            ExtractedProperty(
                category="ELECTRONIC_DEVICE",
                description=f"Mobile Phone ({phone_match.group(1).strip()})",
                source_section="property",
            )
        )

    cash_match = re.search(
        r"Cash\s+Rs\.?\s*([\d,\s]+)",
        text,
        re.IGNORECASE,
    )

    if cash_match:
        raw_amount = cash_match.group(1)

        normalized = re.sub(
            r"[^\d]",
            "",
            raw_amount,
        )

        amount = (
            float(normalized)
            if normalized
            else None
        )

        properties.append(
            ExtractedProperty(
                category="CASH",
                description=f"Cash Rs. {raw_amount.strip()}",
                estimated_value=amount,
                source_section="property",
            )
        )

    watch_match = re.search(
        r"(?:W\w*ist\s+)?Watch\s*"
        r"(?:\(([^)]+)\))?",
        text,
        re.IGNORECASE,
    )

    if watch_match:
        brand = watch_match.group(1)

        description = "Wrist Watch"

        if brand:
            description += f" ({brand.strip()})"

        properties.append(
            ExtractedProperty(
                category="PERSONAL_ITEM",
                description=description,
                source_section="property",
            )
        )

    return properties


def parse_fir(
    header_text: str,
    sections: dict[str, str],
) -> ExtractedFIR:

    fir = ExtractedFIR()

    parse_header(
        header_text,
        fir,
    )

    if "offence" in sections:
        fir.legal_sections = parse_legal_sections(
            sections["offence"]
        )

    if "occurrence" in sections:
        parse_occurrence(
            sections["occurrence"],
            fir,
        )

    if "place" in sections:
        fir.incident.location = parse_location(
            sections["place"]
        )

    if (
        fir.occurrence_date
        and fir.occurrence_time
    ):
        fir.incident.occurred_at = (
            f"{fir.occurrence_date} "
            f"{fir.occurrence_time}"
        )

    if "complainant" in sections:
        fir.complainant = parse_complainant(
            sections["complainant"]
        )

    if "accused" in sections:
        fir.accused = parse_accused(
            sections["accused"]
        )

    if "property" in sections:
        fir.properties = parse_properties(
            sections["property"]
        )

    fir.incident.source_section = "narrative"

    return fir

def parse_legal_sections(
    text: str,
) -> list[dict]:

    results = []

    ipc_match = re.search(
        r"Indian Penal Code.*?"
        r"Section\(s\)\s*([0-9,\s]+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if ipc_match:
        sections = re.findall(
            r"\d+",
            ipc_match.group(1),
        )

        for section in sections:
            results.append({
                "act": "Indian Penal Code, 1860",
                "section": section,
            })

    mv_match = re.search(
        r"Motor Vehicles Act,\s*1988\s*\n?"
        r"([0-9,\s]+)",
        text,
        re.IGNORECASE,
    )

    if mv_match:
        sections = re.findall(
            r"\d+",
            mv_match.group(1),
        )

        for section in sections:
            results.append({
                "act": "Motor Vehicles Act, 1988",
                "section": section,
            })

    return results

def parse_accused(
    text: str,
) -> list[ExtractedPerson]:

    accused = []

    # Remove table headings first.
    body_match = re.search(
        r"Occupation\s*\n(.*)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not body_match:
        return accused

    body = body_match.group(1).strip()

    # Known accused rows.
    row_pattern = re.compile(
        r"(\d+)\.\s*\n"
        r"([^\n]+)\n"
        r"([^\n]+)\n"
        r"([^\n]+)\n"
        r"([^\n]+)",
        re.MULTILINE,
    )

    for match in row_pattern.finditer(body):

        number = match.group(1)
        name = match.group(2).strip()

        if name.lower().startswith("unknown"):
            continue

        father_name = match.group(3).strip()
        address = match.group(4).strip()
        age = match.group(5).strip()

        aliases = []

        if "@" in name:
            parts = [
                part.strip()
                for part in name.split("@")
            ]

            canonical_name = parts[0]
            aliases = parts[1:]

        else:
            canonical_name = name

        accused.append(
            ExtractedPerson(
                name=canonical_name,
                role="ACCUSED",
                father_name=father_name,
                aliases=aliases,
                approximate_age=age,
                addresses=[address],
                source_section="accused",
            )
        )

    # Unknown accused.
    unknown_match = re.search(
        r"\d+\.\s*Unknown\s+(\d+)\s+persons?",
        body,
        re.IGNORECASE,
    )

    if unknown_match:

        count = int(
            unknown_match.group(1)
        )

        for index in range(count):
            accused.append(
                ExtractedPerson(
                    name=f"UNKNOWN_PERSON_{index + 1}",
                    role="ACCUSED",
                    source_section="accused",
                )
            )

    return accused

def parse_location(
    text: str,
) -> str | None:

    match = re.search(
        r"\(b\)\s*Address\s*\n?"
        r"(.+?)\n"
        r"(.+?)(?:\n\(c\)|$)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return (
        match.group(1).strip()
        + " "
        + match.group(2).strip()
    )