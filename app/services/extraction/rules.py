import re


FIR_NUMBER = re.compile(
    r"FIR\s*No\.?\s*([A-Za-z0-9\/\-]+)",
    re.IGNORECASE,
)

POLICE_STATION = re.compile(
    r"P\.S\.\s+(.+?)\s+Year",
    re.IGNORECASE,
)

DISTRICT = re.compile(
    r"District\s+(.+?)(?:\n|P\.S\.)",
    re.IGNORECASE,
)

PHONE = re.compile(
    r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)"
)

VEHICLE_REGISTRATION = re.compile(
    r"\b[A-Z]{2}\s*[-]?\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4}\b",
    re.IGNORECASE,
)

DATE = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{4}\b"
)

TIME = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:hrs?)?\b",
    re.IGNORECASE,
)

def first_match(
    pattern: re.Pattern,
    text: str,
) -> str | None:

    match = pattern.search(text)

    if not match:
        return None

    return match.group(1).strip()