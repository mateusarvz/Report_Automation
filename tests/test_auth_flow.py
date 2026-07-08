import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient

import main


def test_health_endpoint():
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_redirect_url_uses_render_headers():
    class DummyRequest:
        def __init__(self):
            self.headers = {
                "x-forwarded-proto": "https",
                "x-forwarded-host": "report-automation-tcht.onrender.com",
            }

        def url_for(self, name):
            return f"http://localhost:8000/{name}"

    request = DummyRequest()
    assert main.get_auth_redirect_url(request) == "https://report-automation-tcht.onrender.com/auth/callback"
