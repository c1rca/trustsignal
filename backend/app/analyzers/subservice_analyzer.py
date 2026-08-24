from __future__ import annotations

import re

from app.domain.models.report import PageText
from app.domain.models.results import SubservicesResult
from app.schemas.analysis_models import EvidenceItem


class SubserviceAnalyzer:
    HEADING_PATTERN = re.compile(
        r"^(?:[A-Z]\.?\s*)?(?:subservice\s+organization(?:s)?|complementary\s+subservice\s+organization\s+controls)\b",
        re.IGNORECASE,
    )

    CONTRACT_PATTERN = re.compile(
        r"contracts\s+with\s+(.+?)\s+for\b",
        re.IGNORECASE,
    )

    TABLE_ORG_LINE = re.compile(
        r"^(Amazon Web Services\s*\(AWS\)|Google(?:\s+LLC)?|Microsoft(?:\s+Corporation)?\s*[–-]\s*Azure(?:\s+including\s+Dynamics\s+365)?|Salesforce(?:,?\s*Inc\.?)?|Atlassian\s+Corporation\s+PLC|Okta,?\s*Inc\.?\s*\(including\s+Auth0\)|Recurly,?\s*Inc\.?|Site-Four,?\s*LLC|Heroku)$",
        re.IGNORECASE,
    )

    GENERIC_ORG_PATTERN = re.compile(
        r"\b([A-Z][A-Za-z0-9&.'()\-]+(?:\s+[A-Z][A-Za-z0-9&.'()\-]+){0,6}(?:\s+(?:LLC|Inc\.?|Ltd\.?|Corporation|Corp\.?|PLC))?)\b"
    )

    NOISE_TOKENS = {
        "subservice organization",
        "subservice organizations",
        "services and applications",
        "controls",
        "none",
        "n/a",
        "not applicable",
        "user entities",
        "matillion",
    }

    SECTION_BOUNDARY = re.compile(
        r"^(?:user\s+control\s+considerations|complementary\s+user\s+entity\s+controls|common\s+control\s+criteria|control\s+environment|information\s+and\s+communication|risk\s+assessment|monitoring\s+activities|trust\s+services\s+criteria|entity\s+level\s+management\s+processes|components\s+of\s+the\s+system)\b",
        re.IGNORECASE,
    )

    PROVIDER_ALIASES: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"amazon\s+web\s+services|\baws\b", re.IGNORECASE), "Amazon Web Services (AWS)"),
        (re.compile(r"\bgoogle\b", re.IGNORECASE), "Google"),
        (
            re.compile(
                r"microsoft\s+corporation\s*[–-]?\s*azure(?:\s+including\s+dynamics\s*365)?|azure\s+including\s+dynamics\s*365",
                re.IGNORECASE,
            ),
            "Microsoft – Azure including Dynamics 365",
        ),
        (re.compile(r"salesforce", re.IGNORECASE), "Salesforce"),
        (re.compile(r"atlassian", re.IGNORECASE), "Atlassian"),
        (re.compile(r"auth0", re.IGNORECASE), "Auth0"),
        (re.compile(r"\bokta\b", re.IGNORECASE), "Okta"),
        (re.compile(r"recurly", re.IGNORECASE), "Recurly"),
        (re.compile(r"site[-\s]?four", re.IGNORECASE), "Site-Four, LLC"),
        (re.compile(r"\bheroku\b", re.IGNORECASE), "Heroku"),
    ]

    INFRA_PROVIDER_NAMES = {
        "Amazon Web Services (AWS)",
        "Google",
        "Microsoft – Azure including Dynamics 365",
        "Heroku",
        "Site-Four, LLC",
    }

    def analyze(self, pages: list[PageText]) -> SubservicesResult:
        names: list[str] = []
        evidence: list[EvidenceItem] = []

        in_subservice_section = False
        subservice_section_start_page = 0
        vendor_context_until_page = 0

        for page in pages:
            page_lower = page.text.lower()
            if "subservice organizations" in page_lower and "vendor" in page_lower:
                vendor_context_until_page = max(vendor_context_until_page, page.page_number + 4)

            lines = [line.strip() for line in page.text.splitlines() if line.strip()]
            for line in lines:
                lower = line.lower()

                if self.HEADING_PATTERN.search(line):
                    # Ignore table-of-contents style heading rows (typically end with page number).
                    if re.search(r"\b\d{1,3}\s*$", line):
                        continue
                    in_subservice_section = True
                    subservice_section_start_page = page.page_number
                    if ":" in line:
                        inline = line.split(":", 1)[1].strip()
                        if inline:
                            candidates = [inline]
                            candidates.extend(self._extract_from_contract_line(inline))
                            candidates.extend(self._extract_aliases(inline, infra_only=False))
                            for candidate in candidates:
                                clean = self._clean_name(candidate)
                                normalized_candidates = clean.split("|") if "|" in clean else [clean]
                                for normalized in normalized_candidates:
                                    if self._is_valid_org(normalized) and normalized not in names:
                                        names.append(normalized)
                                        evidence.append(
                                            EvidenceItem(
                                                finding_key="subservices",
                                                page_number=page.page_number,
                                                quote=line,
                                                rationale="Detected named subservice organization.",
                                            )
                                        )
                    continue

                if in_subservice_section and (
                    self.SECTION_BOUNDARY.search(line)
                    or (subservice_section_start_page and page.page_number - subservice_section_start_page >= 2)
                ):
                    in_subservice_section = False

                if "subservice organizations and vendors" in lower:
                    vendor_context_until_page = page.page_number + 4

                candidates: list[str] = []
                if in_subservice_section:
                    candidates.extend(self._extract_from_subservice_section_line(line))
                    candidates.extend(self._extract_aliases(line, infra_only=False))

                if "subservice" in lower and "contracts with" in lower:
                    candidates.extend(self._extract_from_contract_line(line))
                    candidates.extend(self._extract_aliases(line, infra_only=False))

                if vendor_context_until_page and page.page_number <= vendor_context_until_page:
                    if any(token in lower for token in ("managed", "hosting", "workspace", "oauth", "cloud")):
                        candidates.extend(self._extract_aliases(line, infra_only=True))

                for candidate in candidates:
                    clean = self._clean_name(candidate)
                    normalized_candidates = clean.split("|") if "|" in clean else [clean]
                    for normalized in normalized_candidates:
                        if not self._is_valid_org(normalized):
                            continue
                        if normalized not in names:
                            names.append(normalized)
                            evidence.append(
                                EvidenceItem(
                                    finding_key="subservices",
                                    page_number=page.page_number,
                                    quote=line,
                                    rationale="Detected named subservice organization.",
                                )
                            )

        ordered = self._order_organizations(names)

        return SubservicesResult(
            organizations=ordered,
            confidence="high" if ordered else "low",
            evidence=evidence
            if evidence
            else [
                EvidenceItem(
                    finding_key="subservices",
                    page_number=0,
                    quote="No named subservice organizations detected.",
                    rationale="No reliable named-organization pattern matched.",
                )
            ],
        )

    def _extract_from_subservice_section_line(self, line: str) -> list[str]:
        lowered = line.lower()
        if lowered in self.NOISE_TOKENS:
            return []

        if self.TABLE_ORG_LINE.match(line.strip()):
            return [line.strip()]

        if "contracts with" in lowered:
            return self._extract_from_contract_line(line)

        if "subservice organizations" in lowered and ":" in line:
            after = line.split(":", 1)[1]
            return [after]

        if line.startswith("CC") or line.startswith("TSC"):
            return []

        # Generic bullet/table rows like: "Site-Four, LLC - Data center hosting"
        bullet = line.lstrip("•*- ").strip()
        if " - " in bullet:
            left = bullet.split(" - ", 1)[0].strip()
            if left and self._looks_like_org_label(left):
                return [left]

        return []

    def _extract_from_contract_line(self, line: str) -> list[str]:
        match = self.CONTRACT_PATTERN.search(line)
        if not match:
            return []
        value = match.group(1)
        # Split list connectors while preserving company suffixes like "Inc.".
        raw_parts = re.split(r"\s+(?:and|&)\s+|;", value, flags=re.IGNORECASE)
        return [part.strip(" ,") for part in raw_parts if part.strip(" ,")]

    def _extract_aliases(self, line: str, infra_only: bool) -> list[str]:
        out: list[str] = []
        for pattern, canonical in self.PROVIDER_ALIASES:
            if infra_only and canonical not in self.INFRA_PROVIDER_NAMES:
                continue
            if pattern.search(line):
                out.append(canonical)
        return out

    def _looks_like_org_label(self, text: str) -> bool:
        lowered = text.lower()
        if any(alias.search(text) for alias, _ in self.PROVIDER_ALIASES):
            return True
        if re.search(r"\b(llc|inc\.?|ltd\.?|corp\.?|corporation|plc)\b", lowered):
            return True
        return False

    def _clean_name(self, value: str) -> str:
        clean = re.sub(r"\s+", " ", value).strip(" .,:;\u2013\u2014-")

        if re.search(r"okta", clean, flags=re.IGNORECASE) and re.search(r"auth0", clean, flags=re.IGNORECASE):
            # Keep both providers explicitly represented when grouped in one row.
            return "Okta|Auth0"

        if re.search(r"amazon\s+web\s+services|\baws\b|amazon\s+data\s+centers?", clean, flags=re.IGNORECASE):
            return "Amazon Web Services (AWS)"

        if re.search(r"microsoft", clean, flags=re.IGNORECASE) and re.search(r"azure", clean, flags=re.IGNORECASE):
            return "Microsoft – Azure including Dynamics 365"

        if re.search(r"google", clean, flags=re.IGNORECASE):
            return "Google"

        if re.search(r"salesforce", clean, flags=re.IGNORECASE):
            return "Salesforce"

        if re.search(r"atlassian", clean, flags=re.IGNORECASE):
            return "Atlassian"

        if re.search(r"okta", clean, flags=re.IGNORECASE):
            return "Okta"

        if re.search(r"auth0", clean, flags=re.IGNORECASE):
            return "Auth0"

        if re.search(r"recurly", clean, flags=re.IGNORECASE):
            return "Recurly"

        clean = clean.replace(" - ", " ").replace(" – ", " ")
        clean = re.sub(r"\s*\([^)]*\)$", "", clean).strip()
        return clean

    @staticmethod
    def _order_organizations(names: list[str]) -> list[str]:
        # Preserve first-seen order from the report text for explainability.
        return names

    def _is_valid_org(self, clean: str) -> bool:
        if not clean:
            return False

        lowered = clean.lower()
        if lowered in self.NOISE_TOKENS:
            return False

        if any(token in lowered for token in ("controls", "services and applications", "for the period")):
            return False

        if re.match(r"^section\s+[ivx0-9]+$", clean, flags=re.IGNORECASE):
            return False

        # Reject long clause-like fragments.
        if len(clean.split()) > 8:
            return False

        if not self.GENERIC_ORG_PATTERN.search(clean):
            return False

        return True
