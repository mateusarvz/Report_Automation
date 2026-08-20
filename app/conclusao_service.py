"""
conclusao_service.py

Responsável por gerar a CONCLUSÃO em texto do relatório PDF, usando a API do Gemini.

Toda a lógica referente à conclusão vive aqui:
  1. Idade do paciente selecionado;
  2. Resultados de todos os relatórios selecionados;
  3. O arquivo "IA-directions.txt" de cada relatório, pareado corretamente com os
     resultados do relatório correspondente (ex.: TAC 2 usa Relatorios_Metricas/TAC 2/IA-directions.txt);
  4. Descrição do paciente escrita pelo usuário;
  5. Histórico de saúde escrito pelo usuário;
  6. Vida escolar escrita pelo usuário;
  7. Comportamento durante a avaliação escrito pelo usuário;
  8. Variável "user_ia_direction_conclusion" (direção dada pelo usuário para a conclusão).

Retorna o texto da conclusão formatado como HTML (parágrafos <p>), pronto para ser
inserido ao final do relatório PDF.
"""

import os
import asyncio
from pathlib import Path
from datetime import date, datetime

import httpx

REPORT_ROOT = Path(__file__).resolve().parents[1] / 'Relatorios_Metricas'


def _compute_age_info(birth_date) -> str:
    """
    Calcula a idade do paciente a partir da data de nascimento.

    Aceita formatos ISO (aaaa-mm-dd) ou brasileiro (dd/mm/aaaa).
    """
    if not birth_date:
        return "Não informada"
    try:
        birth_dt = datetime.fromisoformat(str(birth_date)).date()
    except Exception:
        try:
            birth_dt = datetime.strptime(str(birth_date), "%d/%m/%Y").date()
        except Exception:
            return "Não informada"
    today = date.today()
    age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
    return f"{age} anos"


def _load_direction_report(report_name: str) -> str:
    """
    Lê o conteúdo do arquivo "IA-directions.txt" do relatório informado.

    O arquivo deve existir em: Relatorios_Metricas/<report_name>/IA-directions.txt
    Garante que cada relatório leia o seu próprio arquivo de diretrizes
    (ex.: "Relatorios_Metricas/TAC 2/IA-directions.txt").
    """
    directions_path = REPORT_ROOT / report_name / "IA-directions.txt"
    if not directions_path.exists():
        return ""
    try:
        return directions_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _build_prompt(
    age_info: str,
    report_blocks: list,
    patient_description: str,
    patient_health_history: str,
    patient_school_life: str,
    patient_evaluation_behavior: str,
    user_ia_direction_conclusion: str,
) -> str:
    """
    Monta o prompt final enviado ao Gemini, priorizando:
      1. Instrução de papel (profissional de neuropsicologia);
      2. Direção do usuário para a conclusão;
      3. Resultados e diretrizes de cada relatório selecionado;
      4. Contexto clínico do paciente como apoio, não como prioridade.
    """
    directions_text = ""

    # Concatena os blocos de cada relatório (resultados + manual do teste)
    for block in report_blocks:
        directions_text += block

    direction_block = user_ia_direction_conclusion.strip()
    if direction_block:
        direction_block = (
            "\nDIREÇÃO DO PROFISSIONAL PARA ESTA CONCLUSÃO:\n"
            "{direction}"
            "\nEsta direção deve ser tratada como se fossem as suas próprias conclusões "
            "sobre o caso, e deve guiar a redação final. Use-a como o eixo da conclusão.\n"
        ).format(direction=direction_block)
    else:
        direction_block = (
            "\nComo o profissional não forneceu uma direção específica, "
            "sintetize os resultados de forma equilibrada e objetiva.\n"
        )

    prompt = (
        "INSTRUÇÃO PRINCIPAL (CRÍTICA):\n"
        "Atue como um profissional de neuropsicologia.\n"
        "Você está escrevendo a seção 'Síntese dos resultados' de um relatório de avaliação neuropsicológica.\n"
        f"A prioridade máxima é a DIREÇÃO DO PROFISSIONAL escrita pelo usuario em: {direction_block}.\n"
        "Use essa direção como eixo principal da síntese e como guia da redação final.\n"
        "Use de 50 a 300 palavras.\n"

        "NÃO FAÇA O SEGUINTE:\n"
        "Não cite a idade do paciente de forma explícita.\n"
        "Não repita o conteúdo dos relatórios; apenas sintetize-os de forma coesa.\n\n"

        "CONTEXTO CLÍNICO DO PACIENTE, USAR COMO APOIO SECUNDÁRIO:\n"
        "Descrição do Paciente (escrita pelo profissional):\n"
        f"{patient_description or 'Nenhuma descrição inserida.'}\n"

        "Histórico de Saúde (escrito pelo profissional):\n"
        f"{patient_health_history or 'Nenhum histórico de saúde inserido.'}\n"

        "Vida Escolar (escrito pelo profissional):\n"
        f"{patient_school_life or 'Nenhuma informação escolar inserida.'}\n"

        "Comportamento Durante a Avaliação (escrito pelo profissional):\n"
        f"{patient_evaluation_behavior or 'Nenhum comportamento registrado.'}\n"

        "RESULTADOS E DIRETRIZES DOS TESTES SELECIONADOS:\n"
        f"{directions_text}\n"

        + "\nProduza apenas a síntese, em texto corrido e em parágrafos de texto puro, "
          "sem títulos, sem listas, sem símbolos de markdown e sem textos introdutórios. SEJA SEMPRE DIRETO E OBJETIVO"
    )
    return prompt


def _format_html_text(generated_text: str) -> str:
    """
    Formata o texto gerado pelo Gemini em parágrafos HTML limpos.

    O texto é envolvido num contêiner com espaçamento lateral (padding) para que
    a conclusão não fique colada nas bordas esquerda e direita da página do PDF.
    """
    paragraphs = generated_text.strip().split("\n\n")
    body = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
    if not body:
        return "<p></p>"
    return f'<div style="padding-left:14px; padding-right:14px;">{body}</div>'


def _build_fallback_conclusion_html(
    age_info: str,
    patient_description: str,
    patient_health_history: str,
    patient_school_life: str,
    patient_evaluation_behavior: str,
    user_ia_direction_conclusion: str,
) -> str:
    parts = [
        "Síntese temporariamente indisponível por instabilidade do serviço de IA.",
    ]
    if patient_description.strip():
        parts.append(f"Descrição clínica informada: {patient_description.strip()}")
    if patient_health_history.strip():
        parts.append(f"Histórico de saúde informado: {patient_health_history.strip()}")
    if patient_school_life.strip():
        parts.append(f"Vida escolar informada: {patient_school_life.strip()}")
    if patient_evaluation_behavior.strip():
        parts.append(f"Comportamento durante a avaliação: {patient_evaluation_behavior.strip()}")
    if user_ia_direction_conclusion.strip():
        parts.append(f"Direção profissional: {user_ia_direction_conclusion.strip()}")
    parts.append(f"Idade de referência: {age_info}")
    body = "".join(f"<p>{part}</p>" for part in parts)
    return f'<div style="padding-left:14px; padding-right:14px;">{body}</div>'


async def generate_conclusion(
    birth_date: str = None,
    report_results: list = None,
    patient_description: str = "",
    patient_health_history: str = "",
    patient_school_life: str = "",
    patient_evaluation_behavior: str = "",
    user_ia_direction_conclusion: str = "",
) -> str:
    """
    Gera a conclusão por escrito do relatório PDF usando a API do Gemini.

    Args:
        birth_date: data de nascimento do paciente (para calcular a idade).
        report_results: lista de dicionários com os resultados de cada relatório selecionado.
            Formato esperado: [{"report_name": str, "results_html": str}, ...]
        patient_description: descrição do paciente escrita pelo usuário.
        patient_health_history: histórico de saúde escrito pelo usuário.
        patient_school_life: vida escolar escrita pelo usuário.
        patient_evaluation_behavior: comportamento durante a avaliação escrito pelo usuário.
        user_ia_direction_conclusion: direção do usuário para a conclusão.

    Returns:
        String com a conclusão formatada em HTML (parágrafos <p>).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "<p><em>Conclusão automática indisponível: GEMINI_API_KEY não configurada.</em></p>"

    report_results = report_results or []

    # 1) Idade do paciente
    age_info = _compute_age_info(birth_date)

    # 2) + 3) Para cada relatório, parear os resultados com o seu próprio IA-directions.txt
    report_blocks = []
    for entry in report_results:
        report_name = entry.get("report_name") or "Relatório"
        results_html = entry.get("results_html") or ""
        # Extrai apenas o texto dos resultados, removendo as etiquetas HTML
        import re
        results_text = re.sub(r"<[^>]+>", " ", results_html)
        results_text = re.sub(r"\s+", " ", results_text).strip()

        directions = _load_direction_report(report_name)

        report_blocks.append(
            f"--- TESTE: {report_name} ---\n"
            f"Manual/Diretrizes do teste ({report_name}/IA-directions.txt):\n"
            f"{directions or '(sem diretrizes discectadas)'}\n"
            f"Resultados do teste:\n{results_text or '(sem resultados)'}\n"
            "----------------------------\n"
        )

    # 4) Descrição do paciente + 5) histórico + 6) comportamento + 7) direção do usuário
    # são passados à montagem do prompt
    prompt = _build_prompt(
        age_info,
        report_blocks,
        patient_description,
        patient_health_history,
        patient_school_life,
        patient_evaluation_behavior,
        user_ia_direction_conclusion,
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

    retry_statuses = {429, 500, 502, 503, 504}
    last_error = None

    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            try:
                response = await client.post(url, json=json_payload, timeout=60.0)
                if response.status_code in retry_statuses:
                    last_error = httpx.HTTPStatusError(
                        f"Server error '{response.status_code} {response.reason_phrase}' for url '{url}'",
                        request=response.request,
                        response=response,
                    )
                    raise last_error
                response.raise_for_status()
                data = response.json()
                generated_text = data['candidates'][0]['content']['parts'][0]['text']
                return _format_html_text(generated_text)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.5 * (2 ** attempt))
                    continue
                break
            except Exception as exc:
                last_error = exc
                break

    fallback_html = _build_fallback_conclusion_html(
        age_info,
        patient_description,
        patient_health_history,
        patient_school_life,
        patient_evaluation_behavior,
        user_ia_direction_conclusion,
    )
    error_text = str(last_error) if last_error else "erro desconhecido"
    return (
        f'{fallback_html}'
        f'<p><em>Conclusão automática provisória. Gemini indisponível no momento: {error_text}</em></p>'
    )
