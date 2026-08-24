from __future__ import annotations

import re

from app.domain.models.results import OpinionResult
from app.domain.models.report import PageText
from app.schemas.analysis_models import EvidenceItem


class OpinionAnalyzer:
    QUALIFIED_TOKENS = ("qualified opinion", "basis for qualified opinion")
    ADVERSE_TOKENS = ("adverse opinion",)
    DISCLAIMER_TOKENS = ("disclaimer of opinion",)

    def analyze(self, pages: list[PageText]) -> OpinionResult:
        diagnostics: list[str] = []
        candidate_pages = self._candidate_pages(pages)

        best_unqualified: tuple[int, int, str] | None = None

        for page in candidate_pages:
            text = page.text
            lower = text.lower()

            for token in self.DISCLAIMER_TOKENS:
                if token in lower:
                    return OpinionResult(
                        opinion_type="disclaimer",
                        confidence="high",
                        page_number=page.page_number,
                        evidence=[self._evidence(page.page_number, text, token, "Explicit disclaimer opinion language detected.")],
                        diagnostics=["hard-match: disclaimer token"],
                    )

            for token in self.ADVERSE_TOKENS:
                if token in lower:
                    return OpinionResult(
                        opinion_type="adverse",
                        confidence="high",
                        page_number=page.page_number,
                        evidence=[self._evidence(page.page_number, text, token, "Explicit adverse opinion language detected.")],
                        diagnostics=["hard-match: adverse token"],
                    )

            for token in self.QUALIFIED_TOKENS:
                if token in lower:
                    return OpinionResult(
                        opinion_type="qualified",
                        confidence="high" if token == "qualified opinion" else "medium",
                        page_number=page.page_number,
                        evidence=[self._evidence(page.page_number, text, token, "Qualification language detected in opinion section.")],
                        diagnostics=[f"hard-match: {token}"],
                    )

            score, notes = self._score_unqualified_signal(lower)
            if "\nopinion" in lower or lower.strip().startswith("opinion"):
                score += 1
                notes.append("opinion-heading")
            if score >= 4:
                snippet_token = self._best_token(lower)
                snippet = self._opinion_block_snippet(text, snippet_token) or self._opinion_block_snippet(text, "in our opinion")
                confidence = "high" if score >= 6 else "medium"
                if best_unqualified is None or score > best_unqualified[0]:
                    best_unqualified = (score, page.page_number, snippet)
                diagnostics.extend([f"p{page.page_number}:{note}" for note in notes])

        if best_unqualified is not None:
            score, page_number, snippet = best_unqualified
            return OpinionResult(
                opinion_type="unqualified",
                confidence="high" if score >= 6 else "medium",
                page_number=page_number,
                evidence=[
                    EvidenceItem(
                        finding_key="opinion",
                        page_number=page_number,
                        quote=snippet or "unqualified opinion indicators",
                        rationale="Weighted opinion signals indicate an unqualified conclusion.",
                    )
                ],
                diagnostics=diagnostics[:8],
            )

        diagnostics.append("no sufficient weighted opinion signals found")
        return OpinionResult(
            opinion_type="unclear",
            confidence="low",
            page_number=0,
            evidence=[
                EvidenceItem(
                    finding_key="opinion",
                    page_number=0,
                    quote="No clear opinion statement detected.",
                    rationale="No recognized opinion-language pattern with sufficient confidence.",
                )
            ],
            diagnostics=diagnostics,
        )

    def _candidate_pages(self, pages: list[PageText]) -> list[PageText]:
        prioritized: list[PageText] = []
        remainder: list[PageText] = []

        for page in pages:
            lower = page.text.lower()
            if (
                "independent service auditor" in lower
                or "opinion" in lower
                or "basis for qualified opinion" in lower
            ):
                prioritized.append(page)
            else:
                remainder.append(page)

        return prioritized + remainder

    def _score_unqualified_signal(self, lower: str) -> tuple[int, list[str]]:
        score = 0
        notes: list[str] = []

        if "in our opinion" in lower:
            score += 3
            notes.append("in-our-opinion")

        if "presents fairly" in lower or "fairly presented" in lower:
            score += 2
            notes.append("fair-presentation")

        if "in all material respects" in lower:
            score += 2
            notes.append("material-respects")

        if "description is fairly presented" in lower:
            score += 2
            notes.append("description-fairly-presented")

        if "independent service auditor" in lower or "service auditor" in lower:
            score += 2
            notes.append("auditor-context")

        if "basis for our opinion" in lower:
            score += 2
            notes.append("basis-for-our-opinion")

        if "type ii" in lower:
            score += 1
            notes.append("type-ii-context")

        if "service organization" in lower:
            score += 1
            notes.append("service-organization-context")

        if "the description presents" in lower:
            score += 1
            notes.append("description-presents")

        if "reasonable assurance about whether" in lower:
            score += 1
            notes.append("reasonable-assurance-clause")

        return score, notes

    @staticmethod
    def _best_token(lower: str) -> str:
        if "in all material respects" in lower:
            return "in all material respects"
        if "presents fairly" in lower:
            return "presents fairly"
        if "fairly presented" in lower:
            return "fairly presented"
        return "in our opinion"

    @staticmethod
    def _evidence(page_number: int, text: str, token: str, rationale: str) -> EvidenceItem:
        return EvidenceItem(
            finding_key="opinion",
            page_number=page_number,
            quote=OpinionAnalyzer._opinion_block_snippet(text, token) or token,
            rationale=rationale,
        )

    @staticmethod
    def _opinion_block_snippet(text: str, needle: str) -> str:
        lower = text.lower()
        index = lower.find(needle.lower())
        if index == -1:
            return ""

        opinion_heading_idx = lower.rfind("opinion", 0, index + 1)
        block_start = opinion_heading_idx if opinion_heading_idx != -1 else max(0, index - 140)

        next_heading = re.search(
            r"\n\s*(?:basis for qualified opinion|management's assertion|description of the system|description of tests of controls|assertion)\b",
            text[block_start:],
            flags=re.IGNORECASE,
        )
        if next_heading:
            block_end = block_start + next_heading.start()
        else:
            # No downstream heading found: keep the remainder of the page block
            # so evidence is not cut mid-sentence.
            block_end = len(text)

        snippet = re.sub(r"\s+", " ", text[block_start:block_end]).strip()
        return snippet
