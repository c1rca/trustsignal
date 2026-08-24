from __future__ import annotations

import re
from datetime import datetime

from app.domain.models.report import PageText
from app.domain.models.results import ScopeResult
from app.schemas.analysis_models import EvidenceItem


class ScopeAnalyzer:
    DATE_RANGE_PATTERN = re.compile(
        r"(?:for\s+the\s+period\s+from|for\s+the\s+period|the\s+period\s+from|throughout\s+the\s+period|from)\s+"
        r"([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})"
        r"\s+(?:through|to)\s+"
        r"([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})",
        re.IGNORECASE,
    )

    PERIOD_ENDED_PATTERN = re.compile(
        r"period\s+ended\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        re.IGNORECASE,
    )

    DIRECT_RANGE_PATTERN = re.compile(
        r"([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})"
        r"\s*,?\s*(?:to|through|\-|–|—)\s*"
        r"([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})",
        re.IGNORECASE,
    )

    def analyze(self, pages: list[PageText]) -> ScopeResult:
        for page in pages:
            compact = re.sub(r"\s+", " ", page.text)
            range_match = self.DATE_RANGE_PATTERN.search(compact)
            if range_match:
                start_raw, end_raw = range_match.group(1), range_match.group(2)
                start_iso = self._to_iso_date(start_raw)
                end_iso = self._to_iso_date(end_raw)
                if start_iso and end_iso:
                    normalized = f"{start_iso} to {end_iso}"
                    return ScopeResult(
                        audit_period=normalized,
                        confidence="high",
                        page_number=page.page_number,
                        audit_period_start=start_iso,
                        audit_period_end=end_iso,
                        evidence=[
                            EvidenceItem(
                                finding_key="scope",
                                page_number=page.page_number,
                                quote=range_match.group(0),
                                rationale="Detected explicit SOC 2 period range and normalized to ISO dates.",
                            )
                        ],
                    )

            direct_match = self.DIRECT_RANGE_PATTERN.search(compact)
            if direct_match:
                start_raw, end_raw = direct_match.group(1), direct_match.group(2)
                start_iso = self._to_iso_date(start_raw)
                end_iso = self._to_iso_date(end_raw)
                if start_iso and end_iso:
                    normalized = f"{start_iso} to {end_iso}"
                    return ScopeResult(
                        audit_period=normalized,
                        confidence="high",
                        page_number=page.page_number,
                        audit_period_start=start_iso,
                        audit_period_end=end_iso,
                        evidence=[
                            EvidenceItem(
                                finding_key="scope",
                                page_number=page.page_number,
                                quote=direct_match.group(0),
                                rationale="Detected explicit date range and normalized to ISO dates.",
                            )
                        ],
                    )

            ended_match = self.PERIOD_ENDED_PATTERN.search(compact)
            if ended_match:
                end_iso = self._to_iso_date(ended_match.group(1))
                if end_iso:
                    return ScopeResult(
                        audit_period=f"period ended {end_iso}",
                        confidence="medium",
                        page_number=page.page_number,
                        audit_period_end=end_iso,
                        evidence=[
                            EvidenceItem(
                                finding_key="scope",
                                page_number=page.page_number,
                                quote=ended_match.group(0),
                                rationale="Detected period-ended phrasing and normalized end date.",
                            )
                        ],
                    )

        return ScopeResult(
            audit_period="Not clearly stated",
            confidence="low",
            page_number=0,
            evidence=[
                EvidenceItem(
                    finding_key="scope",
                    page_number=0,
                    quote="No normalized date range pattern detected.",
                    rationale="Date range requires manual review.",
                )
            ],
        )

    @staticmethod
    def _to_iso_date(raw: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", raw.strip())
        cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", cleaned, flags=re.IGNORECASE)
        formats = ["%B %d, %Y", "%B %d %Y", "%d %B %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt).date().isoformat()
            except ValueError:
                continue
        return None
