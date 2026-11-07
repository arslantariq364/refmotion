"""Local Authentication & Session Token Management."""
from __future__ import annotations

import hashlib
import hmac
import base64
import json
import time
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import get_db
from backend.models import User


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = hashlib.sha256(settings.UNICO_SECRET_KEY.encode()).hexdigest()[:16]
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, stored_hash)


def create_access_token(username: str, role: str, expires_in: int = 86400 * 7) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + expires_in,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(
        settings.UNICO_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload_b64, sig = token.split(".", 1)
        expected_sig = hmac.new(
            settings.UNICO_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def ensure_default_admin(db: Session) -> User:
    user = db.query(User).filter(User.username == settings.UNICO_DEFAULT_ADMIN_USER).first()
    if not user:
        user = User(
            username=settings.UNICO_DEFAULT_ADMIN_USER,
            password_hash=hash_password(settings.UNICO_DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not settings.UNICO_REQUIRE_AUTH and not authorization:
        return ensure_default_admin(db)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found",
        )
    return user
