from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_analysis_service, get_upload_service
from app.core.exceptions import ReportNotFoundError
from app.schemas.analysis_models import AnalysisProgressResponse, AnalysisResponse, DebugResponse
from app.services.analysis_service import AnalysisService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/reports", tags=["analysis"])

_executor = ThreadPoolExecutor(max_workers=2)
_jobs_lock = Lock()
_jobs: dict[tuple[str, str], Future[AnalysisResponse]] = {}


class AnalysisJobStatusResponse(BaseModel):
    status: str
    message: str | None = None


def _owner_id(request: Request) -> str:
    owner_id = getattr(request.state, "session_id", None)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return owner_id


@router.post("/{report_id}/analyze/start", response_model=AnalysisJobStatusResponse)
def start_report_analysis(
    request: Request,
    report_id: str,
    upload: UploadService = Depends(get_upload_service),
    analysis: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobStatusResponse:
    owner_id = _owner_id(request)
    existing = upload.get_analysis(owner_id, report_id)
    if existing is not None:
        return AnalysisJobStatusResponse(status="done", message="Analysis already available")

    try:
        report = upload.get_metadata(owner_id, report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    job_key = (owner_id, report_id)

    with _jobs_lock:
        existing_job = _jobs.get(job_key)
        if existing_job and not existing_job.done():
            return AnalysisJobStatusResponse(status="running", message="Analysis already running")

        def _run() -> AnalysisResponse:
            result = analysis.analyze(report)
            upload.save_analysis(owner_id, report_id, result)
            return result

        _jobs[job_key] = _executor.submit(_run)

    return AnalysisJobStatusResponse(status="running", message="Analysis started")


@router.get("/{report_id}/analyze/status", response_model=AnalysisJobStatusResponse)
def get_report_analysis_status(
    request: Request,
    report_id: str,
    upload: UploadService = Depends(get_upload_service),
) -> AnalysisJobStatusResponse:
    owner_id = _owner_id(request)
    existing = upload.get_analysis(owner_id, report_id)
    if existing is not None:
        return AnalysisJobStatusResponse(status="done")

    job_key = (owner_id, report_id)
    with _jobs_lock:
        job = _jobs.get(job_key)

    if not job:
        return AnalysisJobStatusResponse(status="not_started")

    if not job.done():
        return AnalysisJobStatusResponse(status="running")

    exc = job.exception()
    if exc is not None:
        return AnalysisJobStatusResponse(status="failed", message=str(exc))

    return AnalysisJobStatusResponse(status="done")


@router.post("/{report_id}/analyze", response_model=AnalysisResponse)
def analyze_report(
    request: Request,
    report_id: str,
    upload: UploadService = Depends(get_upload_service),
    analysis: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        report = upload.get_metadata(_owner_id(request), report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    result = analysis.analyze(report)
    upload.save_analysis(_owner_id(request), report_id, result)
    return result


@router.get("/{report_id}/progress", response_model=AnalysisProgressResponse)
def get_report_progress(
    report_id: str,
    analysis: AnalysisService = Depends(get_analysis_service),
) -> AnalysisProgressResponse:
    return AnalysisProgressResponse(**analysis.get_progress(report_id))


@router.get("/{report_id}/analysis", response_model=AnalysisResponse)
def get_report_analysis(
    request: Request,
    report_id: str,
    upload: UploadService = Depends(get_upload_service),
) -> AnalysisResponse:
    existing = upload.get_analysis(_owner_id(request), report_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return existing


@router.get("/{report_id}/debug", response_model=DebugResponse)
def get_report_debug(
    request: Request,
    report_id: str,
    upload: UploadService = Depends(get_upload_service),
) -> dict[str, object]:
    try:
        report = upload.get_metadata(_owner_id(request), report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    analysis = upload.get_analysis(_owner_id(request), report_id)

    return {
        "report_id": report.id,
        "filename": report.filename,
        "page_count": report.page_count,
        "sections": [
            {
                "section_id": section.id,
                "heading": section.heading,
                "normalized_heading": section.normalized_heading,
                "section_type": section.section_type,
                "page_start": section.page_start,
                "page_end": section.page_end,
                "content_preview": section.content[:500],
            }
            for section in report.extracted_sections
        ],
        "analysis_available": analysis is not None,
        "analysis_keys": sorted(list(analysis.model_dump().keys())) if analysis else [],
    }
