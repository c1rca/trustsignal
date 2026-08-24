from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class UploadReportResponse(BaseModel):
    report_id: str
    filename: str
    page_count: int
    uploaded_at: datetime


class ReportMetadataResponse(BaseModel):
    report_id: str
    filename: str
    page_count: int
    uploaded_at: datetime


class SectionResponse(BaseModel):
    section_id: str
    heading: str
    normalized_heading: str
    page_start: int
    page_end: int
    section_type: str
    content_preview: str


class ErrorResponse(BaseModel):
    detail: str
