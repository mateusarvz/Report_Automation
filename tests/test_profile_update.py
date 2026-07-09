from fastapi.testclient import TestClient

import app.main as main_module
from app.auth import build_display_name
from app.main import app


class DummyResponse:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error


class DummyTable:
    def __init__(self, client):
        self.client = client
        self.update_payload = None
        self.eq_filter = None

    def update(self, payload):
        self.update_payload = payload
        return self

    def eq(self, column, value):
        self.eq_filter = (column, value)
        return self

    def execute(self):
        self.client.updated_rows.append(self.update_payload)
        return DummyResponse(data=[{"id": self.client.user_id, "full_name": self.update_payload.get("full_name"), "profession": self.update_payload.get("profession")}] )


class DummyClient:
    def __init__(self, user_id):
        self.user_id = user_id
        self.updated_rows = []

    def table(self, _name):
        return DummyTable(self)


def test_update_profile_updates_only_current_user_profile(monkeypatch):
    fake_client = DummyClient("user-123")

    monkeypatch.setattr(main_module, "get_user_from_session", lambda request: {"id": "user-123", "email": "user@example.com", "full_name": "Old Name", "profession": "Old Profession"})
    monkeypatch.setattr(main_module, "get_authenticated_client", lambda request: fake_client)

    client = TestClient(app)
    response = client.post(
        "/account/update-profile",
        data={"full_name": "New Name", "profession": "Psychologist"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/account?updated=1"
    assert len(fake_client.updated_rows) == 1
    assert fake_client.updated_rows[0]["full_name"] == "New Name"
    assert fake_client.updated_rows[0]["profession"] == "Psychologist"


def test_build_display_name_uses_profession_and_gender_prefix():
    assert build_display_name({"full_name": "Ana Silva", "profession": "Psicólogo(a)", "gender": "Feminino"}) == "Dra. Ana Silva"
    assert build_display_name({"full_name": "João Silva", "profession": "Psicólogo(a)", "gender": "Masculino"}) == "Dr. João Silva"
    assert build_display_name({"full_name": "Ana Silva", "profession": "Terapeuta", "gender": "Feminino"}) == "Ana Silva"
    assert build_display_name({"full_name": "Ana Silva", "profession": "Neuropsicólogo(a)", "gender": "Outro"}) == "Ana Silva"
