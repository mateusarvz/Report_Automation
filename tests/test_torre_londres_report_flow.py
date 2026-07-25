import pytest
import pandas as pd
from fastapi.testclient import TestClient
from pathlib import Path
import importlib.util

def load_module(name, filepath):
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

report_dir = Path("Relatorios_Metricas/Torre de Londres")
report_module = load_module("report", report_dir / "report.py")
torre_londres_report_module = load_module("torre_londres_report", report_dir / "torre_londres_report.py")

class DummyResponse:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error


class DummyTable:
    def __init__(self, birth_date):
        self.birth_date = birth_date

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return DummyResponse(data=[{"birth_date": self.birth_date}])


class DummyClient:
    def __init__(self, birth_date):
        self.birth_date = birth_date

    def table(self, _name):
        return DummyTable(self.birth_date)


def test_torre_londres_input_schema():
    schema = report_module.get_input_schema()
    names = [field["name"] for field in schema]
    assert "pontuacao_total" in names
    assert "pontuacao_4_movimentos" in names
    assert "pontuacao_5_movimentos" in names

    total_field = next(f for f in schema if f["name"] == "pontuacao_total")
    assert total_field["min"] == 0
    assert total_field["max"] == 36

    m4_field = next(f for f in schema if f["name"] == "pontuacao_4_movimentos")
    assert m4_field["min"] == 0
    assert m4_field["max"] == 12


def test_classify_score_metric():
    classify = torre_londres_report_module.classify_score_metric
    assert classify(69) == "Muito Baixa"
    assert classify(70) == "Baixa"
    assert classify(84) == "Baixa"
    assert classify(85) == "M\u00e9dia"
    assert classify(114) == "M\u00e9dia"
    assert classify(115) == "Alta"
    assert classify(129) == "Alta"
    assert classify(130) == "Muito Alta"


def test_build_torre_londres_report():
    client = DummyClient("2014-07-25")  # 12 years old if today is 2026-07-25
    
    input_data = {
        "pontuacao_total": 20,
        "pontuacao_4_movimentos": 6,
        "pontuacao_5_movimentos": 6,
    }
    
    html_report = torre_londres_report_module.build_torre_londres_report(client, "pat-123", "Paciente Teste", input_data, report_dir=report_dir)
    print("HTML_REPORT:", html_report)
    
    assert "ToL (Teste da Torre de Londres)" in html_report
    assert "Pontua\u00e7\u00e3o Total" in html_report
    assert "Pontua\u00e7\u00e3o nos itens de 4 movimentos" in html_report
    assert "Pontua\u00e7\u00e3o nos itens de 5 movimentos" in html_report
