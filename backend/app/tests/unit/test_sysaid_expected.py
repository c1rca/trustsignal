from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[4]
FILE_PATH = ROOT / "test_files" / "SysAid_SOC2TypeII_FinalReport2024-Redacted-Can-be-shared-without-NDA.pdf"


def test_sysaid_expected_results() -> None:
    client = TestClient(app)

    with FILE_PATH.open("rb") as fh:
        upload = client.post(
            "/api/reports/upload",
            files={"file": (FILE_PATH.name, BytesIO(fh.read()), "application/pdf")},
        )

    assert upload.status_code == 200
    report_id = upload.json()["report_id"]

    analyze = client.post(f"/api/reports/{report_id}/analyze")
    assert analyze.status_code == 200
    payload = analyze.json()

    assert payload["executive_snapshot"]["opinion"] == "unqualified"
    assert payload["executive_snapshot"]["audit_period_start"] == "2024-04-01"
    assert payload["executive_snapshot"]["audit_period_end"] == "2025-05-31"
    assert payload["executive_snapshot"]["criteria_covered"] == [
        "Security",
        "Availability",
        "Confidentiality",
    ]
    assert payload["criteria"]["criteria_framework_reference"] == [
        "Security",
        "Availability",
        "Processing Integrity",
        "Confidentiality",
        "Privacy",
    ]
    assert payload["ownership"]["ownership_type"] == "vendor_report"
    assert payload["carveout"]["method"] == "carve_out"
    assert payload["subservices"]["organizations"] == ["Amazon Web Services (AWS)"]
    assert payload["exceptions"]["exceptions_detected"] is False
    assert len(payload["cuecs"]["responsibilities"]) == 9
