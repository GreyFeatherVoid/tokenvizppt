from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services.admin_service import get_admin_service, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    points_balance: int
    invite_code: str | None = None
    created_at: str
    last_login_at: str | None = None
    session_count: int = 0
    generation_count: int = 0


class AdminUserListResponse(BaseModel):
    total: int
    users: list[AdminUserResponse]


class UpdateUserRequest(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    role: str | None = Field(default=None, max_length=40)


class CreditAdjustmentRequest(BaseModel):
    amount: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=1, max_length=120)


class CreditLedgerEntryResponse(BaseModel):
    id: str
    user_id: str
    amount: int
    reason: str
    reference_type: str | None = None
    reference_id: str | None = None
    balance_after: int
    metadata: dict = {}
    created_at: str


class CreditAdjustmentResponse(BaseModel):
    user: AdminUserResponse
    ledger: CreditLedgerEntryResponse


class CreditHistoryResponse(BaseModel):
    total: int
    entries: list[CreditLedgerEntryResponse]


class AdminSessionSummaryResponse(BaseModel):
    id: str
    topic: str
    brief: str
    page_count: int
    style_id: str
    status: str
    latest_run_id: str | None = None
    slide_count: int = 0
    output_language: str = "auto"
    enable_ai_images: bool = False
    created_at: str
    updated_at: str


class AdminSessionListResponse(BaseModel):
    total: int
    sessions: list[AdminSessionSummaryResponse]


class AuditLogResponse(BaseModel):
    id: str
    admin_user_id: str
    action: str
    target_type: str
    target_id: str | None = None
    payload: dict = {}
    created_at: str


class AuditLogListResponse(BaseModel):
    total: int
    logs: list[AuditLogResponse]


class AdminMeResponse(BaseModel):
    authorized: bool
    user_id: str
    email: str
    role: str


@router.get("/me", response_model=AdminMeResponse)
def admin_me(request: Request) -> AdminMeResponse:
    admin = require_admin(request)
    return AdminMeResponse(
        authorized=True,
        user_id=admin.id,
        email=admin.email,
        role=admin.role,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    role: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminUserListResponse:
    require_admin(request)
    result = get_admin_service().list_users(
        query=q,
        status=status,
        role=role,
        limit=limit,
        offset=offset,
    )
    return AdminUserListResponse(**result)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(user_id: str, request: Request) -> AdminUserResponse:
    require_admin(request)
    return AdminUserResponse(**get_admin_service().get_user(user_id))


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    request: Request,
) -> AdminUserResponse:
    admin = require_admin(request)
    user = get_admin_service().update_user(
        admin=admin,
        user_id=user_id,
        status=payload.status,
        role=payload.role,
    )
    return AdminUserResponse(**user)


@router.post("/users/{user_id}/credits", response_model=CreditAdjustmentResponse)
def adjust_credits(
    user_id: str,
    payload: CreditAdjustmentRequest,
    request: Request,
) -> CreditAdjustmentResponse:
    admin = require_admin(request)
    result = get_admin_service().adjust_credits(
        admin=admin,
        user_id=user_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    return CreditAdjustmentResponse(**result)


@router.get("/users/{user_id}/credits", response_model=CreditHistoryResponse)
def list_user_credits(
    user_id: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> CreditHistoryResponse:
    require_admin(request)
    result = get_admin_service().list_user_credits(user_id, limit=limit, offset=offset)
    return CreditHistoryResponse(**result)


@router.get("/users/{user_id}/sessions", response_model=AdminSessionListResponse)
def list_user_sessions(
    user_id: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> AdminSessionListResponse:
    require_admin(request)
    result = get_admin_service().list_user_sessions(user_id, limit=limit, offset=offset)
    return AdminSessionListResponse(**result)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogListResponse:
    require_admin(request)
    result = get_admin_service().list_audit_logs(limit=limit, offset=offset)
    return AuditLogListResponse(**result)
