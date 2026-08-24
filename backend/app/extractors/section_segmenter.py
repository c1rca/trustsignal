from __future__ import annotations

import re
from uuid import uuid4

from app.analyzers.pattern_families import (
    CARVEOUT_HEADING_PATTERNS,
    CRITERIA_HEADING_PATTERNS,
    CUEC_HEADING_PATTERNS,
    OPINION_HEADING_PATTERNS,
    SUBSERVICE_HEADING_PATTERNS,
    TESTING_RESULTS_HEADING_PATTERNS,
    matches_any,
)
from app.domain.models.report import PageText, Section


class SectionSegmenter:
    KNOWN_HEADINGS: tuple[str, ...] = (
        "table of contents",
        "independent service auditor",
        "opinion",
        "basis for qualified opinion",
        "management's assertion",
        "assertion",
        "description of the system",
        "system description",
        "subservice organization",
        "complementary user entity controls",
        "description of tests of controls",
        "results of tests",
        "trust services criteria",
    )

    def segment(self, pages: list[PageText]) -> list[Section]:
        sections: list[Section] = []

        for page in pages:
            heading = self._detect_heading(page.text)
            normalized = self._normalize_heading(heading)
            section_type = self._classify(normalized, page.text, page.page_number)

            if sections and self._should_merge(sections[-1], normalized, section_type):
                previous = sections[-1]
                previous.page_end = page.page_number
                previous.content = f"{previous.content}\n\n{page.text}"
                continue

            sections.append(
                Section(
                    id=str(uuid4()),
                    heading=heading,
                    normalized_heading=normalized,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    content=page.text,
                    section_type=section_type,
                )
            )

        return sections

    def _detect_heading(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:16]:
            lower = line.lower()
            if any(keyword in lower for keyword in self.KNOWN_HEADINGS):
                return line
            if self._looks_like_heading(line):
                return line
        return "General"

    @staticmethod
    def _normalize_heading(heading: str) -> str:
        normalized = heading.lower().strip()
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized or "general"

    def _classify(self, normalized_heading: str, text: str, page_number: int) -> str:
        lower = text.lower()

        if "table of contents" in normalized_heading or "table of contents" in lower:
            return "table_of_contents"

        if page_number == 1 and ("soc 2" in lower or "service organization controls" in lower):
            return "cover"

        if "basis for qualified opinion" in normalized_heading:
            return "basis_for_qualified_opinion"
        if matches_any(normalized_heading, OPINION_HEADING_PATTERNS) or "in our opinion" in lower:
            if "independent service auditor" in normalized_heading:
                return "auditor_report"
            return "opinion"
        if "assertion" in normalized_heading:
            return "assertion"
        if matches_any(normalized_heading, SUBSERVICE_HEADING_PATTERNS):
            return "subservice"
        if matches_any(normalized_heading, CUEC_HEADING_PATTERNS):
            return "cuec"
        if matches_any(normalized_heading, TESTING_RESULTS_HEADING_PATTERNS) or "test" in normalized_heading or "result" in normalized_heading:
            return "tests_results"
        if matches_any(normalized_heading, CRITERIA_HEADING_PATTERNS):
            return "criteria"
        if "system" in normalized_heading or "description" in normalized_heading:
            return "system_description"

        if "description of tests of controls and results" in lower or matches_any(lower, TESTING_RESULTS_HEADING_PATTERNS):
            return "tests_results"
        if matches_any(lower, CUEC_HEADING_PATTERNS):
            return "cuec"
        if matches_any(lower, SUBSERVICE_HEADING_PATTERNS) or matches_any(lower, CARVEOUT_HEADING_PATTERNS):
            return "subservice"

        return "general"

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        compact = line.strip()
        return len(compact) <= 100 and compact == compact.upper() and len(compact.split()) <= 16

    @staticmethod
    def _should_merge(previous: Section, normalized_heading: str, section_type: str) -> bool:
        if previous.section_type == section_type and previous.normalized_heading == normalized_heading:
            return True

        if normalized_heading == "general" and previous.section_type not in {"general", "table_of_contents"}:
            return True

        if section_type == previous.section_type and section_type not in {"general", "table_of_contents"}:
            return True

        return False
