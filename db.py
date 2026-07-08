from typing import Optional
import os
import httpx
from dotenv import load_dotenv


class SupabaseClientError(RuntimeError):
    pass

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


def _raise_for_status(response: httpx.Response):
    if response.is_error:
        raise SupabaseClientError(f"Supabase request failed: {response.status_code} {response.text}")
    return response


def save_google_user(
    user_id: str,
    email: str,
    full_name: Optional[str],
    picture: Optional[str],
    access_token: Optional[str] = None,
):
    payload = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "photo_url": picture,
    }
    headers = {"Prefer": "resolution=merge-duplicates"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        headers["apikey"] = SUPABASE_KEY
    response = _client.post(
        "/rest/v1/profiles?on_conflict=id&return=representation",
        json=payload,
        headers=headers,
    )
    _raise_for_status(response)
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
    _raise_for_status(response)
    return response.json()


def load_user_profile(user_id: Optional[str] = None, email: Optional[str] = None):
    params = {"select": "id,email,full_name,photo_url"}
    if user_id:
        params["id"] = f"eq.{user_id}"
    elif email:
        params["email"] = f"eq.{email}"
    else:
        raise ValueError("user_id or email is required")

    response = _client.get("/rest/v1/profiles", params=params)
    _raise_for_status(response)
    data = response.json()
    return data[0] if isinstance(data, list) and data else None


def get_user_patients(psychologist_id: str):
    response = _client.get(
        "/rest/v1/patients",
        params={
            "select": "id,full_name,birth_date,gender,phone,email,created_at,updated_at",
            "psychologist_id": f"eq.{psychologist_id}",
            "order": "created_at.desc",
        },
    )
    _raise_for_status(response)
    return response.json()


def find_patient_by_name(psychologist_id: str, full_name: str):
    response = _client.get(
        "/rest/v1/patients",
        params={
            "select": "id,psychologist_id,full_name,birth_date,gender,phone,email,created_at,updated_at",
            "psychologist_id": f"eq.{psychologist_id}",
            "full_name": f"eq.{full_name}",
            "limit": 1,
        },
    )
    _raise_for_status(response)
    data = response.json()
    return data[0] if isinstance(data, list) and data else None


def create_patient(psychologist_id: str, patient_data: dict):
    payload = {"psychologist_id": psychologist_id, **patient_data}
    response = _client.post(
        "/rest/v1/patients",
        headers={"Prefer": "return=representation"},
        json=payload,
    )
    _raise_for_status(response)
    data = response.json()
    return data[0] if isinstance(data, list) and data else None
