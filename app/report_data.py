import importlib.util
from pathlib import Path

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
