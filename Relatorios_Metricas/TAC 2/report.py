def get_input_schema():
    # three integer inputs with ranges
    return [
        {
            "name": "pontuacao_primeira_parte",
            "label": "Pontuação Primeira parte",
            "type": "number",
            "placeholder": "0 - 50",
            "required": True,
            "min": 0,
            "max": 50,
        },
        {
            "name": "pontuacao_segunda_parte",
            "label": "Pontuação Segunda parte",
            "type": "number",
            "placeholder": "0 - 7",
            "required": True,
            "min": 0,
            "max": 7,
        },
        {
            "name": "pontuacao_terceira_parte",
            "label": "Pontuação Terceira parte",
            "type": "number",
            "placeholder": "0 - 52",
            "required": True,
            "min": 0,
            "max": 52,
        },
    ]


def build_report(patient_id, patient_name, input_data):
    # optional entrypoint when module loaded directly.
    # use dynamic import to avoid package issues
    import importlib.util
    from pathlib import Path

    report_dir = Path(__file__).resolve().parents[0]
    module_file = report_dir / 'TAC2_report.py'
    spec = importlib.util.spec_from_file_location(
        'tac2_module', str(module_file)
    )
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
        if hasattr(module, 'build_tac2_report'):
            return module.build_tac2_report(
                None, patient_id, patient_name, input_data,
                report_dir=report_dir
            )
    raise RuntimeError('TAC2 build_report not available')
