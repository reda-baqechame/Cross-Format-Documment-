"""User registration, login, logout, and profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api.access import claim_session_assets
from docos.api.ratelimit import enforce_auth_rate
from docos.api.session import Actor, clear_auth_cookie, get_actor, set_auth_cookie
from docos.deps import db_session
from docos.services.auth.users import AuthError, authenticate, create_user, get_user

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserView(BaseModel):
    id: str
    email: str
    name: str | None


class AuthResponse(BaseModel):
    user: UserView
    claimed: dict[str, int] | None = None


def _view(user) -> UserView:
    return UserView(id=user.id, email=user.email, name=user.name)


@router.post("/register", response_model=AuthResponse, dependencies=[Depends(enforce_auth_rate)])
def register(
    body: RegisterRequest,
    response: Response,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> AuthResponse:
    try:
        user = create_user(session, email=body.email, password=body.password, name=body.name)
        claimed = claim_session_assets(session, from_session=actor.session_id, to_user=user.id)
        session.commit()
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    set_auth_cookie(response, user.id)
    return AuthResponse(user=_view(user), claimed=claimed)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(enforce_auth_rate)])
def login(
    body: LoginRequest,
    response: Response,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> AuthResponse:
    try:
        user = authenticate(session, email=body.email, password=body.password)
        claimed = claim_session_assets(session, from_session=actor.session_id, to_user=user.id)
        session.commit()
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_auth_cookie(response, user.id)
    return AuthResponse(user=_view(user), claimed=claimed)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserView | None)
def me(
    response: Response,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> UserView | None:
    if actor.user_id is None:
        return None
    user = get_user(session, actor.user_id)
    if user is None:
        clear_auth_cookie(response)
        return None
    return _view(user)
