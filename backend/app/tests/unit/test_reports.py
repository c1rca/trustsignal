from io import BytesIO

import fitz
from fastapi.testclient import TestClient

from app.main import app


def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_upload_report_and_fetch_metadata() -> None:
    client = TestClient(app)

    pdf_bytes = make_pdf_bytes("SOC 2 report sample")
    files = {"file": ("sample.pdf", BytesIO(pdf_bytes), "application/pdf")}

    upload_response = client.post("/api/reports/upload", files=files)
    assert upload_response.status_code == 200

    payload = upload_response.json()
    assert payload["filename"] == "sample.pdf"
    assert payload["page_count"] == 1
    assert payload["report_id"]

    report_id = payload["report_id"]
    metadata_response = client.get(f"/api/reports/{report_id}")
    assert metadata_response.status_code == 200

    sections_response = client.get(f"/api/reports/{report_id}/sections")
    assert sections_response.status_code == 200
    sections = sections_response.json()
    assert len(sections) == 1
    assert sections[0]["section_type"] in {
        "general",
        "cover",
        "table_of_contents",
        "opinion",
        "criteria",
        "subservice",
        "cuec",
        "tests",
        "tests_results",
        "auditor_report",
        "system_description",
    }

    file_response = client.get(f"/api/reports/{report_id}/file")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "application/pdf"


def test_upload_rejects_non_pdf() -> None:
    client = TestClient(app)

    files = {"file": ("sample.txt", BytesIO(b"not-pdf"), "text/plain")}
    response = client.post("/api/reports/upload", files=files)

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are accepted"
