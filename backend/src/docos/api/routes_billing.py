"""Billing plans and Stripe checkout seam."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api.session import Actor, get_actor
from docos.deps import db_session
from docos.services.billing import stripe_checkout
from docos.services.billing.plans import PLANS, effective_plan
from docos.settings import get_settings

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanView(BaseModel):
    id: str
    name: str
    price_monthly: int
    features: list[str]


class BillingStatusResponse(BaseModel):
    configured: bool
    plan: str
    status: str
    plans: list[PlanView]


class CheckoutRequest(BaseModel):
    plan: str  # pro|team


class CheckoutResponse(BaseModel):
    checkout_url: str


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> BillingStatusResponse:
    settings = get_settings()
    plan, status = effective_plan(session, actor)
    return BillingStatusResponse(
        configured=settings.billing_configured,
        plan=plan,
        status=status,
        plans=[
            PlanView(id=p.id, name=p.name, price_monthly=p.price_monthly, features=p.features)
            for p in PLANS
        ],
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    body: CheckoutRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> CheckoutResponse:
    if actor.user_id is None:
        raise HTTPException(status_code=401, detail="sign in to upgrade")
    settings = get_settings()
    if not settings.billing_configured:
        raise HTTPException(
            status_code=501,
            detail=(
                "billing is not configured on this deployment "
                "(set STRIPE_SECRET_KEY and STRIPE_PRICE_PRO)"
            ),
        )
    if body.plan not in ("pro", "team"):
        raise HTTPException(status_code=422, detail="plan must be pro or team")
    user_email = None
    from docos.services.auth.users import get_user

    user = get_user(session, actor.user_id)
    if user:
        user_email = user.email
    url = stripe_checkout.create_checkout_session(
        session,
        user_id=actor.user_id,
        plan=body.plan,
        email=user_email,
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Session = Depends(db_session),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=501, detail="stripe webhook not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    stripe_checkout.handle_webhook(session, payload=payload, signature=sig)
    session.commit()
    return {"ok": True}
