import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATAFRAME_ROOT = BASE_DIR / "dataframes"
REPORT_ROOT = BASE_DIR / "Relatorios_Metricas"

REPORT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "TAC 2": {
        "folder_name": "TAC 2",
        "dataframes": [
            "patient_summary",
            "assessment_items",
        ],
        "csv_files": [
            "patient_summary.csv",
            "assessment_items.csv",
        ],
        "csv_columns": {
            "patient_summary.csv": ["patient_id", "patient_name", "report_type", "status"],
            "assessment_items.csv": ["item_id", "question", "value"],
        },
        "input_fields": [
            {
                "name": "tac2_input",
                "label": "Entrada TAC 2",
                "type": "text",
                "required": False,
                "placeholder": "Digite um valor para TAC 2",
            }
        ],
    }
}


def ensure_report_folders() -> None:
    DATAFRAME_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    for report_name, definition in REPORT_DEFINITIONS.items():
        report_folder = REPORT_ROOT / definition["folder_name"]
        report_folder.mkdir(parents=True, exist_ok=True)

        for csv_name in definition.get("csv_files", []):
            csv_path = report_folder / csv_name
            if not csv_path.exists():
                columns = definition.get("csv_columns", {}).get(csv_name, [])
                pd.DataFrame(columns=columns).to_csv(csv_path, index=False)

        report_py = report_folder / "report.py"
        if not report_py.exists():
            report_py.write_text(
                """import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_FILES = {
    'patient_summary': BASE_DIR / 'patient_summary.csv',
    'assessment_items': BASE_DIR / 'assessment_items.csv',
}


def load_tables():
    tables = {}
    for name, path in CSV_FILES.items():
        if path.exists():
            tables[name] = pd.read_csv(path)
        else:
            tables[name] = pd.DataFrame()
    return tables


def get_input_schema():
    return [
        {
            'name': 'tac2_input',
            'label': 'Entrada TAC 2',
            'type': 'text',
            'required': False,
            'placeholder': 'Digite um valor para TAC 2',
        }
    ]


def build_report(patient_id: str, patient_name: str, input_data: dict | None = None):
    tables = load_tables()
    return {
        'patient_id': patient_id,
        'patient_name': patient_name,
        'input_data': input_data or {},
        'tables': tables,
    }
""",
                encoding="utf-8",
            )

        report_folder_pkl = DATAFRAME_ROOT / definition["folder_name"]
        report_folder_pkl.mkdir(parents=True, exist_ok=True)
        for dataframe_name in definition.get("dataframes", []):
            path = report_folder_pkl / f"{dataframe_name}.pkl"
            if not path.exists():
                pd.DataFrame().to_pickle(path)


def get_report_folders() -> List[str]:
    if not REPORT_ROOT.exists():
        return []
    return [folder.name for folder in REPORT_ROOT.iterdir() if folder.is_dir()]


def get_report_dataframe_names(report_name: str) -> List[str]:
    definition = REPORT_DEFINITIONS.get(report_name)
    return definition["dataframes"] if definition else []


def get_report_input_fields(report_name: str) -> List[Dict[str, Any]]:
    report_module = load_report_module(report_name)
    if not report_module or not hasattr(report_module, 'get_input_schema'):
        return []
    return report_module.get_input_schema()


def load_report_module(report_name: str):
    report_folder = REPORT_ROOT / report_name
    report_path = report_folder / 'report.py'
    if not report_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"report_{report_name}", report_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_report_dataframe_file(report_name: str, dataframe_name: str) -> Path:
    definition = REPORT_DEFINITIONS.get(report_name)
    if not definition:
        raise FileNotFoundError(f"Relatório não encontrado: {report_name}")
    folder = DATAFRAME_ROOT / definition["folder_name"]
    return folder / f"{dataframe_name}.pkl"


def save_dataframe(report_name: str, dataframe_name: str, df: pd.DataFrame) -> None:
    path = get_report_dataframe_file(report_name, dataframe_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)


def load_dataframe(report_name: str, dataframe_name: str) -> pd.DataFrame:
    path = get_report_dataframe_file(report_name, dataframe_name)
    if not path.exists():
        raise FileNotFoundError(f"DataFrame não encontrado: {report_name}/{dataframe_name}")
    return pd.read_pickle(path)
