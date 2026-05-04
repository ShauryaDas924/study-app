import os
from uuid import UUID

import httpx
from fastapi import Header, HTTPException

def _env_true(v: str | None) -> bool:
    return (v or "").lower() in ("1", "true", "yes", "y", "on")

DEV_MODE = _env_true(os.getenv("DEV_MODE"))
DEV_USER_ID = os.getenv("DEV_USER_ID", "00000000-0000-0000-0000-000000000001")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

async def get_current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if DEV_MODE:
        return UUID(DEV_USER_ID)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Auth is not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {token}",
                },
            )

        if res.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        data = res.json()
        user_id = data.get("id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return UUID(user_id)

    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
