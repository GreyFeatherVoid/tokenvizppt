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


class AdminGenerationRunResponse(BaseModel):
    id: str
    session_id: str
    user_id: str | None = None
    user_email: str | None = None
    topic: str
    page_count: int
    status: str
    progress: int
    error: str | None = None
    failure_category: str | None = None
    failure_title: str | None = None
    failure_detail: str | None = None
    duration_ms: int = 0
    charge_amount: int = 0
    charge_settled: bool = False
    anonymous: bool = False
    session_status: str
    slide_count: int = 0
    refunded_credits: int = 0
    created_at: str
    updated_at: str


class AdminGenerationRunListResponse(BaseModel):
    total: int
    runs: list[AdminGenerationRunResponse]


class CancelGenerationRunRequest(BaseModel):
    reason: str = Field(default="Cancelled by admin", min_length=1, max_length=160)


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


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    body: str
    status: str
    published_at: str | None = None
    created_by_user_id: str
    created_at: str
    updated_at: str


class AnnouncementListResponse(BaseModel):
    total: int
    announcements: list[AnnouncementResponse]


class AnnouncementUpsertRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=6000)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class CreditRuleResponse(BaseModel):
    id: str | None = None
    action: str
    label: str
    description: str = ""
    amount: int
    enabled: bool
    source: str
    effective_from: str | None = None
    metadata: dict = {}
    created_at: str | None = None
    updated_at: str | None = None


class CreditRuleListResponse(BaseModel):
    total: int
    rules: list[CreditRuleResponse]


class CreditRuleUpdateRequest(BaseModel):
    amount: int = Field(ge=0, le=100000)
    enabled: bool = True


class ProviderConfigResponse(BaseModel):
    id: str
    provider: str
    name: str
    base_url: str | None = None
    model: str
    status: str
    api_key_masked: str = ""
    has_api_key: bool = False
    metadata: dict = {}
    created_at: str
    updated_at: str


class ProviderConfigListResponse(BaseModel):
    total: int
    configs: list[ProviderConfigResponse]


class ProviderConfigUpsertRequest(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    provider: str = Field(pattern="^(llm|ai_image)$")
    name: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=1000)
    model: str = Field(min_length=1, max_length=160)
    api_key: str | None = Field(default=None, max_length=4000)
    status: str = Field(default="disabled", pattern="^(active|disabled)$")


class AdminDashboardStatsResponse(BaseModel):
    users: dict
    projects: dict
    generation_runs: dict
    credits: dict


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


@router.get("/dashboard", response_model=AdminDashboardStatsResponse)
def get_dashboard_stats(request: Request) -> AdminDashboardStatsResponse:
    require_admin(request)
    return AdminDashboardStatsResponse(**get_admin_service().get_dashboard_stats())


@router.get("/announcements", response_model=AnnouncementListResponse)
def list_announcements(
    request: Request,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AnnouncementListResponse:
    require_admin(request)
    result = get_admin_service().list_announcements(status=status, limit=limit, offset=offset)
    return AnnouncementListResponse(**result)


@router.post("/announcements", response_model=AnnouncementResponse)
def create_announcement(
    payload: AnnouncementUpsertRequest,
    request: Request,
) -> AnnouncementResponse:
    admin = require_admin(request)
    result = get_admin_service().upsert_announcement(
        admin=admin,
        title=payload.title,
        body=payload.body,
        status=payload.status,
    )
    return AnnouncementResponse(**result)


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpsertRequest,
    request: Request,
) -> AnnouncementResponse:
    admin = require_admin(request)
    result = get_admin_service().upsert_announcement(
        admin=admin,
        announcement_id=announcement_id,
        title=payload.title,
        body=payload.body,
        status=payload.status,
    )
    return AnnouncementResponse(**result)


@router.get("/credit-rules", response_model=CreditRuleListResponse)
def list_credit_rules(request: Request) -> CreditRuleListResponse:
    require_admin(request)
    return CreditRuleListResponse(**get_admin_service().list_credit_rules())


@router.patch("/credit-rules/{action}", response_model=CreditRuleResponse)
def update_credit_rule(
    action: str,
    payload: CreditRuleUpdateRequest,
    request: Request,
) -> CreditRuleResponse:
    admin = require_admin(request)
    result = get_admin_service().update_credit_rule(
        admin=admin,
        action=action,
        amount=payload.amount,
        enabled=payload.enabled,
    )
    return CreditRuleResponse(**result)


@router.get("/provider-configs", response_model=ProviderConfigListResponse)
def list_provider_configs(request: Request) -> ProviderConfigListResponse:
    require_admin(request)
    return ProviderConfigListResponse(**get_admin_service().list_provider_configs())


@router.post("/provider-configs", response_model=ProviderConfigResponse)
def upsert_provider_config(
    payload: ProviderConfigUpsertRequest,
    request: Request,
) -> ProviderConfigResponse:
    admin = require_admin(request)
    result = get_admin_service().upsert_provider_config(
        admin=admin,
        config_id=payload.id,
        provider=payload.provider,
        name=payload.name,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        status=payload.status,
    )
    return ProviderConfigResponse(**result)


@router.get("/generation-runs", response_model=AdminGenerationRunListResponse)
def list_generation_runs(
    request: Request,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminGenerationRunListResponse:
    require_admin(request)
    result = get_admin_service().list_generation_runs(status=status, limit=limit, offset=offset)
    return AdminGenerationRunListResponse(**result)


@router.post("/generation-runs/{run_id}/cancel", response_model=AdminGenerationRunResponse)
def cancel_generation_run(
    run_id: str,
    payload: CancelGenerationRunRequest,
    request: Request,
) -> AdminGenerationRunResponse:
    admin = require_admin(request)
    result = get_admin_service().cancel_generation_run(
        admin=admin,
        run_id=run_id,
        reason=payload.reason,
    )
    return AdminGenerationRunResponse(**result)
