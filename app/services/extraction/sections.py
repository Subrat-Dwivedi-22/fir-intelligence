import re
from dataclasses import dataclass


@dataclass
class FIRSection:
    name: str
    text: str


SECTION_PATTERNS = [
    ("offence", re.compile(
        r"2\.\s*\(i\)\s*Act\(s\)", re.IGNORECASE
    )),
    ("occurrence", re.compile(
        r"3\.\s*\(a\)\s*Occurrence of offence", re.IGNORECASE
    )),
    ("information_type", re.compile(
        r"4\.\s*Type of Information", re.IGNORECASE,
    )),
    ("place", re.compile(
        r"5\.\s*Place of Occurrence", re.IGNORECASE
    )),
    ("complainant", re.compile(
        r"6\.\s*Complainant\s*/\s*Informant", re.IGNORECASE
    )),
    ("accused", re.compile(
        r"7\.\s*Details of known", re.IGNORECASE
    )),
    ("delay", re.compile(
        r"8\.\s*Reasons for delay", re.IGNORECASE
    )),
    ("property", re.compile(
        r"9\.\s*Particulars of properties", re.IGNORECASE
    )),
    ("property_value", re.compile(
        r"10\.\s*Total value", re.IGNORECASE
    )),
    ("ud_case", re.compile(
        r"11\.\s*(?:Inquest|Inguest) Report", re.IGNORECASE
    )),
    ("narrative", re.compile(
        r"12\.\s*First Information contents", re.IGNORECASE
    )),
    ("action", re.compile(
        r"13\.\s*Action taken", re.IGNORECASE
    )),
]


def segment_fir(text: str) -> list[FIRSection]:
    matches = []

    for name, pattern in SECTION_PATTERNS:
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

        sections.append(
            FIRSection(
                name=current["name"],
                text=text[start:end].strip(),
            )
        )

    # Everything before section 2 is FIR header metadata.
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
