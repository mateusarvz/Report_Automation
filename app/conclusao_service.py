"""
conclusao_service.py

Responsável por gerar a CONCLUSÃO em texto do relatório PDF, usando a API do Gemini.

Toda a lógica referente à conclusão vive aqui:
  1. Idade do paciente selecionado;
  2. Resultados de todos os relatórios selecionados;
  3. O arquivo "IA-directions.txt" de cada relatório, pareado corretamente com os
     resultados do relatório correspondente (ex.: TAC 2 usa Relatorios_Metricas/TAC 2/IA-directions.txt);
  4. Descrição do paciente escrita pelo usuário;
  5. Variável "user_ia_direction_conclusion" (direção dada pelo usuário para a conclusão).

Retorna o texto da conclusão formatado como HTML (parágrafos <p>), pronto para ser
inserido ao final do relatório PDF.
"""

import os
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
    user_ia_direction_conclusion: str,
) -> str:
    """
    Monta o prompt final enviado ao Gemini, priorizando:
      1. Instrução de papel (profissional de neuropsicologia);
      2. Idade e descrição do paciente;
      3. Resultados e diretrizes de cada relatório selecionado;
      4. Direção do usuário para a conclusão.
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
        "Escreva um texto fluido e dinâmico que integre os resultados de todos os testes aplicados, "
        "a idade e a descrição do paciente e a direção fornecida pelo profissional.\n"
        "Varie o tamanho das frases, alterne períodos curtos e longos, e use conectivos e transições "
        "naturais para dar ritmo à leitura. Evite começar parágrafos sempre da mesma forma e evite "
        "repetir as mesmas estruturas; o texto deve ser coeso, envolvente e fluido, porém sempre com "
        "tom formal e profissional.\n"
        "Use de 10 a 20 palavras.\n"

        "NÃO FAÇA O SEGUINTE:\n"
        "Não detalhe exaustivamente os números de cada teste.\n"
        "Não cite a idade do paciente de forma explícita.\n"
        "Não repita o conteúdo dos relatórios; apenas sintetize-os de forma coesa.\n\n"

        "DADOS DE ENTRADA DO PACIENTE:\n"
        f"Idade do Paciente: {age_info}\n"
        "Descrição do Paciente (escrita pelo profissional):\n"
        f"{patient_description or 'Nenhuma descrição inserida.'}\n"
        "Trate essa descrição como se fosse pensada por você e integre-a à conclusão.\n\n"

        "RESULTADOS E DIRETRIZES DOS TESTES SELECIONADOS:\n"
        f"{directions_text}\n"

        + direction_block

        + "\nProduza apenas a síntese, em texto corrido e em parágrafos de texto puro, "
          "sem títulos, sem listas, sem símbolos de markdown e sem textos introdutórios "
          "como 'A síntese é:' ou 'Aqui está a síntese'."
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


async def generate_conclusion(
    birth_date: str = None,
    report_results: list = None,
    patient_description: str = "",
    user_ia_direction_conclusion: str = "",
) -> str:
    """
    Gera a conclusão por escrito do relatório PDF usando a API do Gemini.

    Args:
        birth_date: data de nascimento do paciente (para calcular a idade).
        report_results: lista de dicionários com os resultados de cada relatório selecionado.
            Formato esperado: [{"report_name": str, "results_html": str}, ...]
        patient_description: descrição do paciente escrita pelo usuário.
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

    # 4) Descrição do paciente + 5) Direção do usuário são passadas à montagem do prompt
    prompt = _build_prompt(age_info, report_blocks, patient_description, user_ia_direction_conclusion)

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
            return _format_html_text(generated_text)
        except Exception as e:
            return f"<p><em>Erro ao gerar a conclusão via Gemini: {str(e)}</em></p>"