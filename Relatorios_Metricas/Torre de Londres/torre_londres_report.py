from pathlib import Path
from datetime import date, datetime
import html

import numpy as np
import pandas as pd


def _escape_html(value):
    if value is None:
        return ""
    return html.escape(str(value)).replace("\n", "<br />")


def classify_score_metric(value) -> str:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if numeric_value < 70:
        return "Muito Baixa"
    elif numeric_value <= 84:
        return "Baixa"
    elif numeric_value <= 114:
        return "M\u00e9dia"
    elif numeric_value <= 129:
        return "Alta"
    return "Muito Alta"


def _read_csv_numeric(path: Path) -> pd.DataFrame:
    # Use utf-8 encoding explicitly
    df = pd.read_csv(path, encoding="utf-8")
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(axis=0, how="all").reset_index(drop=True)


def _compute_age_from_client(client, patient_id: str):
    if client is None:
        try:
            from app.auth import supabase
            client = supabase
        except ImportError:
            pass
    if client is None:
        return None
    try:
        resp = client.table("patients").select("birth_date").eq("id", patient_id).limit(1).execute()
        raw = getattr(resp, "data", []) or []
        if not raw:
            return None
        birth_value = raw[0].get("birth_date")
        if not birth_value:
            return None
        try:
            birth_date = datetime.fromisoformat(str(birth_value)).date()
        except Exception:
            try:
                birth_date = datetime.strptime(str(birth_value), "%d/%m/%Y").date()
            except Exception:
                return None
        today = date.today()
        return int(today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day)))
    except Exception:
        return None


def _map_score(df: pd.DataFrame, raw_score, age):
    if df is None or raw_score is None:
        return np.nan
    try:
        raw_score = int(raw_score)
    except Exception:
        return np.nan

    if age is not None:
        if age >= 15:
            age_col = "Jovens_Adultos"
        elif age <= 11:
            age_col = "11_anos"
        elif age == 12:
            age_col = "12_anos"
        elif age == 13:
            age_col = "13_anos"
        else:
            age_col = "14_anos"
    else:
        age_col = "Jovens_Adultos"

    if age_col not in df.columns:
        cols = [c for c in df.columns if c != df.columns[0]]
        if cols:
            age_col = cols[-1]
        else:
            return np.nan

    first_col = df.columns[0]
    matched = df[df[first_col] == raw_score]
    if matched.empty:
        return np.nan
    value = matched.iloc[0].get(age_col)
    return float(value) if pd.notna(value) else np.nan


def _html_table(results_row):
    return (
        "<table class=\"metric-table\" style=\"width:100%; border-collapse:collapse; font-family: Arial, Helvetica, sans-serif; font-size: 10pt; break-inside: avoid; page-break-inside: avoid;\">"
        "<thead><tr>"
        "<th style=\"border: 0.5px solid #000000; background:#e2e8f0; padding:8px; text-align:left; break-inside: avoid; page-break-inside: avoid;\">Indicador</th>"
        "<th style=\"border: 0.5px solid #000000; background:#e2e8f0; padding:8px; text-align:center; width:18%; break-inside: avoid; page-break-inside: avoid;\">Pontuação</th>"
        "<th style=\"border: 0.5px solid #000000; background:#e2e8f0; padding:8px; text-align:center; width:22%; break-inside: avoid; page-break-inside: avoid;\">Classifica\u00e7\u00e3o</th>"
        "</tr></thead><tbody>"
        f"<tr style=\"break-inside: avoid; page-break-inside: avoid;\"><td style=\"border: 0.5px solid #000000; padding:8px; break-inside: avoid; page-break-inside: avoid;\">Pontua\u00e7\u00e3o Total</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['total_score']}</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['total_categoria']}</td></tr>"
        f"<tr style=\"break-inside: avoid; page-break-inside: avoid;\"><td style=\"border: 0.5px solid #000000; padding:8px; break-inside: avoid; page-break-inside: avoid;\">Pontua\u00e7\u00e3o nos itens de 4 movimentos</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['m4_score']}</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['m4_categoria']}</td></tr>"
        f"<tr style=\"break-inside: avoid; page-break-inside: avoid;\"><td style=\"border: 0.5px solid #000000; padding:8px; break-inside: avoid; page-break-inside: avoid;\">Pontua\u00e7\u00e3o nos itens de 5 movimentos</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['m5_score']}</td><td style=\"border: 0.5px solid #000000; padding:8px; text-align:center; break-inside: avoid; page-break-inside: avoid;\">{results_row['m5_categoria']}</td></tr>"
        "</tbody></table>"
    )


def build_torre_londres_report(client, patient_id, patient_name, input_data, report_dir: Path = None):
    if report_dir is None:
        report_dir = Path(__file__).resolve().parent
    paths = {
        "total": report_dir / "Teste_TorreDeLondres_ScoreTotal.csv",
        "m4": report_dir / "Teste_TorreDeLondres_4Movimentos.csv",
        "m5": report_dir / "Teste_TorreDeLondres_5Movimentos.csv",
    }
    dfs = {k: _read_csv_numeric(v) for k, v in paths.items()}

    age = _compute_age_from_client(client, patient_id)

    tot = input_data.get("pontuacao_total")
    m4 = input_data.get("pontuacao_4_movimentos")
    m5 = input_data.get("pontuacao_5_movimentos")

    score_total = _map_score(dfs["total"], tot, age)
    score_m4 = _map_score(dfs["m4"], m4, age)
    score_m5 = _map_score(dfs["m5"], m5, age)

    row_data = {
        'total_score': f"{score_total:.0f}" if pd.notna(score_total) else "N/A",
        'total_categoria': classify_score_metric(score_total) if pd.notna(score_total) else "N/A",
        'm4_score': f"{score_m4:.0f}" if pd.notna(score_m4) else "N/A",
        'm4_categoria': classify_score_metric(score_m4) if pd.notna(score_m4) else "N/A",
        'm5_score': f"{score_m5:.0f}" if pd.notna(score_m5) else "N/A",
        'm5_categoria': classify_score_metric(score_m5) if pd.notna(score_m5) else "N/A",
    }

    html_text = (
        "<div style=\"font-family: Arial, Helvetica, sans-serif; color:#111827; font-size:10.5pt; break-inside: avoid; page-break-inside: avoid;\">"
        "<p style=\"margin:0 0 10px 0; text-align:justify; font-size:10.75pt; line-height:1.55; break-inside: avoid; page-break-inside: avoid;\">"
        "<strong>ToL (Teste da Torre de Londres)</strong> \u00e9 um instrumento neuropsicol\u00f3gico que avalia fun\u00e7\u00f5es executivas, "
        "principalmente planejamento e resolu\u00e7\u00e3o de problemas, atrav\u00e9s de tarefas como mover pe\u00e7as entre pinos seguindo regras espec\u00edficas."
        "</p>"
        f"<div style=\"break-inside: avoid; page-break-inside: avoid;\">{_html_table(row_data)}</div>"
        "</div>\n"
    )
    return html_text
