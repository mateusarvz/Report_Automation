import importlib
import sys


def test_root_main_module_exposes_app(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", raising=False)

    sys.modules.pop("app.main", None)
    sys.modules.pop("app.auth", None)
    sys.modules.pop("main", None)

    module = importlib.import_module("main")
    assert module.app is not None


def test_app_imports_without_supabase_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", raising=False)

    sys.modules.pop("app.main", None)
    sys.modules.pop("app.auth", None)

    module = importlib.import_module("app.main")
    assert module.app is not None
