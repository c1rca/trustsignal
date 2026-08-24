from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models.report import PageText
from app.domain.models.results import CuecsResult
from app.schemas.analysis_models import EvidenceItem


@dataclass(slots=True)
class _Line:
    page: int
    text: str


class CuecAnalyzer:
    BULLET_START = re.compile(r"^(?:\(?\d+[.)]|[\-–—•*●])\s*(.+)?$")
    STANDALONE_BULLET = re.compile(r"^[\-–—•*●]$")
    LETTERED_START = re.compile(r"^[a-zA-Z][.)]\s+(.+)$")

    RESPONSIBILITY_PATTERNS = (
        "are responsible for",
        "is responsible for",
        "must",
        "should",
        "required to",
        "required",
        "need to",
        "expected to",
        "maintain",
        "notify",
        "provide",
        "review",
        "monitor",
        "implement",
        "ensure",
        "ensuring",
        "develop",
        "determine",
        "comply",
        "adhere",
        "adhering",
        "remove",
        "report",
        "protect",
        "manage",
        "configure",
        "grant",
        "granting",
    )

    HEADING_PATTERNS = (
        re.compile(r"\bcomplementary\s+user\s+entity\s+controls\b", re.IGNORECASE),
        re.compile(r"\bcomplimentary\s+user\s+entity\s+controls\b", re.IGNORECASE),
        re.compile(r"\buser\s+entity\s+controls(?:\s+and\s+responsibilities)?\b", re.IGNORECASE),
        re.compile(r"\buser\s+responsibilities\b", re.IGNORECASE),
        re.compile(r"\buser\s+entity\s+responsibilit(?:y|ies)\b", re.IGNORECASE),
        re.compile(r"\bcontrol\s+responsibilit(?:y|ies).*\buser\s+entities\b", re.IGNORECASE),
        re.compile(r"\bcustomers?['’]?\s+responsibilit(?:y|ies)\b", re.IGNORECASE),
        re.compile(r"\bcomplementary\s+customer\s+controls\b", re.IGNORECASE),
        re.compile(r"\buser\s+control\s+considerations\b", re.IGNORECASE),
        re.compile(r"\bcomplementary\s+controls?\s+at\s+user\s+organizations?\b", re.IGNORECASE),
    )
    PROXIMITY_HEADING_PATTERN = re.compile(
        r"\bcomplement(?:ary|ary\s+controls?|ary\s+controls?\s+at)\b.{0,80}\buser\b.{0,80}\b(control|controls|responsibilit(?:y|ies)|organization|organizations)\b",
        re.IGNORECASE,
    )

    BOUNDARY_HEADING_PATTERNS = (
        re.compile(r"\btrust\s+services\s+criteria\b", re.IGNORECASE),
        re.compile(r"\binformation\s+provided\s+by\s+service\s+auditor\b", re.IGNORECASE),
        re.compile(r"\bcontrol\s+matrix\b", re.IGNORECASE),
        re.compile(r"\bmonitoring\b", re.IGNORECASE),
        re.compile(r"\bsubservice\s+organization\s+controls?\b", re.IGNORECASE),
        re.compile(r"\bdescription\s+of\s+tests\s+of\s+controls\b", re.IGNORECASE),
        re.compile(r"\bresults\s+of\s+tests\b", re.IGNORECASE),
    )

    GENERIC_NOT_CUEC_HEADINGS = {
        "people",
        "procedures",
        "control environment",
        "communication and information",
        "risk assessment",
        "monitoring",
        "control activities",
        "logical and physical access controls",
        "system operations",
        "change management",
        "risk mitigation",
    }

    TEST_LANGUAGE = (
        "no deviations noted",
        "no exceptions noted",
        "inspected",
        "observed",
        "inquiry",
        "reperformed",
        "service auditor",
        "results of tests",
    )

    NON_RESPONSIBILITY_LANGUAGE = (
        "this report is not intended to be",
        "should not be used by anyone other than",
        "specified parties",
        "applicable trust services criteria",
        "risks that may threaten the achievement",
        "service commitments and system requirements",
        "how they may affect the user entity",
        "ability to effectively use the service organization’s services",
        "controls presented below should not be regarded as a comprehensive list",
        "should not be regarded as a comprehensive list",
        "user entity responsibilities are generally",
        "recommended best practice",
        "through legal agreements and instructional material",
    )

    VENDOR_SUBJECT_PREFIXES = (
        "management",
        "the company",
        "the entity",
        "tcwglobal",
        "blink global",
        "with clutch",
        "criteria",
    )

    def analyze(self, pages: list[PageText]) -> CuecsResult:
        toc_pages = {page.page_number for page in pages if "table of contents" in page.text.lower()}
        lines = self._flatten_lines(pages)
        section, heading, heading_page = self._slice_cuec_section(lines, toc_pages=toc_pages)
        heading_lower = heading.lower()
        implied_customer_actor = (
            "responsibilit" in heading_lower
            or "user control considerations" in heading_lower
            or "complementary user entity controls" in heading_lower
            or "complementary customer controls" in heading_lower
            or "complementary controls at user organizations" in heading_lower
        )

        if not section:
            reference = self._find_cuec_reference(pages)
            if reference is not None:
                page_number, quote = reference
                return CuecsResult(
                    responsibilities=[],
                    confidence="medium",
                    present=True,
                    mode="referenced_not_listed",
                    count=0,
                    needs_review=True,
                    evidence=[
                        EvidenceItem(
                            finding_key="cuecs",
                            page_number=page_number,
                            quote=quote,
                            rationale="CUEC language is referenced, but no explicit user-responsibility list was extracted.",
                        )
                    ],
                )

            return CuecsResult(
                responsibilities=[],
                confidence="low",
                present=False,
                mode="not_found",
                count=0,
                needs_review=False,
                evidence=[
                    EvidenceItem(
                        finding_key="cuecs",
                        page_number=0,
                        quote="No CUEC/customer-responsibility section was detected.",
                        rationale="Customer responsibilities may require manual review.",
                    )
                ],
            )

        section_text = " ".join(line.text.lower() for line in section)
        if any(
            phrase in section_text
            for phrase in (
                "complementary user entity controls are not required",
                "cuecs are not required",
                "no controls at the user entity",
                "complementary controls at user organizations are not required",
            )
        ):
            return CuecsResult(
                responsibilities=[],
                confidence="high",
                present=False,
                mode="not_required",
                count=0,
                needs_review=False,
                evidence=[
                    EvidenceItem(
                        finding_key="cuecs",
                        page_number=section[0].page,
                        quote="CUEC language indicates complementary user entity controls are not required.",
                        rationale="Detected explicit no-CUEC-required statement.",
                    )
                ],
            )

        # Parse primarily from the detected evidence page and the page immediately after,
        # while still staying inside the bounded CUEC section.
        scoped_section = self._scope_section_to_anchor_window(section, heading_page)

        structured_items, list_mode = self._extract_structured_items(
            scoped_section,
            implied_customer_actor=implied_customer_actor,
        )
        normalized_items = self._normalize_items(structured_items)

        if self._fails_sanity_checks(normalized_items):
            normalized_items = []

        if not normalized_items:
            table_items = self._extract_table_items(scoped_section, implied_customer_actor=implied_customer_actor)
            normalized_items = self._normalize_items(table_items)
            if normalized_items:
                list_mode = "structured_table"

        anchored_items = self._normalize_items(self._extract_anchor_responsibilities(lines, toc_pages=toc_pages))
        if anchored_items:
            merged = self._normalize_items([*normalized_items, *anchored_items])
            if merged:
                normalized_items = merged
                if list_mode == "narrative":
                    list_mode = "structured_anchored"

        if normalized_items:
            normalized_items = normalized_items[:30]
            extracted_count = len(normalized_items)
            confidence = "high" if extracted_count >= 3 else "medium"
            bullet_markers = sum(
                1
                for line in scoped_section
                if self.BULLET_START.match(line.text) or self.STANDALONE_BULLET.match(line.text)
            )
            suspicious_low_count = extracted_count <= 2
            suspicious_sparse_vs_markers = bullet_markers >= 6 and extracted_count <= (bullet_markers - 2)
            return CuecsResult(
                responsibilities=normalized_items,
                confidence=confidence,
                present=True,
                mode=list_mode,
                count=extracted_count,
                needs_review=suspicious_low_count or suspicious_sparse_vs_markers,
                evidence=[
                    EvidenceItem(
                        finding_key="cuecs",
                        page_number=section[0].page,
                        quote=item,
                        rationale="Extracted customer responsibility from bounded CUEC/customer-responsibility section.",
                    )
                    for item in normalized_items
                ],
            )

        # Deliberately avoid narrative-only extraction for CUECs;
        # require list/table evidence to reduce false positives.
        return CuecsResult(
            responsibilities=[],
            confidence="low",
            present=True,
            mode="narrative",
            count=None,
            needs_review=True,
            evidence=[
                EvidenceItem(
                    finding_key="cuecs",
                    page_number=section[0].page,
                    quote="CUEC/customer-responsibility heading detected but no extractable responsibilities found.",
                    rationale="Manual review required for customer responsibilities.",
                )
            ],
        )

    def _flatten_lines(self, pages: list[PageText]) -> list[_Line]:
        lines: list[_Line] = []
        for page in pages:
            for raw in page.text.splitlines():
                text = raw.replace('\u00a0', ' ').replace('\u202f', ' ').strip()
                if text:
                    lines.append(_Line(page=page.page_number, text=text))
        return lines

    def _slice_cuec_section(self, lines: list[_Line], *, toc_pages: set[int]) -> tuple[list[_Line], str, int]:
        candidates: list[tuple[int, int, str, list[_Line]]] = []

        for idx, line in enumerate(lines):
            if line.page in toc_pages:
                continue
            if not self._is_valid_heading(line.text):
                continue

            section: list[_Line] = []
            for j in range(idx + 1, len(lines)):
                candidate_line = lines[j]
                if self._is_boundary(candidate_line.text):
                    break
                section.append(candidate_line)

            score = self._score_section(line.text, section)
            candidates.append((score, line.page, line.text, section))

        if not candidates:
            return [], "", 0

        # Prefer strongest customer-responsibility section; tie-break by longer section.
        candidates.sort(key=lambda item: (item[0], len(item[3])), reverse=True)
        best = candidates[0]

        best_score, best_page, best_heading, best_section = best
        heading_lower = best_heading.lower()
        explicit_customer_heading = any(
            token in heading_lower
            for token in ("user entity", "user control", "customer", "responsibilit")
        )
        if best_score < 3 and not explicit_customer_heading:
            return [], "", 0

        return best_section, best_heading, best_page

    def _scope_section_to_anchor_window(self, section: list[_Line], heading_page: int) -> list[_Line]:
        if not section or heading_page <= 0:
            return section

        max_page = heading_page + 1
        scoped = [line for line in section if heading_page <= line.page <= max_page]
        return scoped or section

    def _is_valid_heading(self, line: str) -> bool:
        lower = line.lower().strip()
        if lower in self.GENERIC_NOT_CUEC_HEADINGS:
            return False
        if self._looks_like_toc_entry(line):
            return False
        matches = [pattern.search(line) for pattern in self.HEADING_PATTERNS]
        proximity_match = self.PROXIMITY_HEADING_PATTERN.search(line)
        if not any(matches) and not proximity_match:
            return False

        earliest = min((m.start() for m in matches if m), default=999)
        if proximity_match:
            earliest = min(earliest, proximity_match.start())
        starts_with_heading = earliest <= 5

        words = line.strip().split()
        if not starts_with_heading:
            if len(words) > 10:
                return False
            if len(line.strip()) > 90:
                return False
            if line.strip().endswith("."):
                return False

        lowered = f" {lower} "
        if any(token in lowered for token in (" are ", " were ", " that ", " along with ", "description indicates")):
            return False

        # Avoid misclassifying subservice-control headings as customer CUECs.
        has_subservice_token = any(token in lowered for token in (" subservice ", " sub-service ", " subservice organization "))
        has_customer_token = any(token in lowered for token in (" user entity ", " customer ", " user control ", " user responsibilities "))
        if has_subservice_token and not has_customer_token:
            return False

        return self._looks_like_heading(line) or len(words) <= 8

    def _score_section(self, heading: str, section: list[_Line]) -> int:
        heading_lower = heading.lower()
        text = " ".join(line.text.lower() for line in section[:120])

        score = 0
        if "customers" in heading_lower or "responsibilit" in heading_lower:
            score += 8
        if "cuec" in heading_lower:
            score += 4
        if "service auditor" in heading_lower:
            score -= 6
        if "management assertion" in heading_lower:
            score -= 6
        if "subservice" in heading_lower and not any(token in heading_lower for token in ("user", "customer")):
            score -= 10

        score += sum(1 for line in section if self.BULLET_START.match(line.text) or self.STANDALONE_BULLET.match(line.text)) * 2
        score += sum(1 for token in ("customer", "user entity", "users") if token in text) * 2
        score += sum(1 for token in ("responsible", "must", "required", "should") if token in text)

        if "no controls at the user entity" in text or "cuecs are not required" in text:
            score -= 4

        return score

    def _is_boundary(self, line: str) -> bool:
        # Another CUEC-family heading is treated as an in-section subheading, not a boundary.
        if self._is_valid_heading(line):
            return False

        lower = line.lower()
        words = line.strip().split()
        if re.match(r"^(?:section\s+)?\d+(?:\.\d+)*\s+", lower):
            return True
        if re.match(r"^[ivxlcdm]+\.\s*$", lower):
            return True

        if self._looks_like_heading(line):
            if any(pattern.search(lower) for pattern in self.BOUNDARY_HEADING_PATTERNS):
                return True

        return False

    def _extract_structured_items(self, section: list[_Line], *, implied_customer_actor: bool) -> tuple[list[str], str]:
        items: list[str] = []
        current: str | None = None

        numbered_hits = 0
        bullet_hits = 0

        def flush() -> None:
            nonlocal current
            if not current:
                return
            candidate = self._normalize_text(current)
            if self._is_valid_responsibility(candidate, implied_customer_actor=implied_customer_actor):
                items.append(candidate)
            current = None

        expecting_bullet_payload = False

        for line in section:
            text = line.text

            if self.STANDALONE_BULLET.match(text):
                flush()
                expecting_bullet_payload = True
                bullet_hits += 1
                continue

            if expecting_bullet_payload:
                expecting_bullet_payload = False
                current = text.strip()
                continue

            numbered_or_bullet = self.BULLET_START.match(text)
            if numbered_or_bullet:
                prefix = text[0]
                if prefix.isdigit() or (prefix == "(" and len(text) > 1 and text[1].isdigit()):
                    numbered_hits += 1
                else:
                    bullet_hits += 1

                flush()
                payload = (numbered_or_bullet.group(1) or "").strip()
                current = payload
                continue

            # lettered lists are accepted only if they are responsibility-bearing
            lettered = self.LETTERED_START.match(text)
            if lettered:
                flush()
                current = lettered.group(1).strip()
                continue

            if current is not None:
                if self._looks_like_heading(text):
                    flush()
                    break
                current = f"{current} {text}".strip()
                continue

        flush()

        mode = "structured_numbered" if numbered_hits >= bullet_hits and numbered_hits > 0 else "structured_bulleted"
        return items, mode

    def _is_valid_responsibility(self, text: str, *, implied_customer_actor: bool = False) -> bool:
        lower = text.lower()

        if lower.strip() in {"user entity responsibilities", "complementary user entity controls"}:
            return False

        if lower.startswith("user entity responsibilities"):
            return False

        if "responsibilities should be considered by user entities" in lower:
            return False
        if "control responsibilities to be considered by user entities" in lower:
            return False

        if text.strip().endswith(":"):
            return False

        if any(token in lower for token in self.TEST_LANGUAGE):
            return False

        if any(token in lower for token in self.NON_RESPONSIBILITY_LANGUAGE):
            return False

        if any(lower.startswith(prefix) for prefix in self.VENDOR_SUBJECT_PREFIXES):
            return False

        has_actor = any(
            actor in lower
            for actor in (
                "customer",
                "customers",
                "user entity",
                "user entities",
                "user organization",
                "users",
                "client",
                "organization",
                "administrators",
            )
        )
        has_obligation = any(pattern in lower for pattern in self.RESPONSIBILITY_PATTERNS)

        if not has_obligation:
            if not implied_customer_actor:
                return False
            # In a clearly-scoped user-responsibility section, keep substantive bullets
            # even if they are short noun-phrase controls.
            if len(lower) < 20:
                return False
            if text and text[0].islower():
                return False

        if not has_actor and not implied_customer_actor:
            return False

        # Avoid org chart/team descriptions.
        if any(token in lower for token in ("department", "team", "legal and compliance", "client and employee services")):
            return False

        if "no controls at the user entity" in lower or "cuecs are not required" in lower:
            return False

        return True

    def _extract_table_items(self, section: list[_Line], *, implied_customer_actor: bool) -> list[str]:
        items: list[str] = []
        for line in section:
            text = line.text.strip()
            lower = text.lower()

            if any(token in lower for token in ("user entity responsibilities", "user entity controls", "complementary user entity controls", "complimentary user entity controls")):
                continue

            candidates: list[str] = []
            if "|" in text:
                candidates.extend([part.strip() for part in text.split("|") if part.strip()])
            if re.search(r"\s{2,}", text):
                candidates.extend([part.strip() for part in re.split(r"\s{2,}", text) if part.strip()])
            if not candidates:
                candidates = [text]

            # Usually responsibility text is in the right-most table column.
            for candidate in sorted(candidates, key=len, reverse=True):
                lowered = candidate.lower().strip()
                if not (
                    lowered.startswith("user entity is responsible")
                    or lowered.startswith("customers are responsible")
                    or lowered.startswith("customer is responsible")
                    or lowered.startswith("user entities are responsible")
                ):
                    continue

                # Table extraction is stricter: require explicit customer/user actor to avoid false positives.
                if self._is_valid_responsibility(candidate, implied_customer_actor=False):
                    items.append(candidate)
                    break

        return items[:40]

    def _extract_anchor_responsibilities(self, lines: list[_Line], *, toc_pages: set[int]) -> list[str]:
        anchor_patterns = (
            re.compile(r"\buser\s+entity\s+responsibilit(?:y|ies)\b", re.IGNORECASE),
            re.compile(r"\buser\s+entities\s+are\s+responsible\s+for\b", re.IGNORECASE),
            re.compile(r"\buser\s+entity\s+is\s+responsible\s+for\b", re.IGNORECASE),
        )
        stop_patterns = (
            re.compile(r"\bnon[-\s]?applicable\s+trust\s+services\s+criteria\b", re.IGNORECASE),
            re.compile(r"^\d+\s+non[-\s]?applicable\b", re.IGNORECASE),
            re.compile(r"\bdescription\s+of\s+criteria,?\s+controls\b", re.IGNORECASE),
        )

        items: list[str] = []
        in_anchor_region = False
        window = 0
        current: str | None = None

        def flush_current() -> None:
            nonlocal current
            if not current:
                return
            candidate = self._normalize_text(current)
            if self._is_valid_responsibility(candidate, implied_customer_actor=True):
                items.append(candidate)
            current = None

        for line in lines:
            if line.page in toc_pages:
                continue

            text = line.text.strip()
            lower = text.lower()

            if self._looks_like_toc_entry(text):
                continue

            if any(p.search(text) for p in anchor_patterns):
                in_anchor_region = True
                window = 0

            if not in_anchor_region:
                continue

            if any(p.search(text) for p in stop_patterns):
                flush_current()
                in_anchor_region = False
                continue

            window += 1
            if window > 220:
                flush_current()
                in_anchor_region = False
                continue

            # Ignore common table criteria-only cells.
            if re.fullmatch(r"[A-Z]{2}\d(?:\.\d+)?(?:\s*,\s*[A-Z]{2}\d(?:\.\d+)?)*", text):
                continue

            normalized_lower = re.sub(r"^(?:\(?\d+[.)]?|[a-zA-Z][.)]|[\-–—•*●])\s*", "", lower)
            starts_with_user_actor = normalized_lower.startswith("user entities ") or normalized_lower.startswith("user entity ")
            starts_with_responsibility_phrase = (
                normalized_lower.startswith("user entities are responsible for")
                or normalized_lower.startswith("user entity is responsible for")
                or normalized_lower.startswith("it is the responsibility of the user entity")
            )

            if starts_with_responsibility_phrase or starts_with_user_actor:
                flush_current()
                current = re.sub(r"^(?:\(?\d+[.)]?|[a-zA-Z][.)]|[\-–—•*●])\s*", "", text).strip()
                continue

            if current is not None:
                # Stop appending on obvious section/heading boundaries.
                if self._is_boundary(text):
                    flush_current()
                    break

                # Continue wrapped row text.
                current = f"{current} {text}".strip()

        flush_current()
        return items[:40]

    def _extract_narrative_items(self, section: list[_Line], *, implied_customer_actor: bool) -> list[str]:
        joined = " ".join(line.text for line in section)
        sentences = re.split(r"(?<=[.!?])\s+", joined)
        items: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            clean = self._normalize_text(sentence)
            if not self._is_valid_responsibility(clean, implied_customer_actor=implied_customer_actor):
                continue
            key = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
            if key in seen:
                continue
            seen.add(key)
            items.append(clean)
        return items[:30]

    def _fails_sanity_checks(self, items: list[str]) -> bool:
        if not items:
            return False

        test_language_count = sum(1 for item in items if any(token in item.lower() for token in self.TEST_LANGUAGE))
        if test_language_count:
            return True

        vendor_subject_count = sum(1 for item in items if any(item.lower().startswith(prefix) for prefix in self.VENDOR_SUBJECT_PREFIXES))
        if vendor_subject_count / len(items) > 0.5:
            return True

        return False

    def _normalize_items(self, items: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for item in items:
            clean = self._normalize_text(item)
            clean = re.sub(r"^(?:\(?\d+[.)]|[a-zA-Z][.)]|[\-•*●])\s*", "", clean)
            key = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
            if not clean or key in seen:
                continue

            # If one entry is just a truncated prefix of another, keep the longer one.
            replaced = False
            for idx, existing in enumerate(normalized):
                if existing.startswith(clean) and len(existing) - len(clean) >= 20:
                    replaced = True
                    break
                if clean.startswith(existing) and len(clean) - len(existing) >= 20:
                    normalized[idx] = clean
                    seen.add(key)
                    replaced = True
                    break
            if replaced:
                continue

            seen.add(key)
            normalized.append(clean)

        return normalized

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip(" -–—•*●")

        # If OCR/table parsing accidentally merges multiple bullets, keep only the first bullet phrase.
        normalized = re.split(r"\s+[•●]\s+", normalized, maxsplit=1)[0].strip()

        # Trim at common report footer/disclaimer boundaries that are not CUEC responsibilities.
        normalized = re.sub(r"\bThis\s+report\s+is\s+not\s+intended\s+to\s+be\b.*$", "", normalized, flags=re.IGNORECASE).strip()
        normalized = re.sub(r"\bshould\s+not\s+be\s+used\s+by\s+anyone\s+other\s+than\b.*$", "", normalized, flags=re.IGNORECASE).strip()
        normalized = re.sub(r"\bSan\s+Jose,\s+California\b.*$", "", normalized, flags=re.IGNORECASE).strip()

        normalized = re.sub(r"\b\d+\s+Section\s+[IVXLC]+\b.*$", "", normalized, flags=re.IGNORECASE).strip()
        normalized = re.sub(r"\bDescription\s+of\s+the\s+System\s+Provided\s+by\b.*$", "", normalized, flags=re.IGNORECASE).strip()
        normalized = re.sub(r"\b\d+\s*/\s*\d+\b\s*$", "", normalized).strip()
        normalized = re.sub(r"\s+\d+\s*$", "", normalized).strip()
        normalized = re.sub(r"\s+[A-Za-z0-9&._-]+\s*\|\s*$", "", normalized).strip()
        normalized = normalized.replace(" .", ".")
        return normalized

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        text = line.strip()
        if not text:
            return False
        if len(text) > 120:
            return False
        if text.endswith((".", ",", ";", ":")):
            return False
        words = text.split()
        if len(words) > 16:
            return False
        if len(words) == 1 and not text.isupper():
            return False
        if text == text.upper():
            return True
        if text.istitle() and len(words) <= 12:
            return True
        return False

    @staticmethod
    def _looks_like_toc_entry(line: str) -> bool:
        compact = line.strip()
        if re.search(r"(?:\.{3,}|_{3,})\s*\d+\s*$", compact):
            return True
        if re.search(r"\.{3,}\s*$", compact):
            return True
        return bool(re.search(r"\s\d+\s*$", compact) and "contents" in compact.lower())

    def _find_cuec_reference(self, pages: list[PageText]) -> tuple[int, str] | None:
        pattern = re.compile(r"complementary\s+user\s+entity\s+controls?", re.IGNORECASE)
        for page in pages:
            match = pattern.search(page.text)
            if not match:
                continue
            quote = self._snippet(page.text, match.start(), match.end())
            return page.page_number, quote
        return None

    @staticmethod
    def _snippet(text: str, start: int, end: int, radius: int = 180) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        return re.sub(r"\s+", " ", text[left:right]).strip()
