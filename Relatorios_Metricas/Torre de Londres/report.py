def get_input_schema():
    return [
        {
            "name": "pontuacao_total",
            "label": "Pontuação Total",
            "type": "number",
            "placeholder": "1 - 36",
            "required": True,
            "min": 1,
            "max": 36,
        },
        {
            "name": "pontuacao_4_movimentos",
            "label": "Pontuação nos itens de 4 movimentos",
            "type": "number",
            "placeholder": "1 - 12",
            "required": True,
            "min": 1,
            "max": 12,
        },
        {
            "name": "pontuacao_5_movimentos",
            "label": "Pontuação nos itens de 5 movimentos",
            "type": "number",
            "placeholder": "1 - 12",
            "required": True,
            "min": 1,
            "max": 12,
        },
    ]


def _validate_inputs(input_data):
    rules = {
        "pontuacao_total": (1, 36),
        "pontuacao_4_movimentos": (1, 12),
        "pontuacao_5_movimentos": (1, 12),
    }
    for field, (min_value, max_value) in rules.items():
        value = input_data.get(field)
        if value is None:
            raise ValueError(f"{field} é obrigatório")
        try:
            numeric = int(value)
        except Exception as exc:
            raise ValueError(f"{field} deve ser numérico") from exc
        if numeric < min_value or numeric > max_value:
            raise ValueError(f"{field} fora da faixa permitida")


def build_report(patient_id, patient_name, input_data):
    import importlib.util
    from pathlib import Path

    report_dir = Path(__file__).resolve().parents[0]
    module_file = report_dir / "torre_londres_report.py"
    spec = importlib.util.spec_from_file_location("torre_londres_module", str(module_file))
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
        _validate_inputs(input_data or {})
        return module.build_torre_londres_report(None, patient_id, patient_name, input_data, report_dir=report_dir)
    raise RuntimeError("Torre de Londres build_report not available")
