from __future__ import annotations

import re

from app.domain.models.report import PageText
from app.domain.models.results import ExceptionsResult
from app.schemas.analysis_models import EvidenceItem


class ExceptionAnalyzer:
    POSITIVE_PATTERNS = (
        re.compile(r"\b(exception|exceptions|deviation|deviations)\s+(was|were)\s+(noted|identified|observed)\b", re.IGNORECASE),
        re.compile(r"\bexception\s+noted\s+by\b", re.IGNORECASE),
        re.compile(r"\bidentified\s+testing\s+exceptions\b", re.IGNORECASE),
    )

    NEGATIVE_PATTERNS = (
        re.compile(r"\bno\s+(exceptions?|deviations?)\s+(noted|identified|observed)\b", re.IGNORECASE),
        re.compile(r"\bwithout\s+(exceptions?|deviations?)\b", re.IGNORECASE),
        re.compile(r"\bnone\s+noted\b", re.IGNORECASE),
    )

    IGNORE_CONTEXT = (
        "auditor responsibilities",
        "management's responsibilities",
        "inherent limitations",
        "description criteria",
        "performing procedures",
        "basis for opinion",
    )

    HEADING_EXCEPTION_PATTERNS = (
        re.compile(r"management['’]?s\s+response\s+to\s+identified\s+testing\s+exceptions", re.IGNORECASE),
        re.compile(r"management['’]?s\s+responses?\s+to\s+exceptions?\s+noted", re.IGNORECASE),
        re.compile(r"identified\s+testing\s+exceptions", re.IGNORECASE),
        re.compile(r"exceptions?\s+noted\s+during\s+testing", re.IGNORECASE),
    )

    def analyze(self, pages: list[PageText]) -> ExceptionsResult:
        positives: list[EvidenceItem] = []
        negatives: list[EvidenceItem] = []
        heading_signals: list[EvidenceItem] = []

        for page in pages:
            compact = re.sub(r"\s+", " ", page.text).strip()
            lower = compact.lower()

            page_in_ignore_context = any(token in lower for token in self.IGNORE_CONTEXT)

            for heading_pattern in self.HEADING_EXCEPTION_PATTERNS:
                for match in heading_pattern.finditer(compact):
                    heading_signals.append(
                        EvidenceItem(
                            finding_key="exceptions",
                            page_number=page.page_number,
                            quote=self._full_sentence(compact, match.start(), match.end()),
                            rationale="Exception-related heading detected; review associated result rows.",
                        )
                    )

            if not page_in_ignore_context:
                for pattern in self.NEGATIVE_PATTERNS:
                    for match in pattern.finditer(compact):
                        negatives.append(
                            EvidenceItem(
                                finding_key="exceptions",
                                page_number=page.page_number,
                                quote=self._full_sentence(compact, match.start(), match.end()),
                                rationale="Results text indicates no exceptions/deviations.",
                            )
                        )

                for pattern in self.POSITIVE_PATTERNS:
                    for match in pattern.finditer(compact):
                        window = compact[max(0, match.start() - 8):match.start()].lower()
                        if "no " in window:
                            continue
                        positives.append(
                            EvidenceItem(
                                finding_key="exceptions",
                                page_number=page.page_number,
                                quote=self._full_sentence(compact, match.start(), match.end()),
                                rationale="Potential test-result exception/deviation identified.",
                            )
                        )

        if positives:
            return ExceptionsResult(exceptions_detected=True, confidence="high", evidence=positives)

        if heading_signals:
            # Exception-specific heading exists; avoid high-confidence "no exceptions" conclusion.
            return ExceptionsResult(
                exceptions_detected=False,
                confidence="low",
                evidence=heading_signals[:3],
            )

        if negatives:
            # Negative phrases confirm absence of exceptions; do not surface them as exception evidence rows.
            return ExceptionsResult(exceptions_detected=False, confidence="high", evidence=[])

        return ExceptionsResult(
            exceptions_detected=False,
            confidence="low",
            evidence=[
                EvidenceItem(
                    finding_key="exceptions",
                    page_number=0,
                    quote="No clear test-results exception statements detected.",
                    rationale="Unable to confirm exceptions from results rows; manual review recommended.",
                )
            ],
        )

    @staticmethod
    def _full_sentence(text: str, start: int, end: int) -> str:
        left = text.rfind(".", 0, start)
        right = text.find(".", end)

        sentence_start = 0 if left == -1 else left + 1
        sentence_end = len(text) if right == -1 else right + 1

        return text[sentence_start:sentence_end].strip()
