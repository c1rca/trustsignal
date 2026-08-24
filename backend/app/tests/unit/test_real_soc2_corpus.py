from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_real_soc2_corpus_upload_analyze_debug() -> None:
    """Regression coverage for real SOC 2 samples in test_files/."""
    client = TestClient(app)
    file_path = Path(__file__).resolve()
    project_root = next((parent for parent in file_path.parents if (parent / "test_files").exists()), None)
    assert project_root is not None, "Could not locate project root containing test_files/"

    corpus_dir = project_root / "test_files"
    samples = sorted(corpus_dir.glob("*.pdf"))
    assert samples, "Expected sample PDFs in test_files/"

    for sample in samples:
        with sample.open("rb") as handle:
            upload_response = client.post(
                "/api/reports/upload",
                files={"file": (sample.name, handle, "application/pdf")},
            )

        assert upload_response.status_code == 200, sample.name
        report_id = upload_response.json()["report_id"]

        analyze_response = client.post(f"/api/reports/{report_id}/analyze")
        assert analyze_response.status_code == 200, sample.name

        payload = analyze_response.json()
        assert payload["report_metadata"]["report_id"] == report_id
        assert len(payload["findings"]) == 6
        assert payload["review_summary"]["total_findings"] == 6
        assert "status_counts" in payload["review_summary"]
        assert all(
            finding["status"] in {"pass", "fail", "needs_review"}
            for finding in payload["findings"]
        )

        get_analysis_response = client.get(f"/api/reports/{report_id}/analysis")
        assert get_analysis_response.status_code == 200, sample.name

        debug_response = client.get(f"/api/reports/{report_id}/debug")
        assert debug_response.status_code == 200, sample.name
