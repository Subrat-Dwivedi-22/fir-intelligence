import os
import resource
import tempfile

os.environ["FLAGS_use_mkldnn"] = "0"

from paddleocr import PaddleOCR

from app.services.ocr.base import OCRService
from app.services.ocr.models import (
    OCRDocument,
    OCRPage,
    OCRWord,
)
from app.services.ocr.pdf_renderer import render_pdf


def memory_mb():
    """
    Return the maximum resident set size used by this process in MB.
    """
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class PaddleOCRService(OCRService):

    def __init__(self):
        print(
            f"[MEM] before PaddleOCR init: "
            f"{memory_mb():.1f} MB"
        )

        self.ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,

            # Disable document preprocessing models.
            # FIR PDFs are already rendered as upright page images.
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

        print(
            f"[MEM] after PaddleOCR init: "
            f"{memory_mb():.1f} MB"
        )

    def process(self, pdf_path: str) -> OCRDocument:

        print(
            f"[MEM] before render: "
            f"{memory_mb():.1f} MB"
        )

        rendered_pages = render_pdf(pdf_path)

        print(
            f"[MEM] after render: "
            f"{memory_mb():.1f} MB"
        )

        print(
            f"[MEM] rendered pages: "
            f"{len(rendered_pages)}"
        )

        pages = []

        for rendered_page in rendered_pages:

            print(
                f"[MEM] before OCR: "
                f"{memory_mb():.1f} MB"
            )

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

            print(
                f"[MEM] after OCR: "
                f"{memory_mb():.1f} MB"
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
                            bounding_box=(
                                box.tolist()
                                if hasattr(box, "tolist")
                                else box
                            ),
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

            print(
                f"[MEM] after page processing: "
                f"{memory_mb():.1f} MB"
            )

        return OCRDocument(
            pages=pages
        )