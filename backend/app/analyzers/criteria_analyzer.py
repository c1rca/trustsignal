from __future__ import annotations

import re

from app.analyzers.pattern_families import CRITERIA_HEADING_PATTERNS, matches_any
from app.domain.models.results import CriteriaResult
from app.domain.models.report import PageText
from app.schemas.analysis_models import EvidenceItem


class CriteriaAnalyzer:
    CATEGORY_MAP = {
        "security": "Security",
        "availability": "Availability",
        "processing integrity": "Processing Integrity",
        "confidentiality": "Confidentiality",
        "privacy": "Privacy",
    }

    IN_SCOPE_PATTERNS = (
        re.compile(r"controls(?:[^.]{0,120})?relevant\s+to\s+([a-z,&/\s\-\d]+)", re.IGNORECASE),
        re.compile(r"relevant\s+to\s+([a-z,&/\s\-\d]+)", re.IGNORECASE),
        re.compile(r"criterion\s+(?:for|of)\s+([a-z,&/\s\-]+?)(?:\s+set\s+forth|[.;]|$)", re.IGNORECASE),
        re.compile(r"criteria\s+(?:relevant\s+to|for)\s+([a-z,&/\s\-]+?)(?:\s+set\s+forth|[.;]|$)", re.IGNORECASE),
        re.compile(r"report\s+on\s+controls.*?relevant\s+to\s+([a-z,&/\s\-]+?)(?:[.;]|$)", re.IGNORECASE),
        re.compile(r"applicable\s+trust\s+services\s+criteria\s+relevant\s+to\s+([a-z,&/\s\-]+?)(?:[.;]|$)", re.IGNORECASE),
    )

    FRAMEWORK_PATTERN = re.compile(
        r"trust\s+services\s+criteria\s+for\s+security,\s*availability,\s*processing\s+integrity,\s*confidentiality,\s*and\s*privacy",
        re.IGNORECASE,
    )

    CONTEXT_PRIORITY_MARKERS = (
        "independent service auditor",
        "table of contents",
        "assertion",
        "report on management",
        "opinion",
    )

    def analyze(self, pages: list[PageText]) -> CriteriaResult:
        found_scope: list[str] = []
        framework_references: list[str] = []
        evidence: list[EvidenceItem] = []

        scoped_candidates: list[tuple[int, int, list[str], str, int]] = []

        for page in pages:
            compact_page = re.sub(r"\s+", " ", page.text).strip()
            lower_page = compact_page.lower()

            framework_match = self.FRAMEWORK_PATTERN.search(compact_page)
            if framework_match:
                ref = framework_match.group(0)
                for label in self.CATEGORY_MAP.values():
                    if label not in framework_references:
                        framework_references.append(label)
                evidence.append(
                    EvidenceItem(
                        finding_key="criteria",
                        page_number=page.page_number,
                        quote=ref,
                        rationale="Detected Trust Services framework citation.",
                    )
                )

            page_has_signal = (
                matches_any(lower_page, CRITERIA_HEADING_PATTERNS)
                or "relevant to" in lower_page
                or "criterion for" in lower_page
                or "criterion of" in lower_page
                or "controls relevant to" in lower_page
            )
            if not page_has_signal:
                continue

            for pattern in self.IN_SCOPE_PATTERNS:
                for match in pattern.finditer(compact_page):
                    matched_text = match.group(0)
                    categories = self._extract_categories(match.group(1))
                    if not categories:
                        continue
                    if self._looks_like_framework_only(matched_text):
                        continue
                    priority = self._priority_for_context(lower_page, page.page_number)
                    scoped_candidates.append((priority, page.page_number, categories, matched_text, len(matched_text)))

        if scoped_candidates:
            scoped_candidates.sort(key=lambda item: (item[0], item[1], item[4]))
            _, page_number, categories, quote, _ = scoped_candidates[0]
            for label in categories:
                if label in found_scope:
                    continue
                found_scope.append(label)
                evidence.append(
                    EvidenceItem(
                        finding_key="criteria",
                        page_number=page_number,
                        quote=quote,
                        rationale="Detected scoped Trust Services criteria category from highest-confidence scope language.",
                    )
                )

        found_scope = self._dedupe_labels(found_scope)
        framework_references = self._dedupe_labels(framework_references)

        if found_scope:
            return CriteriaResult(
                criteria=found_scope,
                criteria_framework_reference=framework_references,
                confidence="high",
                evidence=evidence,
            )

        return CriteriaResult(
            criteria=[],
            criteria_framework_reference=framework_references,
            confidence="low",
            evidence=evidence
            or [
                EvidenceItem(
                    finding_key="criteria",
                    page_number=0,
                    quote="No explicit scoped Trust Services criteria statement found.",
                    rationale="Criteria coverage requires manual verification.",
                )
            ],
        )

    def _extract_categories(self, text: str) -> list[str]:
        lower = text.lower()
        hits: list[tuple[int, str]] = []
        for key, label in self.CATEGORY_MAP.items():
            match = re.search(rf"\b{re.escape(key)}\b", lower)
            if match:
                hits.append((match.start(), label))
        hits.sort(key=lambda item: item[0])

        detected: list[str] = []
        for _, label in hits:
            if label not in detected:
                detected.append(label)
        return detected

    def _priority_for_context(self, lower_page: str, page_number: int) -> int:
        if any(marker in lower_page for marker in self.CONTEXT_PRIORITY_MARKERS):
            return 0
        if page_number <= 12:
            return 1
        return 2

    def _looks_like_framework_only(self, text: str) -> bool:
        lowered = text.lower()
        has_framework_list = all(
            token in lowered
            for token in (
                "security",
                "availability",
                "processing integrity",
                "confidentiality",
                "privacy",
            )
        )
        return has_framework_list

    def _dedupe_labels(self, labels: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for label in labels:
            key = re.sub(r"\s+", " ", label).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(label.strip())
        return out
