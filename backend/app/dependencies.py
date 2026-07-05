"""
FastAPI reusable dependencies for authentication and authorization.
Import these into any route that needs auth or tier enforcement.
"""
import logging
from fastapi import Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.services.auth_service import AuthService
from app.utils import resolve_user_tier

logger = logging.getLogger(__name__)


def get_current_user(
    authorization: str = Header(None),
    token: str = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from a Bearer token.
    Raises HTTP 401 if the token is missing or invalid.
    """
    actual_token = token
    if authorization and authorization.startswith("Bearer "):
        actual_token = authorization.split(" ", 1)[1]

    if not actual_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthService.get_user_from_token(actual_token, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    return user


def get_user_tier(user: User) -> str:
    """Return the effective tier ('premium' or 'free')."""
    return resolve_user_tier(user)


def is_premium_user(user: User) -> bool:
    return resolve_user_tier(user) == "premium"


def require_premium(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the current user to have a premium subscription.
    Raises HTTP 403 for free-tier users.
    """
    if not user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a Premium subscription. Please upgrade to access it.",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the current user to have the admin role.
    Raises HTTP 403 for non-admin users.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


def get_optional_user(
    authorization: str = Header(None),
    token: str = Query(None),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Like get_current_user but returns None instead of raising if unauthenticated.
    Useful for endpoints that behave differently for auth vs. anon users.
    """
    actual_token = token
    if authorization and authorization.startswith("Bearer "):
        actual_token = authorization.split(" ", 1)[1]
    if not actual_token:
        return None
    user = AuthService.get_user_from_token(actual_token, db)
    if not user or not user.is_active:
        return None
    return user
