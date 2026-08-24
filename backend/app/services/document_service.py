from app.domain.models.report import PageText, Section
from app.extractors.pdf_text_extractor import PdfTextExtractor
from app.extractors.section_segmenter import SectionSegmenter


class DocumentService:
    def __init__(self, extractor: PdfTextExtractor, segmenter: SectionSegmenter) -> None:
        self._extractor = extractor
        self._segmenter = segmenter

    def extract_pages(self, pdf_bytes: bytes) -> tuple[int, list[PageText]]:
        return self._extractor.extract_pages(pdf_bytes)

    def segment_sections(self, pages: list[PageText]) -> list[Section]:
        return self._segmenter.segment(pages)
