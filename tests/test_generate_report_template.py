from pathlib import Path


def test_generate_report_template_has_separate_input_and_action_blocks():
    template_path = Path(__file__).resolve().parents[1] / "templates" / "generate_report.html"
    html = template_path.read_text(encoding="utf-8")

    assert 'id="report-input-container"' in html
    assert 'id="report-results-container"' in html
    assert 'Gerar relatório' in html
