"""TAC2 report helpers: load tables, compute mapped scores, build results.

This module loads CSVs only from the TAC2 report directory and keeps the
computed result in memory. It does not generate CSV files for the report
output.
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import date, datetime


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
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all")
    return df.reset_index(drop=True)


def _compute_age_from_client(client, patient_id: str) -> int:
    if client is None:
        return None
    resp = (
        client.table("patients")
        .select("birth_date")
        .eq("id", patient_id)
        .limit(1)
        .execute()
    )
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
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    return int(age)


def _map_score(df: pd.DataFrame, raw_score, age) -> float:
    if df is None or raw_score is None:
        return np.nan
    try:
        raw_score = int(raw_score)
    except Exception:
        return np.nan

    if age is not None and age >= 15:
        age_col = "Jovens_Adultos"
    elif age is not None:
        age_col = f"{age}_anos"
    else:
        age_col = None

    if age_col is None or age_col not in df.columns:
        age_columns = [c for c in df.columns if c != "Score_bruto"]
        if not age_columns:
            return np.nan
        age_col = age_columns[-1]

    if "Score_bruto" in df.columns:
        score_col = "Score_bruto"
    else:
        score_col = next((c for c in df.columns if "score" in c.lower()), None)

    if score_col is None:
        return np.nan

    matched = df[df[score_col] == raw_score]
    if not matched.empty:
        val = matched.iloc[0].get(age_col)
        return float(val) if pd.notna(val) else np.nan

    try:
        diffs = (df[score_col] - raw_score).abs()
        idx = diffs.idxmin()
        val = df.loc[idx, age_col]
        return float(val) if pd.notna(val) else np.nan
    except Exception:
        return np.nan


def build_tac2_report(
    client,
    patient_id: str,
    patient_name: str,
    input_data: dict,
    report_dir: Path = None,
) -> dict:
    if report_dir is None:
        report_dir = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "Relatorios_Metricas"
            / "TAC 2"
        )
    else:
        report_dir = Path(report_dir)

    paths = {
        "primeira_parte": (
            report_dir / "TAC2_PrimeiraParte_Pontuação(5 a 14).csv"
        ),
        "segunda_parte": (
            report_dir / "TAC2_SegundaParte_Pontuação(5 a 14).csv"
        ),
        "terceira_parte": (
            report_dir / "TAC2_TerceiraParte_Pontuação(5 a 14).csv"
        ),
        "score_geral": (
            report_dir / "TAC_ScoreGeral_Pontuação(5 a 14).csv"
        ),
    }

    dfs = {
        key: _read_csv_numeric(path) if path.exists() else pd.DataFrame()
        for key, path in paths.items()
    }
    idade = _compute_age_from_client(client, patient_id)

    p1 = input_data.get("pontuacao_primeira_parte")
    p2 = input_data.get("pontuacao_segunda_parte")
    p3 = input_data.get("pontuacao_terceira_parte")

    mapped1 = _map_score(dfs.get("primeira_parte"), p1, idade)
    mapped2 = _map_score(dfs.get("segunda_parte"), p2, idade)
    mapped3 = _map_score(dfs.get("terceira_parte"), p3, idade)

    score_total_input = None
    if p1 is not None and p2 is not None and p3 is not None:
        score_total_input = p1 + p2 + p3
    mapped_total = (
        _map_score(dfs.get("score_geral"), score_total_input, idade)
        if score_total_input is not None
        else np.nan
    )

    results = pd.DataFrame([
        {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "idade_paciente_tac2": idade if idade is not None else np.nan,
            "pontuacao_primeira_parte_input": p1 if p1 is not None else np.nan,
            "pontuacao_primeira_parte_mapeada": mapped1,
            "pontuacao_primeira_parte_categoria": classify_score_metric(mapped1),
            "score_total_input": (
                score_total_input if score_total_input is not None else np.nan
            ),
            "score_total_mapeado": mapped_total,
            "score_total_categoria": classify_score_metric(mapped_total),
            "pontuacao_segunda_parte_input": p2 if p2 is not None else np.nan,
            "pontuacao_segunda_parte_mapeada": mapped2,
            "pontuacao_segunda_parte_categoria": classify_score_metric(mapped2),
            "pontuacao_terceira_parte_input": p3 if p3 is not None else np.nan,
            "pontuacao_terceira_parte_mapeada": mapped3,
            "pontuacao_terceira_parte_categoria": classify_score_metric(mapped3),
        }
    ])

    for col in results.columns:
        if col in ("patient_name", "patient_id"):
            continue
        if col.endswith("_categoria"):
            continue
        results[col] = pd.to_numeric(results[col], errors="coerce")

    return {
        "score_geral": dfs.get("score_geral"),
        "primeira_parte": dfs.get("primeira_parte"),
        "segunda_parte": dfs.get("segunda_parte"),
        "terceira_parte": dfs.get("terceira_parte"),
        "results": results,
    }
