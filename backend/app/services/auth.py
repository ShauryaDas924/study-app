import os
from uuid import UUID
from fastapi import Header, HTTPException

def _env_true(v: str | None) -> bool:
    return (v or "").lower() in ("1", "true", "yes", "y", "on")

DEV_MODE = _env_true(os.getenv("DEV_MODE"))
DEV_USER_ID = os.getenv("DEV_USER_ID", "00000000-0000-0000-0000-000000000001")

async def get_current_user_id(authorization: str | None = Header(default=None)):
    # Dev-mode bypass
    if DEV_MODE:
        return UUID(DEV_USER_ID)

    # Real auth (later): require Bearer token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")

    # In production you would decode JWT + verify
    raise HTTPException(501, "Auth not implemented yet (turn on DEV_MODE=true)")
