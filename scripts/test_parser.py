from pprint import pprint

from app.db.mongodb import db
from app.services.extraction.parser import parse_fir


document = db.document_pages.find_one({})

if not document:
    raise SystemExit("No OCR document found")

document_id = document["document_id"]

pages = list(
    db.document_pages.find(
        {"document_id": document_id}
    ).sort("page_number", 1)
)

full_text = "\n".join(
    page["text"]
    for page in pages
)

from app.services.extraction.sections import segment_fir

sections = segment_fir(full_text)

section_map = {
    section.name: section.text
    for section in sections
}

header_text = section_map.get(
    "header",
    "",
)

result = parse_fir(
    header_text,
    section_map,
)

pprint(result)