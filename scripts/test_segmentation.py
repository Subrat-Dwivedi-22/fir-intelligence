from app.db.mongodb import db
from app.services.extraction.sections import segment_fir


document = db.document_pages.find_one(
    {},
    {
        "_id": 0,
        "document_id": 1,
    },
)

if not document:
    print("No OCR document found")
    raise SystemExit(1)

document_id = document["document_id"]

print(f"Document: {document_id}")

pages = list(
    db.document_pages.find(
        {"document_id": document_id}
    ).sort("page_number", 1)
)

ocr_text = "\n\n".join(
    page.get("text", "")
    for page in pages
)

print(f"OCR characters: {len(ocr_text)}")

sections = segment_fir(ocr_text)

print(f"Sections found: {len(sections)}")

for section in sections:
    print()
    print("=" * 60)
    print(section.name)
    print("=" * 60)
    print(section.text[:1000])

db.document_sections.delete_many({
    "document_id": document_id
})

if sections:
    db.document_sections.insert_many([
        {
            "document_id": document_id,
            "section": section.name,
            "text": section.text,
            "section_order": index,
        }
        for index, section in enumerate(sections)
    ])

print()
print("✓ Sections stored")