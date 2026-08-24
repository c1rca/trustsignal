from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ConfidenceLevel = Literal["low", "medium", "high"]
FindingStatus = Literal["pass", "fail", "needs_review"]


class EvidenceItem(BaseModel):
    finding_key: str
    page_number: int
    quote: str
    rationale: str


class FindingItem(BaseModel):
    key: str
    status: FindingStatus
    summary: str
    page_number: int
    confidence: ConfidenceLevel
    review_required: bool
    review_reason: str


class ReportMetadata(BaseModel):
    report_id: str
    filename: str
    page_count: int
    uploaded_at: datetime | str


class ExecutiveSnapshot(BaseModel):
    opinion: str
    audit_period: str
    audit_period_start: str | None = None
    audit_period_end: str | None = None
    criteria_covered: list[str]
    ownership: str


class ReviewSummary(BaseModel):
    total_findings: int
    review_required_count: int
    review_required_keys: list[str]
    status_counts: dict[str, int]


class OpinionBlock(BaseModel):
    opinion_type: str
    confidence: ConfidenceLevel
    page_number: int = 0
    evidence: list[EvidenceItem]


class ScopeBlock(BaseModel):
    audit_period: str
    audit_period_start: str | None = None
    audit_period_end: str | None = None
    confidence: ConfidenceLevel
    page_number: int = 0
    evidence: list[EvidenceItem]


class CriteriaBlock(BaseModel):
    criteria: list[str]
    criteria_framework_reference: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem]


class OwnershipBlock(BaseModel):
    ownership_type: str
    confidence: ConfidenceLevel
    summary: str | None = None
    evidence: list[EvidenceItem]


class SubservicesBlock(BaseModel):
    organizations: list[str]
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem]


class CarveoutBlock(BaseModel):
    method: str
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem]


class CuecsBlock(BaseModel):
    responsibilities: list[str]
    confidence: ConfidenceLevel
    present: bool = False
    mode: str = "not_found"
    count: int | None = 0
    needs_review: bool = False
    evidence: list[EvidenceItem]


class ExceptionsBlock(BaseModel):
    exceptions_detected: bool
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem]


class AnalysisResponse(BaseModel):
    report_metadata: ReportMetadata
    executive_snapshot: ExecutiveSnapshot
    opinion: OpinionBlock
    scope: ScopeBlock
    criteria: CriteriaBlock
    ownership: OwnershipBlock
    subservices: SubservicesBlock
    carveout: CarveoutBlock
    cuecs: CuecsBlock
    exceptions: ExceptionsBlock
    reviewer_takeaway: str
    findings: list[FindingItem]
    evidence_index: list[EvidenceItem]
    evidence_by_finding: dict[str, list[EvidenceItem]]
    review_summary: ReviewSummary


class AnalysisProgressResponse(BaseModel):
    status: Literal["idle", "running", "done", "error"]
    stage: str
    message: str
    ocr_active: bool = False
    ocr_current_page: int | None = None
    ocr_total_pages: int | None = None
    ocr_pages_remaining: int | None = None


class DebugSection(BaseModel):
    section_id: str
    heading: str
    normalized_heading: str
    section_type: str
    page_start: int
    page_end: int
    content_preview: str


class DebugResponse(BaseModel):
    report_id: str
    filename: str
    page_count: int
    sections: list[DebugSection]
    analysis_available: bool
    analysis_keys: list[str]
