import re
from dataclasses import dataclass


@dataclass
class FIRSection:
    name: str
    text: str


# ---------------------------------------------------------
# Official / numbered FIR format
# ---------------------------------------------------------

NUMBERED_SECTION_PATTERNS = [
    ("offence", re.compile(
        r"2\.\s*\(i\)\s*Act\(s\)",
        re.IGNORECASE,
    )),
    ("occurrence", re.compile(
        r"3\.\s*\(a\)\s*Occurrence of offence",
        re.IGNORECASE,
    )),
    ("information_type", re.compile(
        r"4\.\s*Type of Information",
        re.IGNORECASE,
    )),
    ("place", re.compile(
        r"5\.\s*Place of Occurrence",
        re.IGNORECASE,
    )),
    ("complainant", re.compile(
        r"6\.\s*Complainant\s*/\s*Informant",
        re.IGNORECASE,
    )),
    ("accused", re.compile(
        r"7\.\s*Details of known",
        re.IGNORECASE,
    )),
    ("delay", re.compile(
        r"8\.\s*Reasons for delay",
        re.IGNORECASE,
    )),
    ("property", re.compile(
        r"9\.\s*Particulars of properties",
        re.IGNORECASE,
    )),
    ("property_value", re.compile(
        r"10\.\s*Total value",
        re.IGNORECASE,
    )),
    ("ud_case", re.compile(
        r"11\.\s*(?:Inquest|Inguest) Report",
        re.IGNORECASE,
    )),
    ("narrative", re.compile(
        r"12\.\s*First Information contents",
        re.IGNORECASE,
    )),
    ("action", re.compile(
        r"13\.\s*Action taken",
        re.IGNORECASE,
    )),
]


# ---------------------------------------------------------
# Narrative / simplified FIR format
# ---------------------------------------------------------

NARRATIVE_SECTION_PATTERNS = [
    ("complainant", re.compile(
        r"^COMPLAINANT\s+STATEMENT\s*:?",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("occurrence", re.compile(
        r"^INCIDENT\s+DETAILS?\s*(?:&|AND)\s*SUSPECTS?\s*:?",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("property", re.compile(
        r"^RECOVERED\s+EVIDENCE\s*:?",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("narrative", re.compile(
        r"^RELATIONSHIP\s+LINKAGES?\s*:?",
        re.IGNORECASE | re.MULTILINE,
    )),
]


def _build_sections(
    text: str,
    patterns,
) -> list[FIRSection]:

    matches = []

    for name, pattern in patterns:
        match = pattern.search(text)

        if match:
            matches.append(
                {
                    "name": name,
                    "start": match.start(),
                }
            )

    matches.sort(key=lambda item: item["start"])

    sections = []

    for index, current in enumerate(matches):
        start = current["start"]

        if index + 1 < len(matches):
            end = matches[index + 1]["start"]
        else:
            end = len(text)

        section_text = text[start:end].strip()

        if section_text:
            sections.append(
                FIRSection(
                    name=current["name"],
                    text=section_text,
                )
            )

    if matches:
        header_end = matches[0]["start"]
        header_text = text[:header_end].strip()

        if header_text:
            sections.insert(
                0,
                FIRSection(
                    name="header",
                    text=header_text,
                ),
            )

    return sections


def segment_fir(text: str) -> list[FIRSection]:
    """
    Segment OCR text into logical FIR sections.

    Supports:
    1. Official numbered FIR formats.
    2. Narrative / simplified FIR formats.

    Returns an empty list only when no recognized section
    headings are found.
    """

    if not text or not text.strip():
        return []

    text = text.strip()

    # First try the official numbered FIR format.
    sections = _build_sections(
        text,
        NUMBERED_SECTION_PATTERNS,
    )

    if sections:
        return sections

    # Fall back to narrative FIR format.
    return _build_sections(
        text,
        NARRATIVE_SECTION_PATTERNS,
    )