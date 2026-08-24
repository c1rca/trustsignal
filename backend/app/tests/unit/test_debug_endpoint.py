from io import BytesIO

import fitz
from fastapi.testclient import TestClient

from app.main import app


def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_debug_endpoint_returns_sections_and_analysis_flags() -> None:
    client = TestClient(app)

    files = {
        "file": (
            "debug.pdf",
            BytesIO(make_pdf_bytes("INDEPENDENT SERVICE AUDITOR'S REPORT\nIn our opinion, the description presents fairly.")),
            "application/pdf",
        )
    }

    upload_response = client.post("/api/reports/upload", files=files)
    report_id = upload_response.json()["report_id"]

    debug_before = client.get(f"/api/reports/{report_id}/debug")
    assert debug_before.status_code == 200
    payload_before = debug_before.json()
    assert payload_before["analysis_available"] is False
    assert isinstance(payload_before["sections"], list)

    analyze_response = client.post(f"/api/reports/{report_id}/analyze")
    assert analyze_response.status_code == 200

    debug_after = client.get(f"/api/reports/{report_id}/debug")
    assert debug_after.status_code == 200
    payload_after = debug_after.json()
    assert payload_after["analysis_available"] is True
    assert "executive_snapshot" in payload_after["analysis_keys"]
