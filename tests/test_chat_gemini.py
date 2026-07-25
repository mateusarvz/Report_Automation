import pytest
from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

def test_chat_gemini_page_redirect_when_not_authenticated(monkeypatch):
    monkeypatch.setattr(main_module, "get_user_from_session", lambda request: None)
    client = TestClient(app)
    response = client.get("/chat-gemini", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_chat_gemini_page_loads_when_authenticated(monkeypatch):
    monkeypatch.setattr(main_module, "get_user_from_session", lambda request: {"id": "user-123", "email": "user@example.com"})
    client = TestClient(app)
    response = client.get("/chat-gemini")
    assert response.status_code == 200
    assert "Chat Gemini" in response.text

def test_api_chat_gemini_success(monkeypatch):
    monkeypatch.setattr(main_module, "get_user_from_session", lambda request: {"id": "user-123", "email": "user@example.com"})
    monkeypatch.setenv("GEMINI_API_KEY", "fake-api-key")
    
    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, json, timeout):
            assert "fake-api-key" in url
            return MockResponse({
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Olá do Gemini!"}
                            ]
                        }
                    }
                ]
            })

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
    
    client = TestClient(app)
    response = client.post("/api/chat-gemini", json={
        "contents": [{"role": "user", "parts": [{"text": "Oi"}]}]
    })
    
    assert response.status_code == 200
    assert response.json() == {"text": "Olá do Gemini!"}
