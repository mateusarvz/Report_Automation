import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


class DummyResponse:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error


class DummyTable:
    def __init__(self, client):
        self.client = client

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return DummyResponse(data=[{"id": self.client.user_id, "full_name": "Paciente Teste"}])


class DummyClient:
    def __init__(self, user_id):
        self.user_id = user_id

    def table(self, _name):
        return DummyTable(self)


def test_tac2_report_does_not_save_dataframe_files(monkeypatch):
    fake_client = DummyClient("user-123")

    monkeypatch.setattr(main_module, "get_user_from_session", lambda request: {"id": "user-123"})
    monkeypatch.setattr(main_module, "get_authenticated_client", lambda request: fake_client)
    monkeypatch.setattr(main_module, "get_report_folders", lambda: ["TAC 2"])
    monkeypatch.setattr(
        main_module,
        "build_tac2_dataframes",
        lambda client, patient_id, patient_name, input_data: {
            "results": pd.DataFrame([{"patient_id": patient_id, "score_total_mapeado": 10.0}]),
        },
    )

    def fail_save_dataframe(*args, **kwargs):
        raise AssertionError("TAC2 should not save dataframe files")

    monkeypatch.setattr(main_module, "save_dataframe", fail_save_dataframe)

    client = TestClient(app)
    response = client.post(
        "/api/reports",
        json={
            "patient_id": "user-123",
            "report_name": "TAC 2",
            "input_data": {"pontuacao_primeira_parte": 10},
        },
    )

    assert response.status_code == 200
    assert response.json()["report_name"] == "TAC 2"
    assert response.json()["report_results"]["score_total_mapeado"] == 10.0
