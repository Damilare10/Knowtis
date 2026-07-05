"""
Authentication and token management service
"""
import logging
import base64
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import User, RefreshToken
from app.config import settings

logger = logging.getLogger(__name__)

# ── Optional library imports with fallbacks ───────────────────────────────────
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False


class AuthService:
    """Service handling password hashing, JWT creation/decoding, and refresh tokens"""

    # ── Password utilities ────────────────────────────────────────────────────

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its stored hash."""
        if HAS_BCRYPT:
            # bcrypt has a 72-byte input limit; truncate like the library itself
            # does so we don't accidentally raise and fall through.
            encoded = plain_password.encode("utf-8")[:72]
            try:
                return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
            except (ValueError, TypeError) as exc:
                logger.warning("bcrypt verification failed unexpectedly: %s", exc)
                return False

        # SHA-256 + salt fallback (dev only — explicitly weaker than bcrypt).
        if "$" in hashed_password:
            salt, stored_hash = hashed_password.split("$", 1)
        else:
            salt, stored_hash = "default_salt", hashed_password
        computed = AuthService._fallback_hash(plain_password, salt)
        return hmac.compare_digest(computed, stored_hash)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate a secure password hash."""
        if HAS_BCRYPT:
            # bcrypt has a 72-byte input limit; truncate like the library itself
            # does so we don't accidentally raise and fall through.
            encoded = password.encode("utf-8")[:72]
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(encoded, salt).decode("utf-8")

        # SHA-256 + salt fallback — dev only. Insecure for production.
        logger.warning(
            "bcrypt is not available; using insecure SHA-256 fallback for password hashing"
        )
        import uuid as _uuid

        salt = _uuid.uuid4().hex
        return f"{salt}${AuthService._fallback_hash(password, salt)}"

    @staticmethod
    def _fallback_hash(password: str, salt: str) -> str:
        """SHA-256 fallback hash (not bcrypt-strength, dev use only)"""
        return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()

    # ── Access token ──────────────────────────────────────────────────────────

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a short-lived JWT access token"""
        from datetime import timezone
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
        )
        to_encode.update({"exp": int(expire.timestamp()), "type": "access"})

        if HAS_JWT:
            try:
                return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
            except Exception:
                pass

        return AuthService._simulated_token(to_encode, settings.jwt_secret_key)

    @staticmethod
    def get_user_from_token(token: str, db: Session) -> Optional[User]:
        """Decode an access token and return the corresponding user"""
        from datetime import timezone
        payload = AuthService._decode_token(token, settings.jwt_secret_key)
        if not payload:
            return None

        if payload.get("type") != "access":
            return None

        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None

        username = payload.get("sub")
        if not username:
            return None

        return db.query(User).filter(User.username == username).first()

    # ── Refresh token ─────────────────────────────────────────────────────────

    @staticmethod
    def create_refresh_token(user_id, db: Session) -> str:
        """
        Create a long-lived refresh token, store its hash in the DB,
        and return the raw token string to send to the client.
        """
        import secrets
        raw_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)

        record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        db.add(record)
        db.commit()
        return raw_token

    @staticmethod
    def verify_refresh_token(raw_token: str, db: Session) -> Optional[Tuple[User, RefreshToken]]:
        """
        Validate a raw refresh token.
        Returns (User, RefreshToken record) if valid, None otherwise.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        record = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        ).first()

        if not record:
            return None

        if datetime.utcnow() > record.expires_at:
            record.revoked = True
            db.commit()
            return None

        user = db.query(User).filter(User.id == record.user_id).first()
        if not user or not user.is_active:
            return None

        return user, record

    @staticmethod
    def revoke_refresh_token(raw_token: str, db: Session) -> bool:
        """Revoke a specific refresh token (logout)"""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        record = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if record:
            record.revoked = True
            db.commit()
            return True
        return False

    @staticmethod
    def revoke_all_user_tokens(user_id, db: Session) -> int:
        """Revoke all refresh tokens for a user (e.g. password change, security event)"""
        count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
        ).update({"revoked": True})
        db.commit()
        return count

    # ── Google OAuth helpers ──────────────────────────────────────────────────

    @staticmethod
    def get_google_oauth_url() -> Optional[str]:
        """
        Build the Google OAuth consent URL.
        Returns None if Google credentials are not configured.
        """
        if not settings.google_client_id:
            return None

        import urllib.parse
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": f"{settings.backend_url}/api/v1/auth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        base = "https://accounts.google.com/o/oauth2/v2/auth"
        return f"{base}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def exchange_google_code(code: str) -> Optional[dict]:
        """
        Exchange a Google authorization code for user info.
        Returns dict with {email, name, google_id} or None on failure.
        """
        if not settings.google_client_id or not settings.google_client_secret:
            return None

        try:
            import urllib.request
            import urllib.parse as up

            # Exchange code for tokens
            token_data = up.urlencode({
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.backend_url}/api/v1/auth/google/callback",
                "grant_type": "authorization_code",
            }).encode()

            req = urllib.request.Request(
                "https://oauth2.googleapis.com/token",
                data=token_data,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                tokens = json.loads(resp.read())

            id_token = tokens.get("id_token", "")
            if not id_token:
                return None

            # Decode id_token payload (no signature verification needed for MVP — Google already validated)
            parts = id_token.split(".")
            if len(parts) < 2:
                return None

            padding = len(parts[1]) % 4
            padded = parts[1] + "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(padded))

            return {
                "email": payload.get("email"),
                "name": payload.get("name", ""),
                "google_id": payload.get("sub"),
            }

        except Exception as e:
            logger.error(f"Google OAuth exchange failed: {e}")
            return None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _simulated_token(payload: dict, secret: str) -> str:
        """Pure-Python HMAC token when python-jose is not installed"""
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8").rstrip("=")

        sig = hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return f"simulated.{payload_b64}.{sig}"

    @staticmethod
    def _decode_token(token: str, secret: str) -> Optional[dict]:
        """Decode a JWT or simulated token, returning the payload dict or None"""
        if not token:
            return None
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]

        if HAS_JWT:
            try:
                return jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
            except Exception:
                pass

        # Simulated token fallback
        try:
            parts = token.split(".")
            if len(parts) == 3 and parts[0] == "simulated":
                payload_b64, sig = parts[1], parts[2]
                expected_sig = hmac.new(
                    secret.encode("utf-8"),
                    payload_b64.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()

                if hmac.compare_digest(sig, expected_sig):
                    padding = len(payload_b64) % 4
                    if padding:
                        payload_b64 += "=" * (4 - padding)
                    return json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        except Exception as e:
            logger.error(f"Token decode error: {e}")

        return None
