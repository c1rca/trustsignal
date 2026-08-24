from __future__ import annotations

import re


def _compile(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


OPINION_HEADING_PATTERNS = _compile(
    (
        r"\bindependent\s+service\s+auditor(?:'|’)s\s+report\b",
        r"\bopinion\b",
        r"\bbasis\s+for\s+qualified\s+opinion\b",
    )
)

CRITERIA_HEADING_PATTERNS = _compile(
    (
        r"\btrust\s+services\s+criteria\b",
        r"\breport\s+on\s+controls.*\brelevant\s+to\b",
        r"\bapplicable\s+trust\s+services\s+criteria\b",
        r"\brelevant\s+to\s+security(?:,|\s|$)",
    )
)

SUBSERVICE_HEADING_PATTERNS = _compile(
    (
        r"\bsubservice\s+organization",
        r"\bsubservice\s+organizations\b",
    )
)

CARVEOUT_HEADING_PATTERNS = _compile(
    (
        r"\bcarved[- ]out\b",
        r"\bsubservice\s+organization\s+carved[- ]out\s+controls\b",
        r"\bcarved[- ]out\s+unaffiliated\s+subservice\s+organization\b",
    )
)

CUEC_HEADING_PATTERNS = _compile(
    (
        r"\bcomplementary\s+user\s+entity\s+controls\b",
        r"\buser\s+entity\s+controls(?:\s+and\s+responsibilities)?\b",
        r"\buser\s+control\s+considerations\b",
        r"\bcomplementary\s+controls\s+considerations\b",
        r"\bcomplementary\s+customer\s+controls\b",
        r"\bcustomers?['’]?\s+responsibilities\b",
        r"\bcustomer\s+responsibilities\b",
        r"\buser\s+responsibilities\b",
        r"\buser\s+entity\s+responsibilities\b",
    )
)

TESTING_RESULTS_HEADING_PATTERNS = _compile(
    (
        r"\bdescription\s+of\s+tests\s+of\s+controls\b",
        r"\bresults\s+of\s+tests\b",
        r"\btest\s+results\b",
    )
)


def matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)
