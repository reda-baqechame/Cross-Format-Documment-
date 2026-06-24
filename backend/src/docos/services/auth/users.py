"""User registration and authentication."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.db.models import Subscription, User
from docos.services.auth.passwords import hash_password, verify_password


class AuthError(Exception):
    pass


def create_user(session: Session, *, email: str, password: str, name: str | None = None) -> User:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise AuthError("a valid email is required")
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters")
    existing = session.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise AuthError("an account with this email already exists")
    user = User(
        id=f"user_{uuid.uuid4().hex[:16]}",
        email=normalized,
        password_hash=hash_password(password),
        name=(name or "").strip() or None,
    )
    session.add(user)
    session.flush()
    session.add(
        Subscription(
            id=f"sub_{uuid.uuid4().hex[:16]}",
            user_id=user.id,
            plan="free",
            status="active",
        )
    )
    return user


def authenticate(session: Session, *, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = session.scalar(select(User).where(User.email == normalized))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid email or password")
    return user


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)
