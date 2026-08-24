import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.analysis import router as analysis_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.extractors.pdf_text_extractor import PdfTextExtractor
from app.extractors.section_segmenter import SectionSegmenter
from app.services.analysis_service import AnalysisService
from app.services.document_service import DocumentService
from app.services.auth_service import AuthService
from app.services.upload_service import UploadService
from app.storage.report_store import ReportStore

setup_logging(settings.log_level)
logger = logging.getLogger("app.http")

report_store = ReportStore(ttl_minutes=settings.report_ttl_minutes)
document_service = DocumentService(PdfTextExtractor(), SectionSegmenter())
upload_service = UploadService(
    document_service=document_service,
    report_store=report_store,
    max_size_bytes=settings.max_upload_mb * 1024 * 1024,
)
analysis_service = AnalysisService()
auth_service = AuthService(require_login=True, store_path=settings.auth_store_path, session_ttl_minutes=settings.session_ttl_minutes)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5191",
        "http://127.0.0.1:5191",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    started = time.perf_counter()
    client = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info("%s %s -> %s | %.1fms | client=%s", method, path, response.status_code, duration_ms, client)
        return response
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception("%s %s -> 500 | %.1fms | client=%s", method, path, duration_ms, client)
        raise


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    allowed_unauthenticated = {
        f"{settings.api_prefix}/health",
        f"{settings.api_prefix}/auth/config",
        f"{settings.api_prefix}/auth/setup",
        f"{settings.api_prefix}/auth/login",
    }
    if path in allowed_unauthenticated or not path.startswith(settings.api_prefix):
        return await call_next(request)

    token = request.cookies.get("trustsignal_session")
    if not token:
        authorization = request.headers.get("authorization", "")
        token = authorization[7:] if authorization.lower().startswith("bearer ") else None

    if not auth_service.is_authenticated(token):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    # CSRF protection for state-changing requests when using cookie sessions.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != settings.frontend_origin:
            return JSONResponse(status_code=403, content={"detail": "Invalid request origin"})

        csrf_header = request.headers.get("x-csrf-token")
        if not auth_service.validate_csrf(token, csrf_header):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

    request.state.session_id = token
    return await call_next(request)


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
