import importlib.util
from pathlib import Path


def _load_tac2_module():
    module_path = Path(__file__).resolve().parents[1] / "Relatorios_Metricas" / "TAC 2" / "TAC2_report.py"
    spec = importlib.util.spec_from_file_location("tac2_report_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyResponse:
    def __init__(self, data=None):
        self.data = data or []


class DummyQuery:
    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return DummyResponse([{"birth_date": "2000-01-01"}])


class DummyClient:
    def table(self, _name):
        return DummyQuery()


def test_tac2_score_category_thresholds():
    module = _load_tac2_module()

    assert module.classify_score_metric(69) == "Muito Baixa"
    assert module.classify_score_metric(70) == "Baixa"
    assert module.classify_score_metric(84) == "Baixa"
    assert module.classify_score_metric(85) == "Média"
    assert module.classify_score_metric(114) == "Média"
    assert module.classify_score_metric(115) == "Alta"
    assert module.classify_score_metric(129) == "Alta"
    assert module.classify_score_metric(130) == "Muito Alta"


def test_tac2_report_keeps_category_text():
    module = _load_tac2_module()
    report_dir = Path(__file__).resolve().parents[1] / "Relatorios_Metricas" / "TAC 2"
    result = module.build_tac2_report(
        DummyClient(),
        "patient-1",
        "Paciente Teste",
        {
            "pontuacao_primeira_parte": 10,
            "pontuacao_segunda_parte": 10,
            "pontuacao_terceira_parte": 10,
        },
        report_dir=report_dir,
    )
    row = result["results"].iloc[0]

    assert isinstance(row["pontuacao_primeira_parte_categoria"], str)
    assert isinstance(row["pontuacao_segunda_parte_categoria"], str)
    assert isinstance(row["pontuacao_terceira_parte_categoria"], str)
    assert row["pontuacao_primeira_parte_categoria"] in {"Muito Baixa", "Baixa", "Média", "Alta", "Muito Alta"}
