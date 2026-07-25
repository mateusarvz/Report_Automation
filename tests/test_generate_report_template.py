from pathlib import Path


def test_generate_report_template_has_separate_input_and_action_blocks():
    template_path = Path(__file__).resolve().parents[1] / "templates" / "generate_report.html"
    html = template_path.read_text(encoding="utf-8")

    assert 'id="report-input-container"' in html
    assert 'id="report-results-container"' in html
    assert 'Gerar relatório' in html


def test_report_input_fields_include_observacoes():
    from app.report_store import get_report_input_fields

    fields = get_report_input_fields("TAC 2")
    assert any(field.get("name") == "observacoes_sobre_o_teste" for field in fields)
    observation_field = next(field for field in fields if field.get("name") == "observacoes_sobre_o_teste")
    assert observation_field["type"] == "textarea"
