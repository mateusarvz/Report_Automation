from typing import Optional
import os
import httpx
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY are required in .env or .env.local"
    )

_client = httpx.Client(
    base_url=SUPABASE_URL,
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    },
    timeout=10.0,
)


def save_google_user(email: str, full_name: Optional[str], picture: Optional[str]):
    payload = {
        "email": email,
        "full_name": full_name,
        "photo_url": picture,
    }
    response = _client.post(
        "/rest/v1/profiles?on_conflict=email&return=representation",
        json=payload,
        headers={"Prefer": "resolution=merge-duplicates"},
    )
    response.raise_for_status()
    return response.json()


def get_supabase_user(access_token: str):
    response = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def load_user_profile(email: str):
    response = _client.get(
        "/rest/v1/profiles",
        params={"select": "id,email,full_name,photo_url", "email": f"eq.{email}"},
    )
    response.raise_for_status()
    data = response.json()
    return data[0] if isinstance(data, list) and data else None
