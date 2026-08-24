from fastapi import APIRouter, Depends, Header, HTTPException, Response, Cookie
from pydantic import BaseModel

from app.api.deps import get_auth_service
from app.core.config import settings
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_COOKIE = "trustsignal_session"
CSRF_COOKIE = "trustsignal_csrf"


class AuthConfigResponse(BaseModel):
    require_login: bool
    setup_required: bool


class SetupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class SessionResponse(BaseModel):
    authenticated: bool


@router.get("/config", response_model=AuthConfigResponse)
def auth_config(service: AuthService = Depends(get_auth_service)) -> AuthConfigResponse:
    return AuthConfigResponse(require_login=True, setup_required=service.is_setup_required())


@router.post("/setup")
def auth_setup(payload: SetupRequest, service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    if not service.is_setup_required():
        raise HTTPException(status_code=409, detail="Credentials already configured")
    try:
        service.setup_credentials(payload.username, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "ok"}


@router.post("/login", response_model=LoginResponse)
def auth_login(payload: LoginRequest, response: Response, service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    try:
        token, csrf_token = service.login(payload.username, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error

    cookie_kwargs = {
        "path": "/",
        "secure": settings.use_https,
        "samesite": "lax",
        "max_age": settings.session_ttl_minutes * 60,
    }
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        **cookie_kwargs,
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        **cookie_kwargs,
    )
    return LoginResponse(token=token)


@router.get("/session", response_model=SessionResponse)
def auth_session(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> SessionResponse:
    token = session_cookie or ""
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    return SessionResponse(authenticated=service.is_authenticated(token))


@router.post("/logout")
def auth_logout(
    response: Response,
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    token = session_cookie or ""
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    service.logout(token)

    cookie_kwargs = {"path": "/"}
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain

    response.delete_cookie(SESSION_COOKIE, **cookie_kwargs)
    response.delete_cookie(CSRF_COOKIE, **cookie_kwargs)
    return {"status": "ok"}
