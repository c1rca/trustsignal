from __future__ import annotations

import re
from threading import Lock

import fitz

from app.analyzers.carveout_analyzer import CarveOutAnalyzer
from app.analyzers.criteria_analyzer import CriteriaAnalyzer
from app.analyzers.cuec_analyzer import CuecAnalyzer
from app.analyzers.exception_analyzer import ExceptionAnalyzer
from app.analyzers.opinion_analyzer import OpinionAnalyzer
from app.analyzers.ownership_analyzer import OwnershipAnalyzer
from app.analyzers.scope_analyzer import ScopeAnalyzer
from app.analyzers.subservice_analyzer import SubserviceAnalyzer
from app.domain.models.report import PageText, SocReport
from app.extractors.ocr_fallback import OcrFallback
from app.domain.models.results import (
    CarveoutResult,
    CriteriaResult,
    CuecsResult,
    ExceptionsResult,
    OpinionResult,
    OwnershipResult,
    ScopeResult,
    SubservicesResult,
)
from app.schemas.analysis_models import (
    AnalysisResponse,
    CarveoutBlock,
    CriteriaBlock,
    CuecsBlock,
    EvidenceItem,
    ExceptionsBlock,
    ExecutiveSnapshot,
    FindingItem,
    OpinionBlock,
    OwnershipBlock,
    ReportMetadata,
    ReviewSummary,
    ScopeBlock,
    SubservicesBlock,
)


class AnalysisService:
    def __init__(self) -> None:
        self._opinion = OpinionAnalyzer()
        self._scope = ScopeAnalyzer()
        self._criteria = CriteriaAnalyzer()
        self._ownership = OwnershipAnalyzer()
        self._subservices = SubserviceAnalyzer()
        self._carveout = CarveOutAnalyzer()
        self._cuecs = CuecAnalyzer()
        self._exceptions = ExceptionAnalyzer()
        self._ocr = OcrFallback(min_chars=220)
        self._progress_lock = Lock()
        self._progress: dict[str, dict[str, object]] = {}

    def get_progress(self, report_id: str) -> dict[str, object]:
        with self._progress_lock:
            return dict(
                self._progress.get(
                    report_id,
                    {
                        "status": "idle",
                        "stage": "idle",
                        "message": "Not started",
                        "ocr_active": False,
                        "ocr_current_page": None,
                        "ocr_total_pages": None,
                        "ocr_pages_remaining": None,
                    },
                )
            )

    def _set_progress(self, report_id: str, **updates: object) -> None:
        with self._progress_lock:
            current = self._progress.get(
                report_id,
                {
                    "status": "idle",
                    "stage": "idle",
                    "message": "Not started",
                    "ocr_active": False,
                    "ocr_current_page": None,
                    "ocr_total_pages": None,
                    "ocr_pages_remaining": None,
                },
            )
            current.update(updates)
            self._progress[report_id] = current

    def analyze(self, report: SocReport) -> AnalysisResponse:
        self._set_progress(report.id, status="running", stage="prepare", message="Preparing analysis", ocr_active=False)

        opinion_pages = self._pages_for(report, "opinion", "auditor_report", "basis_for_qualified_opinion")
        scope_pages = report.pages
        criteria_pages = report.pages
        ownership_pages = report.pages
        subservice_pages = report.pages
        carveout_pages = report.pages
        cuec_pages = self._pages_for(report, "cuec", "system_description", "general")
        exception_pages = report.pages

        try:
            self._set_progress(report.id, stage="opinion", message="Analyzing opinion")
            opinion = self._opinion.analyze(opinion_pages)
            if opinion.opinion_type == "unclear":
                opinion = self._opinion_with_targeted_ocr(report, opinion_pages)

            self._set_progress(report.id, stage="scope", message="Analyzing scope")
            scope = self._scope.analyze(scope_pages)
            self._set_progress(report.id, stage="criteria", message="Analyzing criteria")
            criteria = self._criteria.analyze(criteria_pages)
            self._set_progress(report.id, stage="ownership", message="Analyzing ownership")
            ownership = self._ownership.analyze(ownership_pages)
            self._set_progress(report.id, stage="subservices", message="Analyzing subservices")
            subservices = self._subservices.analyze(subservice_pages)
            self._set_progress(report.id, stage="carveout", message="Analyzing carve-out method")
            carveout = self._carveout.analyze(carveout_pages)
            self._set_progress(report.id, stage="cuecs", message="Analyzing CUECs")
            cuecs = self._cuecs.analyze(cuec_pages)
            self._set_progress(report.id, stage="exceptions", message="Analyzing exceptions")
            exceptions = self._exceptions.analyze(exception_pages)
            if not exceptions.exceptions_detected and exceptions.confidence != "high":
                exceptions = self._exceptions_with_targeted_ocr(report, exception_pages)

            criteria, ownership, subservices, carveout, cuecs, exceptions = self._apply_sanity_checks(
                report,
                criteria,
                ownership,
                subservices,
                carveout,
                cuecs,
                exceptions,
            )

            evidence_index: list[EvidenceItem] = []
            for block in (opinion, scope, criteria, ownership, subservices, carveout, cuecs, exceptions):
                evidence_index.extend(block.evidence)
            evidence_index = self._dedupe_evidence(evidence_index)

            findings = self._order_findings(
                self._build_findings(opinion, scope, criteria, ownership, carveout, cuecs, exceptions)
            )
            reviewer_takeaway = self._build_reviewer_takeaway(opinion, scope, criteria, ownership, carveout)

            result = AnalysisResponse(
                report_metadata=ReportMetadata(
                    report_id=report.id,
                    filename=report.filename,
                    page_count=report.page_count,
                    uploaded_at=report.uploaded_at.isoformat(),
                ),
                executive_snapshot=ExecutiveSnapshot(
                    opinion=opinion.opinion_type,
                    audit_period=scope.audit_period,
                    audit_period_start=scope.audit_period_start,
                    audit_period_end=scope.audit_period_end,
                    criteria_covered=criteria.criteria,
                    ownership=ownership.ownership_type,
                ),
                opinion=OpinionBlock(
                    opinion_type=opinion.opinion_type,
                    confidence=opinion.confidence,
                    page_number=opinion.page_number,
                    evidence=opinion.evidence,
                ),
                scope=ScopeBlock(
                    audit_period=scope.audit_period,
                    audit_period_start=scope.audit_period_start,
                    audit_period_end=scope.audit_period_end,
                    confidence=scope.confidence,
                    page_number=scope.page_number,
                    evidence=scope.evidence,
                ),
                criteria=CriteriaBlock(
                    criteria=criteria.criteria,
                    criteria_framework_reference=criteria.criteria_framework_reference,
                    confidence=criteria.confidence,
                    evidence=criteria.evidence,
                ),
                ownership=OwnershipBlock(
                    ownership_type=ownership.ownership_type,
                    confidence=ownership.confidence,
                    summary=ownership.summary,
                    evidence=ownership.evidence,
                ),
                subservices=SubservicesBlock(
                    organizations=subservices.organizations,
                    confidence=subservices.confidence,
                    evidence=subservices.evidence,
                ),
                carveout=CarveoutBlock(
                    method=carveout.method,
                    confidence=carveout.confidence,
                    evidence=carveout.evidence,
                ),
                cuecs=CuecsBlock(
                    responsibilities=cuecs.responsibilities,
                    confidence=cuecs.confidence,
                    present=cuecs.present,
                    mode=cuecs.mode,
                    count=cuecs.count,
                    needs_review=cuecs.needs_review,
                    evidence=cuecs.evidence,
                ),
                exceptions=ExceptionsBlock(
                    exceptions_detected=exceptions.exceptions_detected,
                    confidence=exceptions.confidence,
                    evidence=exceptions.evidence,
                ),
                reviewer_takeaway=reviewer_takeaway,
                findings=findings,
                evidence_index=evidence_index,
                evidence_by_finding=self._group_evidence_by_finding(evidence_index),
                review_summary=self._build_review_summary(findings),
            )
            self._set_progress(report.id, status="done", stage="complete", message="Analysis complete", ocr_active=False)
            return result
        except Exception:
            self._set_progress(report.id, status="error", stage="error", message="Analysis failed", ocr_active=False)
            raise
    def _build_findings(
        self,
        opinion: OpinionResult,
        scope: ScopeResult,
        criteria: CriteriaResult,
        ownership: OwnershipResult,
        carveout: CarveoutResult,
        cuecs: CuecsResult,
        exceptions: ExceptionsResult,
    ) -> list[FindingItem]:
        opinion_status = (
            "pass"
            if opinion.opinion_type == "unqualified"
            else "fail" if opinion.opinion_type in {"qualified", "adverse", "disclaimer"} else "needs_review"
        )

        scope_status = "pass" if scope.audit_period != "Not clearly stated" else "needs_review"
        criteria_status = "pass" if criteria.criteria else "needs_review"
        ownership_status = "pass" if ownership.ownership_type == "vendor_report" else "needs_review"
        carveout_status = "needs_review" if carveout.method == "unclear" else "pass"

        cuec_count = cuecs.count if cuecs.count is not None else len(cuecs.responsibilities)
        cuec_has_page_evidence = any(ev.page_number and ev.page_number > 0 for ev in cuecs.evidence)
        low_cuec_count = cuecs.mode != "not_required" and cuecs.present and cuec_count <= 2
        if cuecs.mode == "not_required":
            cuec_status = "pass"
        elif cuecs.confidence == "low" or low_cuec_count:
            cuec_status = "needs_review"
        else:
            cuec_status = "pass"

        has_exception_heading_signal = any("heading" in ev.rationale.lower() for ev in exceptions.evidence)
        has_exception_page_evidence = any(ev.page_number and ev.page_number > 0 for ev in exceptions.evidence)

        if exceptions.exceptions_detected:
            exception_status = "fail"
        elif exceptions.confidence == "high":
            exception_status = "pass"
        elif has_exception_heading_signal or has_exception_page_evidence:
            exception_status = "needs_review"
        else:
            # Dynamic false-positive suppression:
            # low-confidence/no-page generic exception outputs should not become noisy review flags.
            exception_status = "pass"

        return [
            FindingItem(
                key="opinion",
                status=opinion_status,
                summary=f"Opinion detected as {opinion.opinion_type}.",
                page_number=opinion.page_number,
                confidence=opinion.confidence,
                review_required=opinion_status != "pass" or opinion.confidence == "low",
                review_reason=(
                    "Opinion is not unqualified or confidence is low."
                    if opinion_status != "pass" or opinion.confidence == "low"
                    else ""
                ),
            ),
            FindingItem(
                key="scope",
                status=scope_status,
                summary=f"Audit period: {scope.audit_period}.",
                page_number=scope.page_number,
                confidence=scope.confidence,
                review_required=scope_status != "pass" or scope.confidence in {"low", "medium"},
                review_reason=(
                    "Scope period is missing or non-canonical; confirm exact audit window."
                    if scope_status != "pass" or scope.confidence in {"low", "medium"}
                    else ""
                ),
            ),
            FindingItem(
                key="criteria",
                status=criteria_status,
                summary=(
                    f"Criteria covered: {', '.join(criteria.criteria)}."
                    if criteria.criteria
                    else "No criteria confidently detected."
                ),
                page_number=0,
                confidence=criteria.confidence,
                review_required=criteria_status != "pass" or criteria.confidence == "low",
                review_reason=(
                    "Criteria coverage appears incomplete or uncertain."
                    if criteria_status != "pass" or criteria.confidence == "low"
                    else ""
                ),
            ),
            FindingItem(
                key="cuecs",
                status=cuec_status,
                summary=(
                    "CUECs detected and parsed with sufficient coverage."
                    if cuecs.mode != "not_required" and bool(cuecs.responsibilities) and cuec_count > 2
                    else (
                        "CUEC language detected, but extracted item count is low (1–2); manual review recommended."
                        if cuec_status == "needs_review" and cuec_has_page_evidence and cuec_count <= 2
                        else (
                            "CUEC language is referenced, but explicit user responsibilities were not listed."
                            if cuec_has_page_evidence or cuecs.mode == "referenced_not_listed"
                            else (
                                "Report indicates CUECs are not required."
                                if cuecs.mode == "not_required"
                                else "No obvious CUEC language detected."
                            )
                        )
                    )
                ),
                page_number=0,
                confidence=cuecs.confidence,
                review_required=cuec_status != "pass",
                review_reason=(
                    "Only 1–2 CUEC items were extracted; parsing may be incomplete. Verify the CUEC section manually."
                    if cuec_status == "needs_review" and cuec_has_page_evidence and cuec_count <= 2
                    else (
                        "CUEC extraction confidence is low or parsed count is unexpectedly low; review CUEC section parsing."
                        if cuec_status == "needs_review" and bool(cuecs.responsibilities)
                        else (
                            "CUEC was referenced but no explicit responsibility list was extracted."
                            if cuec_status == "needs_review" and (cuec_has_page_evidence or cuecs.mode == "referenced_not_listed")
                            else (
                                "No page-level CUEC evidence was found; verify whether CUECs are truly absent for this report."
                                if cuec_status == "needs_review"
                                else ""
                            )
                        )
                    )
                ),
            ),
            FindingItem(
                key="exceptions",
                status=exception_status,
                summary=(
                    "Potential exceptions/deviations detected."
                    if exceptions.exceptions_detected
                    else (
                        "Exception-related section found; manual review recommended."
                        if exception_status == "needs_review"
                        else "No obvious exception/deviation language detected."
                    )
                ),
                page_number=0,
                confidence=exceptions.confidence,
                review_required=exception_status != "pass",
                review_reason=(
                    "Exception indicators found and should be manually confirmed."
                    if exceptions.exceptions_detected
                    else (
                        "Exception-related heading detected but no explicit exception statement was found."
                        if exception_status == "needs_review" and has_exception_heading_signal
                        else (
                            "Low-confidence exception signal found; no page-level evidence was captured."
                            if exception_status == "needs_review"
                            else ""
                        )
                    )
                ),
            ),
        ]

    def _opinion_with_targeted_ocr(self, report: SocReport, opinion_pages: list[PageText]) -> OpinionResult:
        if not self._ocr.enabled:
            return self._opinion.analyze(opinion_pages)

        try:
            with fitz.open(stream=report.pdf_bytes, filetype="pdf") as document:
                max_pages = min(document.page_count, 20)
                enhanced: list[PageText] = []

                self._set_progress(
                    report.id,
                    stage="ocr_opinion",
                    message="Running OCR for opinion pages",
                    ocr_active=True,
                    ocr_total_pages=max_pages,
                    ocr_current_page=1,
                    ocr_pages_remaining=max_pages - 1,
                )

                for page_number in range(1, max_pages + 1):
                    self._set_progress(
                        report.id,
                        stage="ocr_opinion",
                        message=f"OCR page {page_number} of {max_pages}",
                        ocr_active=True,
                        ocr_total_pages=max_pages,
                        ocr_current_page=page_number,
                        ocr_pages_remaining=max_pages - page_number,
                    )
                    page = document[page_number - 1]
                    native = page.get_text("text")
                    lower = native.lower()

                    likely_opinion_page = any(
                        token in lower
                        for token in (
                            "independent service auditor",
                            "opinion",
                            "basis for",
                            "material respects",
                            "fairly presented",
                            "presents fairly",
                        )
                    )
                    if not likely_opinion_page and page_number > 8:
                        continue

                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    ocr_text = self._ocr.extract_from_png_bytes(pix.tobytes("png"))
                    combined = f"{native}\n{ocr_text}".strip() if ocr_text else native
                    enhanced.append(PageText(page_number=page_number, text=combined))

                if not enhanced:
                    self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
                    return self._opinion.analyze(opinion_pages)

                ocr_opinion = self._opinion.analyze(enhanced)
                self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
                return ocr_opinion if ocr_opinion.opinion_type != "unclear" else self._opinion.analyze(opinion_pages)
        except Exception:
            self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
            return self._opinion.analyze(opinion_pages)

    def _exceptions_with_targeted_ocr(self, report: SocReport, exception_pages: list[PageText]) -> ExceptionsResult:
        if not self._ocr.enabled:
            return self._exceptions.analyze(exception_pages)

        try:
            with fitz.open(stream=report.pdf_bytes, filetype="pdf") as document:
                total = document.page_count
                enhanced: list[PageText] = []

                self._set_progress(
                    report.id,
                    stage="ocr_exceptions",
                    message="Running OCR for exceptions pages",
                    ocr_active=True,
                    ocr_total_pages=total,
                    ocr_current_page=1,
                    ocr_pages_remaining=max(total - 1, 0),
                )

                for page_number in range(1, total + 1):
                    self._set_progress(
                        report.id,
                        stage="ocr_exceptions",
                        message=f"OCR page {page_number} of {total}",
                        ocr_active=True,
                        ocr_total_pages=total,
                        ocr_current_page=page_number,
                        ocr_pages_remaining=total - page_number,
                    )
                    page = document[page_number - 1]
                    native = page.get_text("text")
                    lower = native.lower()

                    in_back_half = page_number >= max(2, total // 2)
                    likely_exception_page = any(
                        token in lower
                        for token in (
                            "tests of controls",
                            "results of tests",
                            "testing exceptions",
                            "exception",
                            "deviation",
                            "management's response",
                        )
                    )

                    if not in_back_half and not likely_exception_page:
                        continue

                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    ocr_text = self._ocr.extract_from_png_bytes(pix.tobytes("png"))
                    combined = f"{native}\n{ocr_text}".strip() if ocr_text else native
                    enhanced.append(PageText(page_number=page_number, text=combined))

                if not enhanced:
                    self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
                    return self._exceptions.analyze(exception_pages)

                ocr_exceptions = self._exceptions.analyze(enhanced)
                self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
                if ocr_exceptions.exceptions_detected or ocr_exceptions.confidence != "low":
                    return ocr_exceptions
                return self._exceptions.analyze(exception_pages)
        except Exception:
            self._set_progress(report.id, ocr_active=False, ocr_current_page=None, ocr_pages_remaining=None)
            return self._exceptions.analyze(exception_pages)

    def _pages_for(self, report: SocReport, *section_types: str) -> list[PageText]:
        if not report.extracted_sections:
            return report.pages

        wanted = set(section_types)
        selected_numbers: list[int] = []
        for section in report.extracted_sections:
            if section.section_type in wanted:
                selected_numbers.extend(range(section.page_start, section.page_end + 1))

        if not selected_numbers:
            return report.pages

        page_index = {page.page_number: page for page in report.pages}
        ordered_unique = sorted(set(selected_numbers))
        pages = [page_index[number] for number in ordered_unique if number in page_index]
        return pages or report.pages

    @staticmethod
    def _order_findings(findings: list[FindingItem]) -> list[FindingItem]:
        priority = {"fail": 0, "needs_review": 1, "pass": 2}
        fixed_top_order = {
            "opinion": 0,
            "scope": 1,
            "criteria": 2,
            "exceptions": 3,
        }

        def key(item: FindingItem) -> tuple[int, int, str]:
            if item.key in fixed_top_order:
                return (0, fixed_top_order[item.key], item.key)
            return (1, priority.get(item.status, 3), item.key)

        return sorted(findings, key=key)

    @staticmethod
    def _group_evidence_by_finding(evidence_index: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
        grouped: dict[str, list[EvidenceItem]] = {}
        for evidence in evidence_index:
            grouped.setdefault(evidence.finding_key, []).append(evidence)
        return grouped

    @staticmethod
    def _dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[tuple[str, int, str, str]] = set()
        deduped: list[EvidenceItem] = []
        for item in items:
            key = (
                item.finding_key,
                item.page_number,
                item.quote.strip(),
                item.rationale.strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _build_review_summary(findings: list[FindingItem]) -> ReviewSummary:
        required = [item for item in findings if item.review_required]
        statuses = {
            "pass": len([item for item in findings if item.status == "pass"]),
            "fail": len([item for item in findings if item.status == "fail"]),
            "needs_review": len([item for item in findings if item.status == "needs_review"]),
        }

        return ReviewSummary(
            total_findings=len(findings),
            review_required_count=len(required),
            review_required_keys=[item.key for item in required],
            status_counts=statuses,
        )

    def _apply_sanity_checks(
        self,
        report: SocReport,
        criteria: CriteriaResult,
        ownership: OwnershipResult,
        subservices: SubservicesResult,
        carveout: CarveoutResult,
        cuecs: CuecsResult,
        exceptions: ExceptionsResult,
    ) -> tuple[CriteriaResult, OwnershipResult, SubservicesResult, CarveoutResult, CuecsResult, ExceptionsResult]:
        full_text = "\n".join(page.text for page in report.pages)
        lower_text = full_text.lower()

        scoped_multi = self._extract_scoped_criteria(lower_text)
        singular_security = any(
            phrase in lower_text
            for phrase in (
                "criterion relevant to security",
                "controls relevant to security",
                "security category",
            )
        )

        if scoped_multi:
            criteria.criteria = scoped_multi
            criteria.confidence = "high"
        elif singular_security:
            criteria.criteria = ["Security"]
            criteria.confidence = "high"

        if self._looks_like_full_framework_reference(lower_text):
            criteria.criteria_framework_reference = [
                "Security",
                "Availability",
                "Processing Integrity",
                "Confidentiality",
                "Privacy",
            ]

        if criteria.criteria == criteria.criteria_framework_reference and len(criteria.criteria) == 5 and (
            scoped_multi or singular_security
        ):
            criteria.evidence.append(
                EvidenceItem(
                    finding_key="criteria",
                    page_number=0,
                    quote="Scoped criteria and framework-reference criteria are being conflated.",
                    rationale="Scoped-language override applied to keep criteria_in_scope limited to explicitly scoped categories.",
                )
            )

        vendor_signal_count = sum(
            1
            for phrase in (
                "independent service auditor's report",
                "independent service auditor’s report",
                "report on management's description",
                "management's assertion",
                "management’s assertion",
            )
            if phrase in lower_text
        )
        weak_contradictions = any(token in lower_text for token in ("on behalf of", "for use by", "affiliate"))
        strong_contradictions = any(
            token in lower_text for token in ("combined report", "group report", "multiple service organizations")
        )
        if vendor_signal_count >= 3 and weak_contradictions and not strong_contradictions:
            ownership.ownership_type = "vendor_report"
            if ownership.confidence == "low":
                ownership.confidence = "medium"

        carveout_signals = sum(
            1
            for phrase in (
                "does not disclose the actual controls",
                "our examination did not include the services provided by the subservice organizations",
                "our examination did not extend to controls at the subservice organizations",
                "types of complementary subservice organization controls assumed",
            )
            if phrase in lower_text
        )
        if carveout_signals >= 2:
            carveout.method = "carve_out"
            carveout.confidence = "high"

        if carveout.method == "carve_out" and not subservices.organizations and "subservice organizations" in lower_text:
            subservices.confidence = "low"
            subservices.evidence.append(
                EvidenceItem(
                    finding_key="subservices",
                    page_number=0,
                    quote="Subservice section contains named providers, but parser returned none.",
                    rationale="Validation flagged likely extraction miss for carved-out subservice section.",
                )
            )

        user_control_heading_present = any(
            token in lower_text
            for token in (
                "user control considerations",
                "complementary user entity controls",
                "customer responsibilities",
            )
        )
        cuec_has_page_evidence = any(ev.page_number and ev.page_number > 0 for ev in cuecs.evidence)
        if user_control_heading_present and not cuec_has_page_evidence and not cuecs.responsibilities:
            cuecs.present = True
            cuecs.mode = "narrative"
            cuecs.count = None
            cuecs.needs_review = True
            cuecs.confidence = "medium" if cuecs.confidence == "low" else cuecs.confidence
            cuecs.evidence.append(
                EvidenceItem(
                    finding_key="cuecs",
                    page_number=0,
                    quote="User-control section exists, but extractor returned no structured responsibilities.",
                    rationale="Fallback applied for heading-only signal with no page-level CUEC evidence.",
                )
            )

        if exceptions.exceptions_detected and (
            lower_text.count("no exceptions noted") + lower_text.count("no deviations noted")
        ) >= 2:
            exceptions.exceptions_detected = False
            exceptions.confidence = "medium"

        return criteria, ownership, subservices, carveout, cuecs, exceptions

    @staticmethod
    def _looks_like_full_framework_reference(lower_text: str) -> bool:
        return all(
            token in lower_text
            for token in (
                "security",
                "availability",
                "processing integrity",
                "confidentiality",
                "privacy",
            )
        )

    @staticmethod
    def _extract_scoped_criteria(lower_text: str) -> list[str]:
        match = re.search(r"relevant to\s+([a-z,\sand]+)", lower_text)
        if not match:
            return []

        raw = match.group(1)
        categories: list[str] = []
        mapping = {
            "security": "Security",
            "availability": "Availability",
            "processing integrity": "Processing Integrity",
            "confidentiality": "Confidentiality",
            "privacy": "Privacy",
        }

        for key, canonical in mapping.items():
            if re.search(rf"\b{re.escape(key)}\b", raw) and canonical not in categories:
                categories.append(canonical)

        return categories

    def _build_reviewer_takeaway(
        self,
        opinion: OpinionResult,
        scope: ScopeResult,
        criteria: CriteriaResult,
        ownership: OwnershipResult,
        carveout: CarveoutResult,
    ) -> str:
        criteria_text = ", ".join(criteria.criteria) if criteria.criteria else "unclear criteria"

        return (
            f"This appears to be a {opinion.opinion_type} SOC 2 report covering {scope.audit_period}, "
            f"with criteria {criteria_text}. Ownership signal is {ownership.ownership_type}; "
            f"subservice method is {carveout.method}."
        )
