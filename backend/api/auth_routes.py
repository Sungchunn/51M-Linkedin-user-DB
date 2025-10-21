"""
Authentication Routes
Handles user registration, login, and API key management
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import logging
import os

from backend.api.models import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyListItem
)
from backend.api.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_user_id
)
from backend.api.user_manager import UserManager, APIKeyManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


# ==================== DEPENDENCY: Get Current User ====================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Get current user from JWT token.

    NEGATIVE SPACE CONTRACT:
    - Raises 401 if token is missing or invalid
    - Raises 401 if token is expired
    - Returns user dict if valid
    """
    token = credentials.credentials

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user = await UserManager.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


# ==================== ROUTES ====================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(request: UserRegisterRequest):
    """
    Register a new user account.

    NEGATIVE SPACE CONTRACT:
    - Raises 403 if registration is disabled
    - Raises 400 if username/email already exists
    - Returns user profile on success
    """
    allow_registration = os.getenv("ALLOW_USER_REGISTRATION", "true").lower() == "true"
    if not allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User registration is disabled"
        )

    user = await UserManager.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        full_name=request.full_name
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )

    logger.info(f"New user registered: {user['username']}")
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest):
    """
    Login with username and password.

    NEGATIVE SPACE CONTRACT:
    - Raises 401 if credentials are invalid
    - Returns JWT access and refresh tokens
    """
    user = await UserManager.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user['id'], "username": user['username']})
    refresh_token = create_refresh_token(data={"sub": user['id']})

    # Calculate expiration
    expires_in = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60  # seconds

    logger.info(f"User logged in: {user['username']}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile.

    NEGATIVE SPACE CONTRACT:
    - Requires valid JWT token
    - Returns current user profile
    """
    return UserResponse(**current_user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_token: str):
    """
    Refresh access token using refresh token.

    NEGATIVE SPACE CONTRACT:
    - Raises 401 if refresh token is invalid or expired
    - Returns new access and refresh tokens
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    user = await UserManager.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Create new tokens
    access_token = create_access_token(data={"sub": user['id'], "username": user['username']})
    new_refresh_token = create_refresh_token(data={"sub": user['id']})

    expires_in = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in
    )


# ==================== API KEY MANAGEMENT ====================

@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new API key for the current user.

    NEGATIVE SPACE CONTRACT:
    - Requires authentication
    - Returns full API key (only shown once!)
    - API key is hashed before storage
    """
    api_key_data = await APIKeyManager.create_api_key(
        user_id=current_user['id'],
        key_name=request.key_name,
        scopes=request.scopes,
        tier=request.tier,
        expires_in_days=request.expires_in_days
    )

    logger.info(f"API key created: {request.key_name} for user {current_user['username']}")

    return APIKeyResponse(**api_key_data)


@router.get("/api-keys", response_model=List[APIKeyListItem])
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """
    List all API keys for the current user.

    NEGATIVE SPACE CONTRACT:
    - Requires authentication
    - Returns list without full API keys (only prefixes)
    """
    api_keys = await APIKeyManager.get_user_api_keys(current_user['id'])
    return [APIKeyListItem(**key) for key in api_keys]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoke an API key.

    NEGATIVE SPACE CONTRACT:
    - Requires authentication
    - Key must belong to current user
    - Raises 404 if key not found or doesn't belong to user
    """
    success = await APIKeyManager.revoke_api_key(key_id, current_user['id'])

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or doesn't belong to you"
        )

    logger.info(f"API key revoked: {key_id} by user {current_user['username']}")
    return None
