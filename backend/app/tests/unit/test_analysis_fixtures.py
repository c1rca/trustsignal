from io import BytesIO

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.tests.fixtures.soc_snippets import (
    PERIOD_FROM_TO_VENDOR,
    PROVIDER_CARVEOUT,
    QUALIFIED_WITH_EXCEPTION,
    UNQUALIFIED_VENDOR,
)


def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def upload_and_analyze(sample_text: str) -> dict[str, object]:
    client = TestClient(app)
    files = {"file": ("fixture.pdf", BytesIO(make_pdf_bytes(sample_text)), "application/pdf")}
    upload = client.post("/api/reports/upload", files=files)
    report_id = upload.json()["report_id"]
    analyze = client.post(f"/api/reports/{report_id}/analyze")
    assert analyze.status_code == 200
    return analyze.json()


def test_fixture_unqualified_vendor_path() -> None:
    payload = upload_and_analyze(UNQUALIFIED_VENDOR)

    assert payload["executive_snapshot"]["opinion"] in {"unqualified", "unclear"}
    assert payload["ownership"]["ownership_type"] in {"vendor_report", "mixed_or_parent", "unclear"}
    assert payload["exceptions"]["exceptions_detected"] is False


def test_fixture_qualified_exception_path() -> None:
    payload = upload_and_analyze(QUALIFIED_WITH_EXCEPTION)

    assert payload["executive_snapshot"]["opinion"] in {"qualified", "unclear"}
    assert payload["exceptions"]["exceptions_detected"] is True
    assert any(item["key"] == "exceptions" and item["status"] in {"fail", "needs_review"} for item in payload["findings"])


def test_fixture_provider_carveout_path() -> None:
    payload = upload_and_analyze(PROVIDER_CARVEOUT)

    assert payload["carveout"]["method"] in {"carve_out", "unclear"}
    assert payload["ownership"]["ownership_type"] in {"provider_or_subservice_report", "mixed_or_parent", "unclear"}
    assert isinstance(payload["subservices"]["organizations"], list)


def test_fixture_period_from_to_vendor_path() -> None:
    payload = upload_and_analyze(PERIOD_FROM_TO_VENDOR)

    assert payload["executive_snapshot"]["audit_period"] == "2025-01-01 to 2025-12-31"
    assert payload["scope"]["confidence"] in {"high", "medium"}
    assert payload["ownership"]["ownership_type"] in {"vendor_report", "mixed_or_parent", "unclear"}
