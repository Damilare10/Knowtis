"""
API Routes - Authentication
Covers: register, login, token refresh, logout, Google OAuth
"""
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    RefreshRequest,
    UserUpdate,
    UsernameCheckResponse,
)
from app.services.auth_service import AuthService
from app.dependencies import get_current_user, require_admin
from app.config import settings
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ── Username helpers ────────────────────────────────────────────────────────

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def _normalize_username(raw: str) -> str:
    """Lowercase + strip — used for both availability checks and storage."""
    return raw.strip().lower()


def _next_available_variant(db: Session, base: str) -> str:
    """Generate ``base2``, ``base3`` … until a free username is found.

    Returns ``None`` if no variant under ``max_attempts`` tries fits the
    length cap or character set.
    """
    base = base[:18]  # leave room for a 1-2 digit suffix
    for i in range(2, 1000):
        candidate = f"{base}{i}"
        if len(candidate) > 20:
            # Trim the base further to fit a single digit.
            candidate = base[:19] + str(i)
            if len(candidate) > 20:
                return None
        taken = (
            db.query(User).filter(User.username == candidate).first() is not None
        )
        if not taken:
            return candidate
    return None


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_auth)
async def register(request: Request, user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new student account and return access + refresh tokens.

    ``UserRegister`` enforces ``password == confirm_password`` via a Pydantic
    model_validator, so a mismatch surfaces as a 422 *before* this handler is
    ever called. Username must match ``^[a-z0-9_]{3,20}$``; email uniqueness
    is still verified server-side.
    """
    username = _normalize_username(user_data.username)

    try:
        existing_email = (
            db.query(User).filter(User.email == user_data.email).first()
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered.",
            )

        existing_username = (
            db.query(User).filter(User.username == username).first()
        )
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken.",
            )

        # Clean the optional WhatsApp number to digits-only.
        whatsapp_number = None
        if user_data.whatsapp_number:
            cleaned = "".join(c for c in user_data.whatsapp_number if c.isdigit())
            whatsapp_number = cleaned or None

        hashed_password = AuthService.get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            username=username,
            hashed_password=hashed_password,
            whatsapp_number=whatsapp_number,
            tier="free",
            role=UserRole.STUDENT,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        access_token = AuthService.create_access_token({"sub": new_user.username})
        refresh_token = AuthService.create_refresh_token(new_user.id, db)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": new_user,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user.",
        )


@router.get("/check-username", response_model=UsernameCheckResponse)
async def check_username(
    request: Request,
    username: str = Query(
        ...,
        min_length=1,
        max_length=40,
        description="Candidate username — normalised server-side.",
    ),
    db: Session = Depends(get_db),
):
    """Lightweight lookup the signup form hits on every keystroke (debounced).

    Returns ``available=True`` when the username is free and well-formed,
    otherwise ``available=False`` plus a numeric-suffixed suggestion when one
    exists within the 20-char limit. All invalid shapes (too short, bad
    characters, too long) surface as ``available=False`` with no suggestion
    so the frontend can present a single coherent "not available" path.
    """
    normalised = _normalize_username(username)

    if not _USERNAME_RE.match(normalised):
        return UsernameCheckResponse(
            username=normalised,
            available=False,
            suggestion=None,
        )

    taken = db.query(User).filter(User.username == normalised).first() is not None
    if not taken:
        return UsernameCheckResponse(username=normalised, available=True)

    suggestion = _next_available_variant(db, normalised)
    return UsernameCheckResponse(
        username=normalised,
        available=False,
        suggestion=suggestion,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
async def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Log in with username + password, returns access + refresh tokens"""
    try:
        user = db.query(User).filter(User.username == credentials.username).first()
        if not user or not AuthService.verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )

        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.commit()

        access_token = AuthService.create_access_token({"sub": user.username})
        refresh_token = AuthService.create_refresh_token(user.id, db)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log in.",
        )


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
async def refresh_token(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token + rotated refresh token.
    Old refresh token is revoked after use (token rotation).
    """
    result = AuthService.verify_refresh_token(body.refresh_token, db)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, old_record = result

    # Revoke the old refresh token (rotation)
    old_record.revoked = True
    db.commit()

    # Issue new token pair
    new_access = AuthService.create_access_token({"sub": user.username})
    new_refresh = AuthService.create_refresh_token(user.id, db)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": user,
    }


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Revoke the provided refresh token.
    The client should also discard the access token locally.
    """
    AuthService.revoke_refresh_token(body.refresh_token, db)
    return {"message": "Logged out successfully."}


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
@limiter.limit(settings.rate_limit_auth)
async def google_oauth_start(request: Request):
    """
    Redirect the user to Google's OAuth consent screen.
    Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to be configured.
    """
    url = AuthService.get_google_oauth_url()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server.",
        )
    return RedirectResponse(url=url)


@router.get("/google/callback")
@limiter.limit(settings.rate_limit_auth)
async def google_oauth_callback(request: Request, code: str = Query(...), db: Session = Depends(get_db)):
    """
    Handle Google's OAuth callback. Creates or links a user account.
    Returns access + refresh tokens on success.
    """
    google_user = AuthService.exchange_google_code(code)

    if not google_user or not google_user.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user info from Google.",
        )

    email = google_user["email"]
    google_id = google_user.get("google_id", "")
    name = google_user.get("name", "")

    # Find or create user
    user = db.query(User).filter(
        (User.email == email) | (
            (User.auth_provider == "google") & (User.auth_provider_id == google_id)
        )
    ).first()

    if not user:
        # Generate a unique username from the email prefix
        base_username = email.split("@")[0].replace(".", "_")
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            full_name=name,
            auth_provider="google",
            auth_provider_id=google_id,
            tier="free",
            role=UserRole.STUDENT,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update provider info if signing in via Google on an existing email account
        if user.auth_provider != "google":
            user.auth_provider = "google"
            user.auth_provider_id = google_id
            db.commit()

    access_token = AuthService.create_access_token({"sub": user.username})
    refresh_token = AuthService.create_refresh_token(user.id, db)

    from app.config import settings
    redirect_url = f"{settings.frontend_url}/login/callback?token={access_token}"
    
    response = RedirectResponse(url=redirect_url)
    # Optionally we could set the refresh token as an httpOnly cookie here
    return response


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile"""
    return user


@router.get("/admin-only", response_model=UserResponse)
async def admin_only(user: User = Depends(require_admin)):
    """Admin-only endpoint to test Role Management"""
    return user


# ── Profile Management ────────────────────────────────────────────────────────

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's profile information"""
    try:
        if user_data.email is not None and user_data.email != current_user.email:
            existing = db.query(User).filter(User.email == user_data.email).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use.",
                )
            current_user.email = user_data.email

        if user_data.full_name is not None:
            current_user.full_name = user_data.full_name

        if user_data.whatsapp_number is not None:
            if user_data.whatsapp_number == "":
                current_user.whatsapp_number = None
            else:
                cleaned_number = "".join(c for c in user_data.whatsapp_number if c.isdigit())
                if cleaned_number == "":
                    current_user.whatsapp_number = None
                elif cleaned_number != current_user.whatsapp_number:
                    existing = db.query(User).filter(User.whatsapp_number == cleaned_number).first()
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="WhatsApp number already in use by another account.",
                        )
                    current_user.whatsapp_number = cleaned_number

        if user_data.password is not None and user_data.password != "":
            current_user.hashed_password = AuthService.get_password_hash(user_data.password)

        if user_data.fcm_token is not None:
            current_user.fcm_token = user_data.fcm_token

        db.commit()
        db.refresh(current_user)
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile.",
        )


@router.post("/fcm-token", response_model=UserResponse)
async def update_fcm_token(
    token_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register or update user's FCM device token"""
    try:
        if token_data.fcm_token is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fcm_token is required.",
            )
        current_user.fcm_token = token_data.fcm_token
        db.commit()
        db.refresh(current_user)
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating FCM token: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update FCM token.",
        )


@router.delete("/profile", status_code=status.HTTP_200_OK)
async def delete_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete currently authenticated user's account"""
    try:
        db.delete(current_user)
        db.commit()
        return {"message": "Account successfully deleted."}
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account.",
        )



