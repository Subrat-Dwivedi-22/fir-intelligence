import fitz


def render_pdf(pdf_path: str, dpi: int = 200):
    document = fitz.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        matrix = fitz.Matrix(
            dpi / 72,
            dpi / 72,
        )

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        pages.append(
            {
                "page_number": page_number,
                "image": pixmap.tobytes("png"),
            }
        )

    document.close()

    return pages