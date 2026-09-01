import tempfile
import os

os.environ["FLAGS_use_mkldnn"] = "0"

from paddleocr import PaddleOCR

from app.services.ocr.base import OCRService
from app.services.ocr.models import (
    OCRDocument,
    OCRPage,
    OCRWord,
)
from app.services.ocr.pdf_renderer import render_pdf


class PaddleOCRService(OCRService):

    def __init__(self):
        self.ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
        )

    def process(self, pdf_path: str) -> OCRDocument:

        rendered_pages = render_pdf(pdf_path)

        pages = []

        for rendered_page in rendered_pages:

            page_number = rendered_page["page_number"]
            image_data = rendered_page["image"]

            with tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=True,
            ) as temp:

                temp.write(image_data)
                temp.flush()

                result = self.ocr.predict(
                    temp.name
                )

            words = []

            for page_result in result:

                # PaddleOCR result structures can vary
                # by version, so keep parsing isolated here.

                data = page_result.json

                if callable(data):
                    data = data()

                res = data.get("res", data)

                texts = res.get("rec_texts", [])
                scores = res.get("rec_scores", [])
                boxes = res.get("rec_polys", [])

                for text, score, box in zip(
                    texts,
                    scores,
                    boxes,
                ):
                    words.append(
                        OCRWord(
                            text=text,
                            confidence=float(score),
                            bounding_box=box.tolist()
                            if hasattr(box, "tolist")
                            else box,
                        )
                    )

            page_text = "\n".join(
                word.text
                for word in words
            )

            pages.append(
                OCRPage(
                    page_number=page_number,
                    text=page_text,
                    words=words,
                )
            )

        return OCRDocument(
            pages=pages
        )