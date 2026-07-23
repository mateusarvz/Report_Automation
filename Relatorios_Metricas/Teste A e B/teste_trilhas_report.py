from pathlib import Path
from datetime import date, datetime

import numpy as np
import pandas as pd


def classify_score_metric(value) -> str:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return ""
    if numeric_value < 70:
        return "Muito Baixa"
    if numeric_value < 85:
        return "Baixa"
    if numeric_value < 115:
        return "Média"
    if numeric_value < 130:
        return "Alta"
    return "Muito Alta"


def _read_csv_numeric(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={df.columns[0]: "Escore bruto"})
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(axis=0, how="all").reset_index(drop=True)


def _compute_age_from_client(client, patient_id: str):
    if client is None:
        return None
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


def _map_score(df: pd.DataFrame, raw_score, age):
    if df is None or raw_score is None:
        return np.nan
    try:
        raw_score = int(raw_score)
    except Exception:
        return np.nan
    if age is not None and age >= 15:
        age_col = "Jovens Adultos"
    elif age is not None and str(age) in df.columns:
        age_col = str(age)
    else:
        age_col = next((c for c in df.columns if c != "Escore bruto"), None)
    if not age_col or age_col not in df.columns:
        return np.nan
    matched = df[df["Escore bruto"] == raw_score]
    if matched.empty:
        return np.nan
    value = matched.iloc[0].get(age_col)
    return float(value) if pd.notna(value) else np.nan


def _html_table(results_row):
    return (
        "<table style=\"width:100%; border-collapse:collapse; font-family: Arial, Helvetica, sans-serif; font-size: 10.5pt;\">"
        "<thead><tr>"
        "<th style=\"border:1px solid #000000; background:#e2e8f0; padding:8px; text-align:left;\">Indicador</th>"
        "<th style=\"border:1px solid #000000; background:#e2e8f0; padding:8px; text-align:center; width:18%;\">Score</th>"
        "<th style=\"border:1px solid #000000; background:#e2e8f0; padding:8px; text-align:center; width:22%;\">Classificação</th>"
        "</tr></thead><tbody>"
        f"<tr><td style=\"border:1px solid #000000; padding:8px;\">Parte A</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_a_score']}</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_a_categoria']}</td></tr>"
        f"<tr><td style=\"border:1px solid #000000; padding:8px;\">Parte B</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_b_score']}</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_b_categoria']}</td></tr>"
        f"<tr><td style=\"border:1px solid #000000; padding:8px;\">Parte B-A</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_ba_score']}</td><td style=\"border:1px solid #000000; padding:8px; text-align:center;\">{results_row['parte_ba_categoria']}</td></tr>"
        "</tbody></table>"
    )


def build_teste_trilhas_report(client, patient_id, patient_name, input_data, report_dir: Path = None):
    if report_dir is None:
        report_dir = Path(__file__).resolve().parent
    paths = {
        "parte_a": report_dir / "Teste_deTrilhas_Correção_Parte_A.csv",
        "parte_b": report_dir / "Teste_deTrilhas_Correção_Parte_B.csv",
        "parte_ba": report_dir / "Teste_deTrilhas_Correção_Parte_B-A.csv",
    }
    dfs = {k: _read_csv_numeric(v) for k, v in paths.items()}
    age = _compute_age_from_client(client, patient_id)
    a = input_data.get("resultado_parte_a")
    b = input_data.get("resultado_parte_b")
    ba = input_data.get("resultado_parte_ba")
    score_a = _map_score(dfs["parte_a"], a, age)
    score_b = _map_score(dfs["parte_b"], b, age)
    score_ba = _map_score(dfs["parte_ba"], ba, age)

    results = pd.DataFrame([{
        "patient_id": patient_id,
        "patient_name": patient_name,
        "idade_paciente_trilhas": age if age is not None else np.nan,
        "parte_a_input": a if a is not None else np.nan,
        "parte_a_score": score_a,
        "parte_a_categoria": classify_score_metric(score_a),
        "parte_b_input": b if b is not None else np.nan,
        "parte_b_score": score_b,
        "parte_b_categoria": classify_score_metric(score_b),
        "parte_ba_input": ba if ba is not None else np.nan,
        "parte_ba_score": score_ba,
        "parte_ba_categoria": classify_score_metric(score_ba),
    }])

    age_html = (
        f"<p style=\"margin:0 0 12px 0;\"><strong>Idade do paciente:</strong> {age} anos</p>"
        if age is not None
        else ""
    )
    html = (
        "<div style=\"font-family: Arial, Helvetica, sans-serif; color:#111827;\">"
        "<p style=\"margin:0 0 10px 0; text-align:justify;\">"
        "<strong>Teste de Trilhas</strong> é um instrumento indicado para avaliar atenção e funções executivas. "
        "Enquanto a Parte A mede atenção concentrada e velocidade ao ligar números em ordem, a Parte B mede flexibilidade cognitiva e atenção alternada ao intercalar números e letras."
        "</p>"
        f"{age_html}"
        f"{_html_table({'parte_a_score': f'{score_a:.0f}' if pd.notna(score_a) else 'N/A', 'parte_a_categoria': classify_score_metric(score_a) or 'N/A', 'parte_b_score': f'{score_b:.0f}' if pd.notna(score_b) else 'N/A', 'parte_b_categoria': classify_score_metric(score_b) or 'N/A', 'parte_ba_score': f'{score_ba:.0f}' if pd.notna(score_ba) else 'N/A', 'parte_ba_categoria': classify_score_metric(score_ba) or 'N/A'})}"
        "</div>\n"
    )
    return html
