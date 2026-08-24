from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import UploadFile

from app.core.exceptions import ReportNotFoundError, ReportValidationError
from app.domain.models.report import SocReport
from app.schemas.analysis_models import AnalysisResponse
from app.services.document_service import DocumentService
from app.storage.report_store import ReportStore


class UploadService:
    def __init__(
        self,
        document_service: DocumentService,
        report_store: ReportStore,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self._document_service = document_service
        self._report_store = report_store
        self._max_size_bytes = max_size_bytes

    async def upload_report(self, owner_id: str, upload: UploadFile) -> SocReport:
        self._validate_filename(upload.filename)

        report_id = str(uuid4())
        safe_filename = upload.filename or f"{report_id}.pdf"

        size = 0
        payload = bytearray()
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > self._max_size_bytes:
                raise ReportValidationError("Uploaded file exceeds max size of 25 MB")
            payload.extend(chunk)

        pdf_bytes = bytes(payload)
        page_count, pages = self._document_service.extract_pages(pdf_bytes)
        sections = self._document_service.segment_sections(pages)

        report = SocReport(
            id=report_id,
            owner_id=owner_id,
            filename=safe_filename,
            stored_path="",
            uploaded_at=datetime.now(UTC),
            page_count=page_count,
            pdf_bytes=pdf_bytes,
            pages=pages,
            extracted_sections=sections,
        )
        self._report_store.save(report)
        return report

    def get_metadata(self, owner_id: str, report_id: str) -> SocReport:
        report = self._report_store.get(owner_id, report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    def save_analysis(self, owner_id: str, report_id: str, analysis: AnalysisResponse) -> None:
        self._report_store.save_analysis(owner_id, report_id, analysis)

    def get_analysis(self, owner_id: str, report_id: str) -> AnalysisResponse | None:
        return self._report_store.get_analysis(owner_id, report_id)

    def purge_all(self, owner_id: str) -> None:
        self._report_store.purge_all(owner_id)

    @staticmethod
    def _validate_filename(filename: str | None) -> None:
        if not filename:
            raise ReportValidationError("Filename is required")
        if not filename.lower().endswith(".pdf"):
            raise ReportValidationError("Only PDF files are accepted")
