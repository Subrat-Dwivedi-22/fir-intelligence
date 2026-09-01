from app.db.mongodb import db


class SectionRepository:

    def replace_sections(
        self,
        document_id: str,
        sections,
    ):
        db.document_sections.delete_many({
            "document_id": document_id,
        })

        if not sections:
            return

        documents = []

        for index, section in enumerate(sections):
            documents.append({
                "document_id": document_id,
                "section": section.name,
                "text": section.text,
                "section_order": index,
            })

        db.document_sections.insert_many(documents)

    def get_sections(
        self,
        document_id: str,
    ):
        return list(
            db.document_sections.find(
                {
                    "document_id": document_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "section_order",
                1,
            )
        )