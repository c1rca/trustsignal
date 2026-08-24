from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_upload_service
from app.core.exceptions import ReportNotFoundError, ReportValidationError
from app.schemas.api_responses import ReportMetadataResponse, SectionResponse, UploadReportResponse
from app.services.upload_service import UploadService

router = APIRouter(prefix="/reports", tags=["reports"])


def _owner_id(request: Request) -> str:
    owner_id = getattr(request.state, "session_id", None)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return owner_id


@router.post("/upload", response_model=UploadReportResponse)
async def upload_report(
    request: Request,
    file: UploadFile = File(...),
    service: UploadService = Depends(get_upload_service),
) -> UploadReportResponse:
    try:
        report = await service.upload_report(_owner_id(request), file)
    except ReportValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return UploadReportResponse(
        report_id=report.id,
        filename=report.filename,
        page_count=report.page_count,
        uploaded_at=report.uploaded_at,
    )


@router.get("/{report_id}", response_model=ReportMetadataResponse)
def get_report_metadata(
    request: Request,
    report_id: str,
    service: UploadService = Depends(get_upload_service),
) -> ReportMetadataResponse:
    try:
        report = service.get_metadata(_owner_id(request), report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    return ReportMetadataResponse(
        report_id=report.id,
        filename=report.filename,
        page_count=report.page_count,
        uploaded_at=report.uploaded_at,
    )


@router.get("/{report_id}/sections", response_model=list[SectionResponse])
def get_report_sections(
    request: Request,
    report_id: str,
    service: UploadService = Depends(get_upload_service),
) -> list[SectionResponse]:
    try:
        report = service.get_metadata(_owner_id(request), report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    return [
        SectionResponse(
            section_id=section.id,
            heading=section.heading,
            normalized_heading=section.normalized_heading,
            page_start=section.page_start,
            page_end=section.page_end,
            section_type=section.section_type,
            content_preview=section.content[:280],
        )
        for section in report.extracted_sections
    ]


@router.get("/{report_id}/file")
def get_report_file(
    request: Request,
    report_id: str,
    service: UploadService = Depends(get_upload_service),
) -> StreamingResponse:
    try:
        report = service.get_metadata(_owner_id(request), report_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    return StreamingResponse(
        iter([report.pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{report.filename}"'},
    )


@router.post("/purge")
def purge_reports(request: Request, service: UploadService = Depends(get_upload_service)) -> dict[str, str]:
    service.purge_all(_owner_id(request))
    return {"status": "ok"}
