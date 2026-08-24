from __future__ import annotations

import glob
from io import BytesIO
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[4]
SAMPLE_DIR = ROOT / "test_files"


def make_pdf_bytes_from_path(path: Path) -> bytes:
    with fitz.open(path) as doc:
        return doc.tobytes()


def test_opinion_regression_on_sample_set() -> None:
    files = sorted(glob.glob(str(SAMPLE_DIR / "*.pdf")))
    assert len(files) >= 8

    client = TestClient(app)
    unclear = 0

    for file_path in files:
        path = Path(file_path)
        files_payload = {
            "file": (path.name, BytesIO(make_pdf_bytes_from_path(path)), "application/pdf")
        }

        upload = client.post("/api/reports/upload", files=files_payload)
        assert upload.status_code == 200
        report_id = upload.json()["report_id"]

        analyze = client.post(f"/api/reports/{report_id}/analyze")
        assert analyze.status_code == 200
        payload = analyze.json()

        opinion = payload["executive_snapshot"]["opinion"]
        if opinion == "unclear":
            unclear += 1

    # Regression guard: unclear should not dominate the sample corpus.
    assert unclear <= 2
