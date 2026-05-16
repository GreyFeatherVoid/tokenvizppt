from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.settings import get_settings
from app.services.auth_service import get_auth_service
from app.services.credit_service import (
    CreditError,
    DailyCheckinAlreadyClaimedError,
    get_credit_service,
)

router = APIRouter(prefix="/credits", tags=["credits"])


class CreditBalanceResponse(BaseModel):
    user_id: str
    points_balance: int
    can_checkin: bool
    checkin_credits: int


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


class CreditHistoryResponse(BaseModel):
    entries: list[CreditLedgerEntryResponse]


def require_current_user_id(request: Request) -> str:
    settings = get_settings()
    user = get_auth_service().get_user_by_token(request.cookies.get(settings.auth_cookie_name))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user.id


@router.get("/balance", response_model=CreditBalanceResponse)
def get_balance(request: Request) -> CreditBalanceResponse:
    try:
        balance = get_credit_service().get_balance(require_current_user_id(request))
    except CreditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CreditBalanceResponse(
        user_id=balance.user_id,
        points_balance=balance.points_balance,
        can_checkin=balance.can_checkin,
        checkin_credits=balance.checkin_credits,
    )


@router.get("/history", response_model=CreditHistoryResponse)
def get_history(request: Request, limit: int = 50) -> CreditHistoryResponse:
    try:
        entries = get_credit_service().list_ledger(require_current_user_id(request), limit=limit)
    except CreditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CreditHistoryResponse(entries=[CreditLedgerEntryResponse(**entry) for entry in entries])


@router.post("/checkin", response_model=CreditBalanceResponse)
def checkin(request: Request) -> CreditBalanceResponse:
    try:
        balance = get_credit_service().checkin(require_current_user_id(request))
    except DailyCheckinAlreadyClaimedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CreditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CreditBalanceResponse(
        user_id=balance.user_id,
        points_balance=balance.points_balance,
        can_checkin=balance.can_checkin,
        checkin_credits=balance.checkin_credits,
    )
