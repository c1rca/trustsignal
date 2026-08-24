from io import BytesIO

import fitz
from fastapi.testclient import TestClient

from app.main import app


def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_analyze_report_and_get_cached_analysis() -> None:
    client = TestClient(app)

    sample_text = (
        "INDEPENDENT SERVICE AUDITOR'S REPORT\n"
        "In our opinion, the description presents fairly.\n"
        "The period from February 1, 2025 through September 19, 2025 was examined.\n"
        "Criteria covered include Security and Availability."
    )

    files = {"file": ("soc2.pdf", BytesIO(make_pdf_bytes(sample_text)), "application/pdf")}
    upload_response = client.post("/api/reports/upload", files=files)
    report_id = upload_response.json()["report_id"]

    analyze_response = client.post(f"/api/reports/{report_id}/analyze")
    assert analyze_response.status_code == 200
    payload = analyze_response.json()

    assert payload["executive_snapshot"]["opinion"] in {"unqualified", "qualified", "unclear"}
    assert isinstance(payload["executive_snapshot"]["criteria_covered"], list)
    assert isinstance(payload["evidence_index"], list)
    assert len(payload["evidence_index"]) >= 1
    assert isinstance(payload["findings"], list)
    assert {finding["key"] for finding in payload["findings"]} == {
        "opinion",
        "scope",
        "criteria",
        "ownership",
        "carveout",
        "exceptions",
    }
    assert all(finding["status"] in {"pass", "fail", "needs_review"} for finding in payload["findings"])
    assert all(finding["confidence"] in {"low", "medium", "high"} for finding in payload["findings"])
    assert all(isinstance(finding["review_required"], bool) for finding in payload["findings"])
    assert all("review_reason" in finding for finding in payload["findings"])
    assert "review_summary" in payload
    assert "status_counts" in payload["review_summary"]
    assert payload["review_summary"]["total_findings"] == 6
    assert "evidence_by_finding" in payload
    assert "reviewer_takeaway" in payload
    assert "ownership" in payload
    assert "subservices" in payload
    assert "carveout" in payload
    assert "cuecs" in payload
    assert "exceptions" in payload

    cached_response = client.get(f"/api/reports/{report_id}/analysis")
    assert cached_response.status_code == 200

    export_response = client.get(f"/api/reports/{report_id}/analysis/export-pdf")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("application/pdf")
