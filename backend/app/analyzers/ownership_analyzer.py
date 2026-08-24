from __future__ import annotations

import re

from app.domain.models.report import PageText
from app.domain.models.results import OwnershipResult
from app.schemas.analysis_models import EvidenceItem


class OwnershipAnalyzer:
    PROVIDER_STRONG_HINTS = (
        "this report describes a hosting provider",
        "this report describes a data center",
        "provider's control environment",
        "subservice organization's report",
    )

    COMPETING_HINTS = (
        "parent company",
        "subsidiary of",
        "on behalf of",
        "multiple service organizations",
        "combined report",
        "group report",
    )

    REPORT_ON_MANAGEMENT_RE = re.compile(
        r"report on management['’]s description of\s+[^\n]{3,140}",
        flags=re.IGNORECASE,
    )
    MANAGEMENT_DESCRIPTION_RE = re.compile(
        r"management['’]s description of\s+[^\n]{3,160}(?:system|service organization)",
        flags=re.IGNORECASE,
    )
    AUDITOR_REPORT_RE = re.compile(r"independent service auditor['’]s report", flags=re.IGNORECASE)
    AUDITOR_ADDRESSEE_RE = re.compile(r"\bto\s+[^\n]{3,120}", flags=re.IGNORECASE)
    OPINION_DESCRIPTION_RE = re.compile(
        r"the description presents\s+[^\n\.]{3,220}(?:\(system\)|\bsystem\b|service organization(?:'s|’s)? system)",
        flags=re.IGNORECASE,
    )
    MANAGEMENT_ASSERTION_RE = re.compile(r"management['’]s\s+assertion", flags=re.IGNORECASE)
    SERVICE_ORG_RE = re.compile(r"service\s+organization", flags=re.IGNORECASE)

    def analyze(self, pages: list[PageText]) -> OwnershipResult:
        signal_hits: dict[str, tuple[int, str]] = {}
        provider_hits: list[tuple[int, str]] = []
        competing_hits: list[tuple[int, str]] = []

        for page in pages:
            # Ownership is typically established in assertion/auditor sections; avoid deep-system pages
            # where subservice/provider names are expected but not ownership-changing.
            if page.page_number > 12:
                continue

            text = page.text
            lower = text.lower()

            management_match = self.REPORT_ON_MANAGEMENT_RE.search(text) or self.MANAGEMENT_DESCRIPTION_RE.search(text)
            if management_match and "management_report" not in signal_hits:
                signal_hits["management_report"] = (page.page_number, management_match.group(0).strip())

            if self.AUDITOR_REPORT_RE.search(text) and self.AUDITOR_ADDRESSEE_RE.search(text):
                if "auditor_report_vendor" not in signal_hits:
                    signal_hits["auditor_report_vendor"] = (
                        page.page_number,
                        "Independent Service Auditor's Report with vendor addressee/context",
                    )

            opinion_match = self.OPINION_DESCRIPTION_RE.search(text)
            if opinion_match and "opinion_description" not in signal_hits:
                signal_hits["opinion_description"] = (page.page_number, opinion_match.group(0).strip())

            if self.MANAGEMENT_ASSERTION_RE.search(text) and "management_assertion" not in signal_hits:
                signal_hits["management_assertion"] = (page.page_number, "Management's Assertion section detected")

            if self.SERVICE_ORG_RE.search(text) and "service_org_term" not in signal_hits:
                signal_hits["service_org_term"] = (page.page_number, "Service organization context detected")

            for hint in self.PROVIDER_STRONG_HINTS:
                if hint in lower:
                    provider_hits.append((page.page_number, hint))

            for hint in self.COMPETING_HINTS:
                if hint in lower:
                    competing_hits.append((page.page_number, hint))

        strong_vendor_signals = len(signal_hits)
        has_competing = bool(provider_hits or competing_hits)

        if strong_vendor_signals >= 2 and not has_competing:
            page, quote = next(iter(signal_hits.values()))
            return OwnershipResult(
                ownership_type="vendor_report",
                confidence="high",
                summary="Language strongly indicates this is the vendor's SOC 2 report.",
                evidence=[
                    EvidenceItem(
                        finding_key="ownership",
                        page_number=page,
                        quote=quote,
                        rationale="At least two independent vendor-ownership signals detected.",
                    )
                ],
            )

        if strong_vendor_signals >= 2 and has_competing:
            v_page, v_quote = next(iter(signal_hits.values()))
            c_page, c_quote = (provider_hits + competing_hits)[0]
            return OwnershipResult(
                ownership_type="mixed_or_parent",
                confidence="low",
                summary="Vendor ownership is indicated but competing ownership context exists; manual review required.",
                evidence=[
                    EvidenceItem(
                        finding_key="ownership",
                        page_number=v_page,
                        quote=v_quote,
                        rationale="Vendor ownership indicator found.",
                    ),
                    EvidenceItem(
                        finding_key="ownership",
                        page_number=c_page,
                        quote=c_quote,
                        rationale="Competing provider/parent ownership context found.",
                    ),
                ],
            )

        if provider_hits and not signal_hits:
            page, hint = provider_hits[0]
            return OwnershipResult(
                ownership_type="provider_or_subservice_report",
                confidence="medium",
                summary="Language suggests this may be a provider/subservice-owned report.",
                evidence=[
                    EvidenceItem(
                        finding_key="ownership",
                        page_number=page,
                        quote=hint,
                        rationale="Provider-oriented ownership language detected.",
                    )
                ],
            )

        if signal_hits and not has_competing:
            page, quote = next(iter(signal_hits.values()))
            return OwnershipResult(
                ownership_type="vendor_report",
                confidence="medium",
                summary="Some vendor ownership language detected, but not enough independent signals for high confidence.",
                evidence=[
                    EvidenceItem(
                        finding_key="ownership",
                        page_number=page,
                        quote=quote,
                        rationale="Single vendor ownership signal detected.",
                    )
                ],
            )

        return OwnershipResult(
            ownership_type="unclear",
            confidence="low",
            summary="Unable to determine report ownership confidently.",
            evidence=[
                EvidenceItem(
                    finding_key="ownership",
                    page_number=0,
                    quote="No clear ownership indicators detected.",
                    rationale="Ownership language not confidently identified.",
                )
            ],
        )
