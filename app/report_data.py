import importlib.util
from pathlib import Path

import pandas as pd

from app.report_store import report_folder_path


def _load_tac2_module(report_dir: Path):
    module_file = report_dir / 'TAC2_report.py'
    if not module_file.exists():
        raise FileNotFoundError(
            f"TAC2 report module not found at {module_file}"
        )
    importlib.invalidate_caches()
    module_name = f"tac2_module_{module_file.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(
        module_name, str(module_file)
    )
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
        return module
    raise ImportError("Failed to load TAC2 module")


def build_tac2_dataframes(
    client,
    patient_id: str,
    patient_name: str,
    input_data: dict = None,
) -> dict:
    """Load TAC2 CSVs from disk, compute mapped scores, and return DataFrames.

    This reads the TAC2 CSV files each time the report is generated so that
    any external CSV edits are reflected immediately in the calculations.

    Returns dict where keys are dataframe names and values are pandas.DataFrame
    """
    input_data = input_data or {}
    report_dir = report_folder_path('TAC 2')
    tac2 = _load_tac2_module(report_dir)

    # delegate to TAC2_report.build_tac2_report
    if not hasattr(tac2, 'build_tac2_report'):
        raise RuntimeError('TAC2_report.build_tac2_report not found')

    result = tac2.build_tac2_report(
        client,
        patient_id,
        patient_name,
        input_data,
        report_dir=report_dir,
    )
    # expect result to be dict of DataFrames
    return result


def _format_number(value):
    if value is None or pd.isna(value):
        return "N/A"
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def build_tac2_text_report(
    client,
    patient_id: str,
    patient_name: str,
    input_data: dict = None,
) -> str:
    input_data = input_data or {}
    report_data = build_tac2_dataframes(client, patient_id, patient_name, input_data)
    results = report_data.get("results")
    if results is None or results.empty:
        return (
            "<div style=\"font-family: Arial, Helvetica, sans-serif; font-size: 11pt; line-height: 1.45; color: #111827;\">"
            "<p style=\"margin: 0 0 10px 0; text-align: justify;\">"
            "<strong>TAC (Teste de atenção por cancelamento)</strong> é um instrumento utilizado para avaliar a atenção sustentada, a atenção seletiva, a velocidade de processamento visual e o controle atencional."
            "</p>"
            "<table style=\"width: 100%; border-collapse: collapse; font-size: 10.5pt;\">"
            "<thead>"
            "<tr>"
            "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: left;\">Indicador</th>"
            "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: center; width: 18%;\">Pontuação</th>"
            "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: center; width: 22%;\">Classificação</th>"
            "</tr>"
            "</thead>"
            "<tbody>"
            "<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Primeira parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td></tr>"
            "<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Segunda parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td></tr>"
            "<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Terceira parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">N/A</td></tr>"
            "<tr><td style=\"border: 1px solid #000000; padding: 8px; font-weight: 700;\">Geral</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center; font-weight: 700;\">N/A</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center; font-weight: 700;\">N/A</td></tr>"
            "</tbody>"
            "</table>"
            "</div>"
        )

    row = results.fillna("").to_dict(orient="records")[0]
    description = (
        "<p style=\"margin: 0 0 10px 0; text-align: justify;\">"
        "<strong>TAC (Teste de atenção por cancelamento)</strong> é um instrumento utilizado "
        "para avaliar a atenção sustentada, a atenção seletiva, a velocidade "
        "de processamento visual e o controle atencional."
        "</p>"
    )
    table = (
        "<table style=\"width: 100%; border-collapse: collapse; font-size: 10.5pt;\">"
        "<thead>"
        "<tr>"
        "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: left;\">Indicador</th>"
        "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: center; width: 18%;\">Pontuação</th>"
        "<th style=\"border: 1px solid #000000; background: #e2e8f0; padding: 8px; text-align: center; width: 22%;\">Classificação</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Primeira parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{_format_number(row.get('pontuacao_primeira_parte_mapeada'))}</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{row.get('pontuacao_primeira_parte_categoria') or 'N/A'}</td></tr>"
        f"<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Segunda parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{_format_number(row.get('pontuacao_segunda_parte_mapeada'))}</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{row.get('pontuacao_segunda_parte_categoria') or 'N/A'}</td></tr>"
        f"<tr><td style=\"border: 1px solid #000000; padding: 8px;\">Terceira parte</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{_format_number(row.get('pontuacao_terceira_parte_mapeada'))}</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center;\">{row.get('pontuacao_terceira_parte_categoria') or 'N/A'}</td></tr>"
        f"<tr><td style=\"border: 1px solid #000000; padding: 8px; font-weight: 700; background: #f8fafc;\">Geral</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center; font-weight: 700; background: #f8fafc;\">{_format_number(row.get('score_total_mapeado'))}</td><td style=\"border: 1px solid #000000; padding: 8px; text-align: center; font-weight: 700; background: #f8fafc;\">{row.get('score_total_categoria') or 'N/A'}</td></tr>"
        "</tbody>"
        "</table>"
    )
    return (
        "<div style=\"font-family: Arial, Helvetica, sans-serif; color: #111827;\">"
        f"{description}"
        f"{table}"
        "</div>\n"
    )
