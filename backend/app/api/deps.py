from app.services.analysis_service import AnalysisService
from app.services.auth_service import AuthService
from app.services.upload_service import UploadService


def get_upload_service() -> UploadService:
    from app.main import upload_service

    return upload_service


def get_analysis_service() -> AnalysisService:
    from app.main import analysis_service

    return analysis_service


def get_auth_service() -> AuthService:
    from app.main import auth_service

    return auth_service
