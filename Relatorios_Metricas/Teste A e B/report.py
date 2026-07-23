def get_input_schema():
    return [
        {
            "name": "resultado_parte_a",
            "label": "Resultados parte A",
            "type": "number",
            "placeholder": "7 - 24",
            "required": True,
            "min": 7,
            "max": 24,
        },
        {
            "name": "resultado_parte_b",
            "label": "Resultado da parte B",
            "type": "number",
            "placeholder": "1 - 24",
            "required": True,
            "min": 1,
            "max": 24,
        },
        {
            "name": "resultado_parte_ba",
            "label": "Resultado da parte B-A",
            "type": "number",
            "placeholder": "0 a -24",
            "required": True,
            "min": -24,
            "max": 0,
        },
    ]


def _validate_inputs(input_data):
    rules = {
        "resultado_parte_a": (7, 24),
        "resultado_parte_b": (1, 24),
        "resultado_parte_ba": (-24, 0),
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
    module_file = report_dir / "teste_trilhas_report.py"
    spec = importlib.util.spec_from_file_location("teste_trilhas_module", str(module_file))
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
        _validate_inputs(input_data or {})
        return module.build_teste_trilhas_report(None, patient_id, patient_name, input_data, report_dir=report_dir)
    raise RuntimeError("Teste Trilhas build_report not available")
