from app.db.mongodb import db


class DocumentRepository:

    def get_ocr_text(
        self,
        document_id: str,
    ) -> str:

        pages = db.document_pages.find(
            {
                "document_id": document_id,
            }
        ).sort(
            "page_number",
            1,
        )

        return "\n\n".join(
            page.get("text", "")
            for page in pages
        )

    def get_ocr_pages(
        self,
        document_id: str,
    ):

        return list(
            db.document_pages.find(
                {
                    "document_id": document_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "page_number",
                1,
            )
        )

    def store_ocr_page(
        self,
        document_id: str,
        page_number: int,
        text: str,
        provider: str,
        confidence: float,
        blocks: list,
    ):

        db.document_pages.update_one(
            {
                "document_id": document_id,
                "page_number": page_number,
            },
            {
                "$set": {
                    "document_id": document_id,
                    "page_number": page_number,
                    "text": text,
                    "ocr": {
                        "provider": provider,
                        "average_confidence": confidence,
                    },
                    "blocks": blocks,
                }
            },
            upsert=True,
        )