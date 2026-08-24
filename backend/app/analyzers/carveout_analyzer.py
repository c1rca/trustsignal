from __future__ import annotations

import re

from app.domain.models.report import PageText
from app.domain.models.results import CarveoutResult
from app.schemas.analysis_models import EvidenceItem


class CarveOutAnalyzer:
    CARVE_OUT_SIGNALS = (
        re.compile(r"\bcarve[- ]out\b", re.IGNORECASE),
        re.compile(r"carved[- ]out\s+unaffiliated\s+subservice\s+organization", re.IGNORECASE),
        re.compile(r"subservice\s+organization\s+carved[- ]out\s+controls", re.IGNORECASE),
        re.compile(r"does\s+not\s+disclose\s+the\s+actual\s+controls", re.IGNORECASE),
        re.compile(r"did\s+not\s+include\s+the\s+services\s+provided\s+by\s+the\s+subservice", re.IGNORECASE),
        re.compile(r"have\s+not\s+evaluated\s+the\s+(?:suitability\s+of\s+the\s+design\s+or\s+)?operating\s+effectiveness\s+of\s+such\s+complementary\s+subservice\s+organization\s+controls", re.IGNORECASE),
        re.compile(r"does\s+not\s+include\s+the\s+data\s+center\s+hosting\s+services\s+provided\s+by", re.IGNORECASE),
    )
    INCLUSIVE_SIGNALS = (
        re.compile(r"\binclusive\s+method\b", re.IGNORECASE),
        re.compile(r"includes\s+the\s+controls\s+at\s+the\s+subservice\s+organization", re.IGNORECASE),
    )

    def analyze(self, pages: list[PageText]) -> CarveoutResult:
        carveout_evidence: list[EvidenceItem] = []
        inclusive_evidence: list[EvidenceItem] = []

        for page in pages:
            compact = re.sub(r"\s+", " ", page.text).strip()
            for pattern in self.CARVE_OUT_SIGNALS:
                match = pattern.search(compact)
                if not match:
                    continue
                carveout_evidence.append(
                    EvidenceItem(
                        finding_key="carveout",
                        page_number=page.page_number,
                        quote=self._snippet(compact, match.start(), match.end()),
                        rationale="Carve-out treatment signal detected for subservice organization.",
                    )
                )

            for pattern in self.INCLUSIVE_SIGNALS:
                match = pattern.search(compact)
                if not match:
                    continue
                inclusive_evidence.append(
                    EvidenceItem(
                        finding_key="carveout",
                        page_number=page.page_number,
                        quote=self._snippet(compact, match.start(), match.end()),
                        rationale="Inclusive-method signal detected for subservice organization.",
                    )
                )

        if any("carve-out" in item.quote.lower() or "carve out" in item.quote.lower() for item in carveout_evidence):
            return CarveoutResult(method="carve_out", confidence="high", evidence=carveout_evidence[:6])

        if len(carveout_evidence) >= 2:
            return CarveoutResult(method="carve_out", confidence="high", evidence=carveout_evidence[:6])

        if carveout_evidence:
            return CarveoutResult(method="carve_out", confidence="medium", evidence=carveout_evidence[:4])

        if inclusive_evidence:
            confidence = "high" if len(inclusive_evidence) >= 2 else "medium"
            return CarveoutResult(method="inclusive", confidence=confidence, evidence=inclusive_evidence[:6])

        return CarveoutResult(
            method="unclear",
            confidence="low",
            evidence=[
                EvidenceItem(
                    finding_key="carveout",
                    page_number=0,
                    quote="No carve-out/inclusive method language detected.",
                    rationale="Method should be manually verified.",
                )
            ],
        )

    @staticmethod
    def _snippet(text: str, start: int, end: int) -> str:
        left_dot = text.rfind('.', 0, start)
        right_dot = text.find('.', end)

        left = 0 if left_dot == -1 else left_dot + 1
        right = len(text) if right_dot == -1 else right_dot + 1

        return text[left:right].strip()
