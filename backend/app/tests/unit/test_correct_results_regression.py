from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


STRICT_EXPECTED = {
    "Matillion-SOC-2-Type-2-FINAL-Report-073124.pdf": {
        "opinion": "unqualified",
        "start": "2023-08-01",
        "end": "2024-07-31",
        "criteria": ["Security"],
        "ownership": "vendor_report",
        "carveout": "carve_out",
        "exceptions": False,
        "subservices": [
            "Amazon Web Services (AWS)",
            "Google",
            "Microsoft – Azure including Dynamics 365",
            "Salesforce",
            "Atlassian",
            "Auth0",
            "Okta",
            "Recurly",
        ],
        "cuecs_present": True,
    },
    "SysAid_SOC2TypeII_FinalReport2024-Redacted-Can-be-shared-without-NDA.pdf": {
        "opinion": "unqualified",
        "start": "2024-04-01",
        "end": "2025-05-31",
        "criteria": ["Security", "Availability", "Confidentiality"],
        "ownership": "vendor_report",
        "carveout": "carve_out",
        "exceptions": False,
        "subservices": ["Amazon Web Services (AWS)"],
    },
    "NayaOne-Limited-2024-SOC-2-Type-II-Final-report.pdf": {
        "opinion": "unqualified",
        "start": "2023-02-01",
        "end": "2024-02-29",
        "criteria": ["Security", "Availability", "Confidentiality"],
        "ownership": "vendor_report",
        "carveout": "carve_out",
        "exceptions": False,
        "subservices": ["Amazon Web Services (AWS)"],
    },
}


def test_test_files_against_correct_results_contract() -> None:
    """Run all SOC 2 test files and enforce strict contracts on curated reference samples."""
    client = TestClient(app)
    root = Path(__file__).resolve().parents[4]
    samples = sorted((root / "test_files").glob("*.pdf"))
    assert samples

    for sample in samples:
        with sample.open("rb") as handle:
            upload = client.post("/api/reports/upload", files={"file": (sample.name, handle, "application/pdf")})
        assert upload.status_code == 200, sample.name

        report_id = upload.json()["report_id"]
        analyze = client.post(f"/api/reports/{report_id}/analyze")
        assert analyze.status_code == 200, sample.name
        payload = analyze.json()

        # Baseline contract for all corpus files.
        assert payload["opinion"]["opinion_type"] in {"unqualified", "qualified", "unclear"}, sample.name
        assert payload["scope"]["audit_period_start"] or payload["scope"]["audit_period"] == "Not clearly stated", sample.name
        assert payload["scope"]["audit_period_end"] or payload["scope"]["audit_period"] == "Not clearly stated", sample.name
        assert payload["ownership"]["ownership_type"] in {"vendor_report", "mixed_or_parent"}, sample.name
        assert payload["carveout"]["method"] in {"carve_out", "inclusive", "unclear"}, sample.name
        assert isinstance(payload["exceptions"]["exceptions_detected"], bool), sample.name

        expected = STRICT_EXPECTED.get(sample.name)
        if not expected:
            continue

        assert payload["opinion"]["opinion_type"] == expected["opinion"], sample.name
        assert payload["scope"]["audit_period_start"] == expected["start"], sample.name
        assert payload["scope"]["audit_period_end"] == expected["end"], sample.name
        assert payload["criteria"]["criteria"] == expected["criteria"], sample.name
        assert payload["ownership"]["ownership_type"] == expected["ownership"], sample.name
        assert payload["carveout"]["method"] == expected["carveout"], sample.name
        assert payload["exceptions"]["exceptions_detected"] is expected["exceptions"], sample.name
        assert payload["subservices"]["organizations"] == expected["subservices"], sample.name

        if expected.get("cuecs_present"):
            assert bool(payload["cuecs"]["responsibilities"]), sample.name
