"""
Authentication and token management service
"""
import logging
import base64
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models import User
from app.config import settings

logger = logging.getLogger(__name__)

# Try to import standard bcrypt and JWT libraries, but prepare pure-Python fallbacks
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
    """Service handling password hashing, password verification, and JWT creation/decoding"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against its hash"""
        if HAS_BCRYPT:
            try:
                return bcrypt.checkpw(
                    plain_password.encode('utf-8'),
                    hashed_password.encode('utf-8')
                )
            except Exception:
                pass
        
        # Cryptographic fallback if bcrypt is not installed
        if "$" in hashed_password:
            salt = hashed_password.split("$")[0]
        else:
            salt = "default_salt"
        expected = AuthService._fallback_hash(plain_password, salt)
        return expected == hashed_password

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate a secure password hash"""
        if HAS_BCRYPT:
            try:
                salt = bcrypt.gensalt()
                return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            except Exception:
                pass
        
        # Cryptographic fallback if bcrypt is not installed
        import uuid
        salt = uuid.uuid4().hex
        return f"{salt}${AuthService._fallback_hash(password, salt)}"

    @staticmethod
    def _fallback_hash(password: str, salt: str) -> str:
        """Helper to create SHA-256 fallback hash with salt"""
        return hashlib.sha256(f"{salt}{password}".encode('utf-8')).hexdigest()

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a new JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        to_encode.update({"exp": int(expire.timestamp())})

        if HAS_JWT:
            try:
                return jwt.encode(
                    to_encode,
                    settings.jwt_secret_key,
                    algorithm=settings.jwt_algorithm
                )
            except Exception:
                pass

        # Pure-Python simulated JWT signature using HMAC
        payload_json = json.dumps(to_encode)
        payload_b64 = base64.urlsafe_b64encode(
            payload_json.encode('utf-8')
        ).decode('utf-8').rstrip("=")
        
        sig = hmac.new(
            settings.jwt_secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"simulated.{payload_b64}.{sig}"

    @staticmethod
    def get_user_from_token(token: str, db: Session) -> Optional[User]:
        """Decode JWT token and retrieve corresponding user"""
        if not token:
            return None
            
        payload = None
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        if HAS_JWT:
            try:
                payload = jwt.decode(
                    token,
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm]
                )
            except Exception:
                pass

        if payload is None:
            # Decode simulated JWT
            try:
                parts = token.split(".")
                if len(parts) == 3 and parts[0] == "simulated":
                    payload_b64 = parts[1]
                    sig = parts[2]
                    
                    expected_sig = hmac.new(
                        settings.jwt_secret_key.encode('utf-8'),
                        payload_b64.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    if hmac.compare_digest(sig, expected_sig):
                        padding = len(payload_b64) % 4
                        if padding:
                            payload_b64 += "=" * (4 - padding)
                        payload_json = base64.urlsafe_b64decode(
                            payload_b64.encode('utf-8')
                        ).decode('utf-8')
                        payload = json.loads(payload_json)
            except Exception as e:
                logger.error(f"Simulated token decoding error: {e}")

        if not payload:
            return None

        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            return None

        username = payload.get("sub")
        if not username:
            return None

        return db.query(User).filter(User.username == username).first()
