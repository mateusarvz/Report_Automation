import pandas as pd
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
