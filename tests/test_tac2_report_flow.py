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
        "build_tac2_text_report",
        lambda client, patient_id, patient_name, input_data: (
            "TAC (Teste de atenção por cancelamento)\n"
            "O TAC é um instrumento utilizado para avaliar a atenção sustentada, a atenção seletiva, a velocidade de processamento visual e o controle atencional.\n"
            "\n"
            "RESULTADOS\n"
            "| Indicador | Pontuação | Classificação |\n"
            "|-----------|-----------|---------------|\n"
            "| Geral | 10 | Baixa |\n"
        ),
    )

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
    assert response.headers["content-type"].startswith("text/html")
    assert "TAC (Teste de atenção por cancelamento)" in response.text
    assert "Paciente:" not in response.text
    assert "Idade:" not in response.text
    assert "| Indicador | Pontuação | Classificação |" in response.text
