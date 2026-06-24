"""Plan definitions and gating helpers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.session import Actor
from docos.db.models import Subscription


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_monthly: int
    features: list[str]
    portal_links: bool


PLANS: list[Plan] = [
    Plan(
        id="free",
        name="Free",
        price_monthly=0,
        features=[
            "Unlimited client packet readiness checks",
            "Full document editor + trust tools",
            "Private session workspace",
        ],
        portal_links=False,
    ),
    Plan(
        id="pro",
        name="Pro",
        price_monthly=99,
        features=[
            "Everything in Free",
            "Shareable client portal links",
            "Bulk send with recipient access",
            "Saved account + document library",
        ],
        portal_links=True,
    ),
    Plan(
        id="team",
        name="Team",
        price_monthly=299,
        features=[
            "Everything in Pro",
            "Team seats (coming soon)",
            "Priority support",
        ],
        portal_links=True,
    ),
]

_PLAN_BY_ID = {p.id: p for p in PLANS}


def effective_plan(session: Session, actor: Actor) -> tuple[str, str]:
    """Return (plan_id, status) for the actor — anonymous users are always free."""
    if actor.user_id is None:
        return "free", "active"
    sub = session.scalar(select(Subscription).where(Subscription.user_id == actor.user_id))
    if sub is None or sub.status != "active":
        return "free", sub.status if sub else "active"
    return sub.plan, sub.status


def has_portal_access(session: Session, actor: Actor) -> bool:
    plan_id, status = effective_plan(session, actor)
    if status != "active":
        return False
    plan = _PLAN_BY_ID.get(plan_id, _PLAN_BY_ID["free"])
    return plan.portal_links


def require_portal_access(session: Session, actor: Actor) -> None:
    if has_portal_access(session, actor):
        return
    if actor.user_id is None:
        raise HTTPException(
            status_code=402,
            detail="sign in and upgrade to Pro to create client portal links",
        )
    raise HTTPException(
        status_code=402,
        detail="upgrade to Pro to create client portal links (/pricing)",
    )
