# auth.py - JWT-based authentication for API
from __future__ import annotations

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import AUTH_DISABLED, JWT_SECRET

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
DEV_USER_ID_HEADER = "X-User-Id"


def get_user_id_from_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if not JWT_SECRET:
        logger.warning("JWT_SECRET not set; auth will reject all requests unless AUTH_DISABLED=1")
        return None
    if not credentials or credentials.scheme != "Bearer":
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user_id = payload.get("sub")
        return str(user_id).strip() if user_id else None
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid JWT: %s", e)
        return None


def require_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Dependency: returns authenticated user_id.
    - When AUTH_DISABLED=1 (dev): reads user_id from X-User-Id header.
    - Otherwise: validates JWT Bearer and returns 'sub' claim.
    Raises 401 if user_id cannot be determined.
    """
    if AUTH_DISABLED:
        dev_uid = request.headers.get(DEV_USER_ID_HEADER, "").strip()
        if dev_uid:
            return dev_uid
        path_uid = request.path_params.get("user_id", "").strip()
        if path_uid:
            return path_uid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="When AUTH_DISABLED=1, provide X-User-Id header or user_id in path",
        )
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured",
        )
    user_id = get_user_id_from_token(credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization",
        )
    return user_id


def validate_path_user_id(
    request: Request,
    auth_user_id: str = Depends(require_user_id),
) -> str:
    """Dependency for routes with {user_id} in path: ensures path matches authenticated user."""
    path_user_id = request.path_params.get("user_id", "")
    if path_user_id != auth_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return path_user_id
