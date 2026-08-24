from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_matillion_acceptance_targets() -> None:
    client = TestClient(app)

    sample = Path(__file__).resolve().parents[4] / "test_files" / "Matillion-SOC-2-Type-2-FINAL-Report-073124.pdf"
    assert sample.exists()

    with sample.open("rb") as handle:
        upload = client.post("/api/reports/upload", files={"file": (sample.name, handle, "application/pdf")})
    assert upload.status_code == 200

    report_id = upload.json()["report_id"]
    analyze = client.post(f"/api/reports/{report_id}/analyze")
    assert analyze.status_code == 200

    payload = analyze.json()

    assert payload["opinion"]["opinion_type"] == "unqualified"
    assert payload["scope"]["audit_period"] == "2023-08-01 to 2024-07-31"
    assert payload["ownership"]["ownership_type"] == "vendor_report"
    assert payload["criteria"]["criteria"] == ["Security"]
    assert payload["criteria"]["criteria_framework_reference"]
    assert payload["carveout"]["method"] == "carve_out"
    assert payload["exceptions"]["exceptions_detected"] is False

    subservices = payload["subservices"]["organizations"]
    assert subservices == [
        "Amazon Web Services (AWS)",
        "Google",
        "Microsoft – Azure including Dynamics 365",
        "Salesforce",
        "Atlassian",
        "Auth0",
        "Okta",
        "Recurly",
    ]

    assert payload["cuecs"]["responsibilities"], "expected user-control section extraction"
