import fitz

from app.domain.models.report import PageText
from app.extractors.ocr_fallback import OcrFallback


class PdfTextExtractor:
    def __init__(self, ocr_fallback: OcrFallback | None = None) -> None:
        self._ocr = ocr_fallback or OcrFallback()

    def extract_pages(self, pdf_bytes: bytes) -> tuple[int, list[PageText]]:
        pages: list[PageText] = []

        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            total_pages = document.page_count
            for index, page in enumerate(document, start=1):
                native_text = page.get_text("text")
                text = native_text

                # Keep upload-time extraction fast and deterministic.
                # OCR is disabled in upload path to avoid long-running uploads.
                should_ocr = False

                if should_ocr:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    ocr_text = self._ocr.extract_from_png_bytes(pix.tobytes("png"))
                    if ocr_text:
                        text = f"{native_text}\n{ocr_text}".strip()

                pages.append(PageText(page_number=index, text=text))

            return document.page_count, pages

    @staticmethod
    def _looks_like_testing_results_page(native_text: str, page_number: int, total_pages: int) -> bool:
        lower = (native_text or "").lower()
        back_half = page_number >= max(2, total_pages // 2)

        has_testing_signal = any(
            token in lower
            for token in (
                "tests of controls",
                "results of tests",
                "test performed",
                "exceptions",
                "deviation",
                "complementary user entity controls",
            )
        )

        # Force OCR for likely testing/result pages in the back half,
        # and also when back-half pages appear text-sparse/unreliable.
        return back_half and (has_testing_signal or len((native_text or "").strip()) < 1200)
