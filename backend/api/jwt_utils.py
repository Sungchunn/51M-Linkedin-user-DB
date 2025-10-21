"""
JWT Token Utilities
Handles JWT token creation, validation, and refresh logic
"""

import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    NEGATIVE SPACE CONTRACT:
    - password must not be empty
    - Returns bcrypt hash string
    """
    if not password or len(password.strip()) == 0:
        raise ValueError("NEGATIVE SPACE: Password cannot be empty")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    NEGATIVE SPACE CONTRACT:
    - Returns False if passwords don't match
    - Returns False if hash is invalid
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    NEGATIVE SPACE CONTRACT:
    - data must contain 'sub' (subject/user_id)
    - Tokens expire after JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    - Returns signed JWT string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token with longer expiration.

    NEGATIVE SPACE CONTRACT:
    - data must contain 'sub' (subject/user_id)
    - Tokens expire after JWT_REFRESH_TOKEN_EXPIRE_DAYS
    - Returns signed JWT string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    NEGATIVE SPACE CONTRACT:
    - Returns None if token is invalid or expired
    - Returns payload dict if valid
    - Validates signature and expiration
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_user_id(token: str) -> Optional[str]:
    """
    Extract user_id from token.

    NEGATIVE SPACE CONTRACT:
    - Returns None if token is invalid
    - Returns user_id string if valid
    """
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired.

    NEGATIVE SPACE CONTRACT:
    - Returns True if expired or invalid
    - Returns False if still valid
    """
    payload = decode_token(token)
    return payload is None
