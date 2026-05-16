from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.credits import require_current_user_id
from app.services.referral_service import ReferralError, get_referral_service

router = APIRouter(prefix="/invites", tags=["invites"])


class MyInviteResponse(BaseModel):
    invite_code: str
    inviter_credits: int
    invitee_credits: int
    total_invites: int
    rewarded_invites: int
    pending_invites: int


@router.get("/me", response_model=MyInviteResponse)
def my_invite(request: Request) -> MyInviteResponse:
    try:
        stats = get_referral_service().get_stats(require_current_user_id(request))
    except ReferralError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MyInviteResponse(**stats)
