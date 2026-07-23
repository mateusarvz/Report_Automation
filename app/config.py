import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILES = (BASE_DIR / ".env.local", BASE_DIR / ".env")


def load_environment() -> None:
    for env_file in ENV_FILES:
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)


@lru_cache(maxsize=1)
def get_settings() -> dict:
    load_environment()
    return {
        "secret_key": os.getenv("SECRET_KEY", "dev-secret-key"),
        "supabase_url": os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
        "supabase_key": (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        ),
    }
