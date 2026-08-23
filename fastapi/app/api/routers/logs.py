from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter(prefix="/api")


@router.get("/logs/ping")
async def logs_ping() -> Dict[str, Any]:
    # Minimal endpoint suitable for v1 uptime checks / alerting.
    return {"status": "ok", "ts": int(time.time()), "iso": datetime.utcnow().isoformat() + 'Z'}

