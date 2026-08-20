import os
from pathlib import Path
import httpx

from datetime import date, datetime

REPORT_ROOT = Path(__file__).resolve().parents[1] / 'Relatorios_Metricas'

async def generate_interpretation(report_name: str, observations: str, table_html: str, birth_date: str = None) -> str:
    """
    Generates a professional neuropedagogy interpretation for the report using Gemini API.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "<p><em>Interpretação automática indisponível: GEMINI_API_KEY não configurada.</em></p>"

    # Load IA-directions.txt
    directions_path = REPORT_ROOT / report_name / "IA-directions.txt"
    directions_content = ""
    if directions_path.exists():
        try:
            directions_content = directions_path.read_text(encoding="utf-8")
        except Exception:
            directions_content = ""

    # Calculate patient age
    age_info = "Não informada"
    if birth_date:
        try:
            birth_dt = datetime.fromisoformat(str(birth_date)).date()
            today = date.today()
            age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
            age_info = f"{age} anos"
        except Exception:
            pass

    # Compile the prompt keeping in mind the priority requested by the user:
    # 1. System/Role Instruction (Neuropedagogy professional, 100-200 words, interpretation of test results)
    # 2. User observations (Instruções para a IA)
    # 3. Test results table
    # 4. Manual / directions (IA-directions.txt)
    prompt = (
        "INSTRUÇÃO PRINCIPAL (CRÍTICA):\n"
        "Atue como um profissional de neuropedagogia. Ultilize linguagem formal, profissional para a área de psicologia."
        f"{"Gere de 5 e 20 palavras" if observations else "Gere entre 15 e 50 palavras"} "
        "Evite dar diagnosticos."
        "Atue sempre como se você estivesse escrevendo a sua interpretação dos resultados.\n\n"

        "NÃO FAÇA O SEGUINTE:\n"
        "Voce não deve detalhar as informações dos resultados dos testes."
        "Voce não deve fazer sugestões nem recomendações"
        "Voce nao deve citar a idade do paciente\n"

        "DADOS DE ENTRADA DO PACIENTE E DO TESTE:\n"
        f"Idade do Paciente: {age_info}\n"
        f"Opinião do Profissional da área sobre o paciente (apenas deste relatório):\n{observations or 'Nenhuma observação inserida.'} Trate essa opnião como se ela fosse pensada por voce."
        "Qualquer informação da Opinião do Profissional da área sobre o paciente Deve ser tratada como se fosse sua. Portando voce deve falar dela como se fossem as suas proprias conclusões."
        f"Resultados:\n{table_html}\n\n"

        "DIRETRIZES E MANUAL DE REFERÊNCIA DO TESTE:\n"
        f"{directions_content or 'Caso nao hajam diretrizes, Voce deve falar NAO HA DIRETRIZES claramente ao final do seu prompt'}\n"
    )

    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    json_payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=json_payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            generated_text = data['candidates'][0]['content']['parts'][0]['text']
            
            # Format generated markdown/text to HTML paragraphs cleanly
            paragraphs = generated_text.strip().split("\n\n")
            html_content = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
            return html_content
        except Exception as e:
            return f"<p><em>Erro ao gerar interpretação via Gemini: {str(e)}</em></p>"
