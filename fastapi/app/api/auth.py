from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings


bearer = HTTPBearer(auto_error=True)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token") from exc
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Authentication token has no subject")
    return payload


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict[str, Any]:
    return decode_token(credentials.credentials)


async def authenticate_websocket(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return False
    try:
        decode_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid or expired authentication token")
        return False
    return True
