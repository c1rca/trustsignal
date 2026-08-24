from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class PageText:
    page_number: int
    text: str


@dataclass(slots=True)
class Section:
    id: str
    heading: str
    normalized_heading: str
    page_start: int
    page_end: int
    content: str
    section_type: str


@dataclass(slots=True)
class Evidence:
    id: str
    finding_key: str
    page_number: int
    section_heading: str
    quote: str
    rationale: str


@dataclass(slots=True)
class SocReport:
    id: str
    owner_id: str
    filename: str
    stored_path: str
    uploaded_at: datetime
    page_count: int
    pdf_bytes: bytes = b""
    pages: list[PageText] = field(default_factory=list)
    extracted_sections: list[Section] = field(default_factory=list)
