import importlib.util
from pathlib import Path

import pandas as pd

REPORT_ROOT = Path(__file__).resolve().parents[1] / 'Relatorios_Metricas'
DATAFRAMES_ROOT = Path(__file__).resolve().parents[1] / 'dataframes'


def ensure_report_folders():
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)


def get_report_folders():
    ensure_report_folders()
    return sorted([folder.name for folder in REPORT_ROOT.iterdir() if folder.is_dir()])


def report_folder_path(report_name: str) -> Path:
    return REPORT_ROOT / report_name


def load_report_module(report_name: str):
    report_dir = report_folder_path(report_name)
    report_file = report_dir / 'report.py'
    if not report_dir.exists() or not report_file.exists():
        raise FileNotFoundError(f"Relatório '{report_name}' não encontrado")

    module_name = f"report_module_{report_name.replace(' ', '_').replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, str(report_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Falha ao carregar o relatório {report_name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_report_input_fields(report_name: str):
    module = load_report_module(report_name)
    if hasattr(module, 'get_input_schema'):
        return module.get_input_schema()
    return []


def save_dataframe(report_name: str, dataframe_name: str, dataframe: pd.DataFrame):
    ensure_report_folders()
    destination = DATAFRAMES_ROOT / report_name
    destination.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(destination / f"{dataframe_name}.csv", index=False)
