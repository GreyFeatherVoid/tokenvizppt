from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.core.settings import get_settings
from app.services.auth_service import get_auth_service, request_ip_hash
from app.services.session_store import SessionNotFoundError, get_session_store


@dataclass(frozen=True)
class RequestAccess:
    user_id: str | None
    ip_hash: str
    auth_enabled: bool


def request_access(request: Request) -> RequestAccess:
    settings = get_settings()
    user = get_auth_service().get_user_by_token(request.cookies.get(settings.auth_cookie_name))
    return RequestAccess(
        user_id=user.id if user else None,
        ip_hash=request_ip_hash(request.client.host if request.client else None),
        auth_enabled=settings.auth_enabled,
    )


def stamp_session_owner(payload: dict, request: Request) -> dict:
    access = request_access(request)
    stamped = dict(payload)
    stamped["user_id"] = access.user_id
    if access.auth_enabled and not access.user_id:
        stamped["anonymous_ip_hash"] = access.ip_hash
    return stamped


def require_session_access(session_id: str, request: Request) -> dict:
    try:
        session = get_session_store().get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not can_access_session(session, request_access(request)):
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def can_access_session(session: dict, access: RequestAccess) -> bool:
    if not access.auth_enabled:
        return True
    owner_user_id = session.get("user_id")
    if access.user_id:
        return owner_user_id == access.user_id or (
            not owner_user_id and session.get("anonymous_ip_hash") == access.ip_hash
        )
    return not owner_user_id and session.get("anonymous_ip_hash") == access.ip_hash
