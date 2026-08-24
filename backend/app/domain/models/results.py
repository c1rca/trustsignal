from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.analysis_models import ConfidenceLevel, EvidenceItem


@dataclass(slots=True)
class OpinionResult:
    opinion_type: str
    confidence: ConfidenceLevel
    page_number: int
    evidence: list[EvidenceItem] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScopeResult:
    audit_period: str
    confidence: ConfidenceLevel
    page_number: int
    audit_period_start: str | None = None
    audit_period_end: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class CriteriaResult:
    criteria: list[str] = field(default_factory=list)
    criteria_framework_reference: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = "low"
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class OwnershipResult:
    ownership_type: str
    confidence: ConfidenceLevel
    summary: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class SubservicesResult:
    organizations: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = "low"
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class CarveoutResult:
    method: str
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class CuecsResult:
    responsibilities: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = "low"
    present: bool = False
    mode: str = "not_found"
    count: int | None = 0
    needs_review: bool = False
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass(slots=True)
class ExceptionsResult:
    exceptions_detected: bool
    confidence: ConfidenceLevel
    evidence: list[EvidenceItem] = field(default_factory=list)
