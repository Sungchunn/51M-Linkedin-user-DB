"""
User and API Key Management
Database operations for users, authentication, and API keys
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
import asyncpg

from backend.api.jwt_utils import hash_password, verify_password
from backend.api import database


class UserManager:
    """Manages user accounts and authentication"""

    @staticmethod
    async def create_admin_if_not_exists():
        """
        Create admin user on startup if it doesn't exist.

        NEGATIVE SPACE CONTRACT:
        - Uses ADMIN_USERNAME and ADMIN_PASSWORD from env
        - Idempotent: safe to call multiple times
        - Admin user has is_admin=TRUE
        """
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin")

        # Truncate password to 72 bytes for bcrypt (which is the max)
        if len(admin_password) > 72:
            admin_password = admin_password[:72]

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Check if admin exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1",
                admin_username
            )

            if not existing:
                password_hash = hash_password(admin_password)
                await conn.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, is_admin, is_active, email_verified)
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, TRUE)
                """, admin_username, f"{admin_username}@prospectiq.local", password_hash, "Administrator")
                print(f"✅ Admin user '{admin_username}' created")

    @staticmethod
    async def create_user(username: str, email: str, password: str, full_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new user account.

        NEGATIVE SPACE CONTRACT:
        - username must be unique and >= 3 chars
        - email must be unique and valid format
        - password must not be empty
        - Returns user dict or None if username/email exists
        """
        # Validate registration is allowed
        allow_registration = os.getenv("ALLOW_USER_REGISTRATION", "true").lower() == "true"
        if not allow_registration:
            return None

        password_hash = hash_password(password)

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            try:
                user = await conn.fetchrow("""
                    INSERT INTO users (username, email, password_hash, full_name)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, username, email, full_name, is_admin, is_active, created_at, last_login_at
                """, username, email, password_hash, full_name)

                # Log audit
                await conn.execute("""
                    INSERT INTO audit_log (user_id, action, resource_type, resource_id)
                    VALUES ($1, 'user.created', 'user', $1)
                """, user['id'])

                # Convert to dict and fix UUID
                user_dict = dict(user)
                user_dict['id'] = str(user_dict['id'])
                return user_dict
            except asyncpg.UniqueViolationError:
                return None

    @staticmethod
    async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with username/password.

        NEGATIVE SPACE CONTRACT:
        - Returns None if username not found
        - Returns None if password is incorrect
        - Returns None if user is not active
        - Returns user dict if authenticated
        """
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT id, username, email, password_hash, full_name, is_admin, is_active
                FROM users
                WHERE username = $1 AND is_active = TRUE
            """, username)

            if not user:
                return None

            if not verify_password(password, user['password_hash']):
                return None

            # Update last login
            await conn.execute("""
                UPDATE users SET last_login_at = NOW() WHERE id = $1
            """, user['id'])

            # Log audit
            await conn.execute("""
                INSERT INTO audit_log (user_id, action)
                VALUES ($1, 'user.login')
            """, user['id'])

            # Return user without password hash
            return {
                'id': str(user['id']),
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'is_admin': user['is_admin'],
                'is_active': user['is_active']
            }

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT id, username, email, full_name, is_admin, is_active, created_at, last_login_at
                FROM users
                WHERE id = $1 AND is_active = TRUE
            """, UUID(user_id))

            if user:
                user_dict = dict(user)
                user_dict['id'] = str(user_dict['id'])
                return user_dict
            return None


class APIKeyManager:
    """Manages API keys for programmatic access"""

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """
        Generate a new API key.

        NEGATIVE SPACE CONTRACT:
        - Returns (api_key, key_prefix)
        - api_key is 64 hex chars (32 bytes)
        - key_prefix is first 16 chars for display
        """
        # Generate 32 random bytes (64 hex chars)
        key_bytes = secrets.token_bytes(32)
        api_key = key_bytes.hex()

        # Prefix for display (first 16 chars)
        key_prefix = api_key[:16]

        return api_key, key_prefix

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for storage.

        NEGATIVE SPACE CONTRACT:
        - Returns SHA-256 hash of api_key
        - Used for secure comparison
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    async def create_api_key(
        user_id: str,
        key_name: str,
        scopes: List[str],
        tier: str = "basic",
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key for a user.

        NEGATIVE SPACE CONTRACT:
        - user_id must exist in users table
        - key_name must be >= 3 chars
        - tier must be in: public, basic, trusted
        - Returns: {api_key, key_prefix, ...}
        - WARNING: api_key is only returned once!
        """
        api_key, key_prefix = APIKeyManager.generate_api_key()
        key_hash = APIKeyManager.hash_api_key(api_key)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO api_keys (user_id, key_name, api_key, key_prefix, scopes, tier, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, user_id, key_name, key_prefix, scopes, tier, is_active, created_at
            """, UUID(user_id), key_name, key_hash, key_prefix, scopes, tier, expires_at)

            # Log audit
            import json
            await conn.execute("""
                INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
                VALUES ($1, 'api_key.created', 'api_key', $2, $3::jsonb)
            """, UUID(user_id), result['id'], json.dumps({"key_name": key_name, "tier": tier}))

            return {
                'id': str(result['id']),
                'api_key': api_key,  # ONLY returned here!
                'key_prefix': key_prefix,
                'key_name': key_name,
                'scopes': result['scopes'],
                'tier': tier,
                'is_active': result['is_active'],
                'created_at': result['created_at']
            }

    @staticmethod
    async def get_user_api_keys(user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.

        NEGATIVE SPACE CONTRACT:
        - Returns list of api_keys (without full api_key)
        - Only returns key_prefix for display
        """
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, key_name, key_prefix, scopes, tier, is_active, usage_count,
                       last_used_at, expires_at, created_at
                FROM api_keys
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, UUID(user_id))

            result = []
            for row in rows:
                key_dict = dict(row)
                key_dict['id'] = str(key_dict['id'])
                result.append(key_dict)
            return result

    @staticmethod
    async def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify an API key and return its metadata.

        NEGATIVE SPACE CONTRACT:
        - Returns None if key not found or inactive
        - Returns None if key is expired
        - Returns key metadata with user_id if valid
        - Increments usage_count
        """
        key_hash = APIKeyManager.hash_api_key(api_key)

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            key_data = await conn.fetchrow("""
                SELECT id, user_id, key_name, scopes, tier, is_active, expires_at
                FROM api_keys
                WHERE api_key = $1 AND is_active = TRUE
            """, key_hash)

            if not key_data:
                return None

            # Check expiration
            if key_data['expires_at'] and key_data['expires_at'] < datetime.utcnow():
                return None

            # Update usage stats
            await conn.execute("""
                UPDATE api_keys
                SET usage_count = usage_count + 1, last_used_at = NOW()
                WHERE id = $1
            """, key_data['id'])

            return {
                'user_id': str(key_data['user_id']),
                'key_name': key_data['key_name'],
                'scopes': key_data['scopes'],
                'tier': key_data['tier']
            }

    @staticmethod
    async def revoke_api_key(key_id: str, user_id: str) -> bool:
        """
        Revoke an API key.

        NEGATIVE SPACE CONTRACT:
        - key must belong to user_id
        - Returns True if revoked successfully
        - Returns False if key not found or doesn't belong to user
        """
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE api_keys
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = $1 AND user_id = $2
            """, UUID(key_id), UUID(user_id))

            if result == "UPDATE 1":
                # Log audit
                await conn.execute("""
                    INSERT INTO audit_log (user_id, action, resource_type, resource_id)
                    VALUES ($1, 'api_key.revoked', 'api_key', $2)
                """, UUID(user_id), UUID(key_id))
                return True

            return False
