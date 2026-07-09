import pandas as pd


def build_tac2_dataframes(patient_id: str, patient_name: str) -> dict:
    patient_summary = pd.DataFrame([
        {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "report_type": "TAC 2",
            "status": "pending",
        }
    ])

    assessment_items = pd.DataFrame([
        {"item_id": 1, "question": "Perfil cognitivo", "value": None},
        {"item_id": 2, "question": "Memória verbal", "value": None},
        {"item_id": 3, "question": "Atenção", "value": None},
    ])

    return {
        "patient_summary": patient_summary,
        "assessment_items": assessment_items,
    }
