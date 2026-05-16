from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.settings import get_settings
from app.services.auth_service import (
    AuthError,
    EmailDomainNotAllowedError,
    PasswordInvalidError,
    UserAlreadyExistsError,
    UserNotRegisteredError,
    VerificationCodeInvalidError,
    VerificationEmailDeliveryError,
    VerificationCodeRateLimitedError,
    get_auth_service,
    request_ip_hash,
    user_to_dict,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SendCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    purpose: str = Field(default="login", pattern="^(login|register)$")


class SendCodeResponse(BaseModel):
    email: str
    expires_at: str
    resend_after_seconds: int
    dev_code: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password_digest: str | None = Field(default=None, pattern="^[0-9a-f]{32}$")
    code: str | None = Field(default=None, min_length=4, max_length=12)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password_digest: str = Field(pattern="^[0-9a-f]{32}$")
    code: str = Field(min_length=4, max_length=12)
    referral_code: str | None = Field(default=None, max_length=80)


class LoginResponse(BaseModel):
    user: dict
    expires_at: str


class MeResponse(BaseModel):
    authenticated: bool
    user: dict | None = None
    allowed_email_domains: list[str] = []
    auth_enabled: bool


@router.post("/send-code", response_model=SendCodeResponse)
def send_code(payload: SendCodeRequest, request: Request) -> SendCodeResponse:
    try:
        result = get_auth_service().send_code(
            str(payload.email),
            ip_hash=request_ip_hash(request.client.host if request.client else None),
            purpose=payload.purpose,
        )
    except EmailDomainNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UserNotRegisteredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VerificationCodeRateLimitedError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except VerificationEmailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SendCodeResponse(
        email=result.email,
        expires_at=result.expires_at,
        resend_after_seconds=result.resend_after_seconds,
        dev_code=result.dev_code,
    )


@router.post("/register", response_model=LoginResponse)
def register(payload: RegisterRequest, request: Request, response: Response) -> LoginResponse:
    settings = get_settings()
    try:
        result = get_auth_service().register(
            email=str(payload.email),
            password_digest=payload.password_digest,
            code=payload.code,
            referral_code=payload.referral_code,
            ip_hash=request_ip_hash(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
    except EmailDomainNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PasswordInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VerificationCodeInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.set_cookie(
        settings.auth_cookie_name,
        result.token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_days * 24 * 60 * 60,
        path="/",
    )
    return LoginResponse(user=result.user, expires_at=result.expires_at)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    settings = get_settings()
    try:
        result = get_auth_service().login(
            email=str(payload.email),
            password_digest=payload.password_digest,
            code=payload.code,
            ip_hash=request_ip_hash(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
    except EmailDomainNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UserNotRegisteredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VerificationCodeInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.set_cookie(
        settings.auth_cookie_name,
        result.token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_days * 24 * 60 * 60,
        path="/",
    )
    return LoginResponse(user=result.user, expires_at=result.expires_at)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    settings = get_settings()
    get_auth_service().logout(request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    settings = get_settings()
    user = get_auth_service().get_user_by_token(request.cookies.get(settings.auth_cookie_name))
    return MeResponse(
        authenticated=user is not None,
        user=user_to_dict(user) if user else None,
        allowed_email_domains=settings.allowed_email_domains,
        auth_enabled=settings.auth_enabled,
    )
