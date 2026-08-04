import io
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fpdf import FPDF
from fpdf import html as fpdf_html
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import login_user, logout_user, get_user_from_session, templates, get_authenticated_client, build_display_name
from app.config import get_settings
from app.report_store import ensure_report_folders, save_dataframe, get_report_input_fields, get_report_folders
from app.report_data import build_tac2_dataframes, build_tac2_text_report

BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS = get_settings()

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


def _patient_age_from_birth_date(birth_value):
    from datetime import date, datetime
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
SPA_INDEX = FRONTEND_DIST / "index.html"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_report_folders()
    yield


app = FastAPI(title="Report Psicologia API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SETTINGS["secret_key"],
    same_site="lax",
    https_only=False,
    max_age=None,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Serve o frontend React buildado (bundles hasheados do Vite)
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


def serve_spa():
    """Devolve o index.html do SPA React (login/rotas tratadas no cliente)."""
    return FileResponse(str(SPA_INDEX))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = SETTINGS["supabase_url"]
SUPABASE_KEY = SETTINGS["supabase_key"]


@app.get("/health")
def health_check():
    return {"status": "ok", "supabase": "configured" if SUPABASE_URL and SUPABASE_KEY else "missing"}


@app.get("/")
async def root(request: Request):
    return serve_spa()


@app.get("/login")
async def login_page(request: Request):
    return serve_spa()


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        await login_user(email, password, request)
    except Exception as exc:
        detail = str(exc)
        if 'Invalid login credentials' in detail:
            detail = 'E-mail ou senha inválidos.'
        return templates.TemplateResponse(request, "login.html", {"request": request, "error": detail})

    return RedirectResponse(url="/generate-report", status_code=303)


@app.post("/api/auth/login")
async def api_login(request: Request):
    payload = await request.json()
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email e senha são obrigatórios")
    try:
        await login_user(email, password, request)
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        detail = str(exc)
        if 'Invalid login credentials' in detail:
            detail = 'E-mail ou senha inválidos.'
        raise HTTPException(status_code=401, detail=detail)
    return {"ok": True, "user": request.session.get("user")}


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    await logout_user(request)
    return {"ok": True}


@app.get("/api/auth/user")
def api_user(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return {"user": user}


@app.get("/logout")
async def logout(request: Request):
    await logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/account")
async def account(request: Request):
    return serve_spa()


@app.post("/account/update-profile")
async def update_profile(request: Request, full_name: str = Form(""), profession: str = Form(""), gender: str = Form("")):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    full_name = (full_name or "").strip()
    profession = (profession or "").strip()
    gender = (gender or "").strip()

    allowed_genders = {"Masculino", "Feminino", "Outro"}
    if gender and gender not in allowed_genders:
        raise HTTPException(status_code=400, detail="Gênero inválido")

    client = get_authenticated_client(request)
    response = client.table("profiles").update({
        "full_name": full_name or user.get("full_name") or None,
        "profession": profession or None,
        "gender": gender or None,
    }).eq("id", user["id"]).execute()

    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    request.session['user'] = {
        **user,
        'full_name': full_name or user.get('full_name'),
        'profession': profession or user.get('profession'),
        'gender': gender or user.get('gender'),
    }

    return RedirectResponse(url="/account?updated=1", status_code=303)


@app.patch("/api/account")
async def api_update_account(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    payload = await request.json()
    full_name = (payload.get("full_name") or "").strip()
    profession = (payload.get("profession") or "").strip()
    gender = (payload.get("gender") or "").strip()

    allowed_genders = {"Masculino", "Feminino", "Outro"}
    if gender and gender not in allowed_genders:
        raise HTTPException(status_code=400, detail="Gênero inválido")

    client = get_authenticated_client(request)
    response = client.table("profiles").update({
        "full_name": full_name or user.get("full_name") or None,
        "profession": profession or None,
        "gender": gender or None,
    }).eq("id", user["id"]).execute()

    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    updated_user = {
        **user,
        'full_name': full_name or user.get('full_name'),
        'profession': profession or user.get('profession'),
        'gender': gender or user.get('gender'),
    }
    request.session['user'] = updated_user
    return {"ok": True, "user": updated_user}


@app.get("/generate-report")
async def generate_report(request: Request):
    return serve_spa()


@app.get("/api/patients")
async def api_patients(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    client = get_authenticated_client(request)
    # select additional fields so frontend can display gender and contact and pre-fill edit form
    response = client.table("patients").select("id, full_name, birth_date, gender, phone, email").eq("psychologist_id", user["id"]).order("created_at", desc=True).execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    raw_patients = getattr(response, "data", []) or []
    from datetime import date, datetime
    today = date.today()
    patients = []
    for p in raw_patients:
        age = ""
        birth_value = p.get("birth_date")
        birth_date_display = ""
        if birth_value:
            try:
                birth_date = datetime.fromisoformat(str(birth_value)).date()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                birth_date_display = birth_date.strftime("%d/%m/%Y")
            except Exception:
                age = ""
                birth_date_display = str(birth_value)

        patients.append({
            "id": p.get("id"),
            "full_name": p.get("full_name") or "Paciente",
            "age": age,
            "birth_date": birth_date_display,
            "gender": p.get("gender") or None,
            "phone": p.get("phone") or None,
            "email": p.get("email") or None,
        })
    return patients


@app.get("/api/report-types")
async def api_report_types(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return get_report_folders()


@app.get("/api/report-fields")
async def api_report_fields(request: Request, report_name: str = ""):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    if not report_name or report_name not in get_report_folders():
        raise HTTPException(status_code=400, detail="Relatório inválido")
    return get_report_input_fields(report_name)


@app.post("/api/reports")
async def create_report(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    payload = await request.json()
    patient_id = payload.get("patient_id")
    report_name = payload.get("report_name")
    input_data = payload.get("input_data") or {}
    if not patient_id or not report_name:
        raise HTTPException(status_code=400, detail="patient_id e report_name são obrigatórios")
    report_folders = get_report_folders()
    if report_name not in report_folders:
        raise HTTPException(status_code=400, detail="Relatório inválido")

    client = get_authenticated_client(request)
    patient_resp = client.table("patients").select("id, full_name, birth_date").eq("psychologist_id", user["id"]).eq("id", patient_id).limit(1).execute()
    if getattr(patient_resp, "error", None):
        raise HTTPException(status_code=500, detail=str(patient_resp.error))
    raw_data = getattr(patient_resp, "data", []) or []
    if not raw_data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    patient = raw_data[0]

    report_text = ""
    if report_name == "TAC 2":
        report_text = build_tac2_text_report(
            client,
            patient["id"],
            patient.get("full_name") or "Paciente",
            input_data,
        )
    else:
        report_module = None
        try:
            from app.report_store import load_report_module
            report_module = load_report_module(report_name)
        except Exception:
            report_module = None

        if not report_module or not hasattr(report_module, 'build_report'):
            raise HTTPException(status_code=400, detail="Relatório não suportado")

        # Report modules are called without the DB client, so they cannot
        # resolve the patient's age themselves. Inject the patient's age so the
        # report can select the correct age column in its score tables.
        report_input = dict(input_data or {})
        patient_age = _patient_age_from_birth_date(patient.get("birth_date"))
        if patient_age is not None:
            report_input["_patient_age"] = patient_age

        report_output = report_module.build_report(patient["id"], patient.get("full_name") or "Paciente", report_input)
        if isinstance(report_output, str):
            report_text = report_output

    if report_text:
        from app.gemini_service import generate_interpretation

        table_match = re.search(r"<table.*?>.*?</table>", report_text, re.DOTALL | re.IGNORECASE)
        table_html = table_match.group(0) if table_match else ""
        observations = input_data.get("observacoes_sobre_o_teste", "")
        interpretation = await generate_interpretation(report_name, observations, table_html, patient.get("birth_date"))
        ai_html = (
            '<div style="margin-top:20px;">'
            f'<div style="border:1px solid #cbd5e1; background:#f8fafc; padding:10px; border-radius:6px; font-size:9pt; line-height:1.5;">{interpretation}</div>'
            '</div>'
        )
        if report_text.endswith("</div>\n"):
            report_text = report_text[:-7] + ai_html + "</div>\n"
        elif report_text.endswith("</div>"):
            report_text = report_text[:-6] + ai_html + "</div>"
        else:
            report_text += ai_html

        return HTMLResponse(report_text)

    return {"ok": True, "report_name": report_name, "patient_id": patient_id}


class PDF(FPDF, fpdf_html.HTMLMixin):
    pass


async def build_report_html(client, patient, report_name: str, input_data: dict) -> str:
    report_text = ""
    if report_name == "TAC 2":
        report_text = build_tac2_text_report(
            client,
            patient["id"],
            patient.get("full_name") or "Paciente",
            input_data,
        )
    else:
        report_module = None
        try:
            from app.report_store import load_report_module
            report_module = load_report_module(report_name)
        except Exception:
            report_module = None

        if not report_module or not hasattr(report_module, 'build_report'):
            raise HTTPException(status_code=400, detail="Relatório não suportado")

        # Report modules are called without the DB client, so they cannot
        # resolve the patient's age themselves. Inject the patient's age so the
        # report can select the correct age column in its score tables.
        report_input = dict(input_data or {})
        patient_age = _patient_age_from_birth_date(patient.get("birth_date"))
        if patient_age is not None:
            report_input["_patient_age"] = patient_age

        report_output = report_module.build_report(patient["id"], patient.get("full_name") or "Paciente", report_input)
        if isinstance(report_output, str):
            report_text = report_output

    if not report_text:
        raise HTTPException(status_code=400, detail="Relatório vazio")

    from app.gemini_service import generate_interpretation
    table_match = re.search(r"<table.*?>.*?</table>", report_text, re.DOTALL | re.IGNORECASE)
    table_html = table_match.group(0) if table_match else ""
    observations = input_data.get("observacoes_sobre_o_teste", "")
    interpretation = await generate_interpretation(report_name, observations, table_html, patient.get("birth_date"))
    ai_html = (
        '<div style="margin-top:20px;">'
        f'<div style="border:1px solid #cbd5e1; background:#f8fafc; padding:10px; border-radius:6px; font-size:9pt; line-height:1.5;">{interpretation}</div>'
        '</div>'
    )
    if report_text.endswith("</div>\n"):
        report_text = report_text[:-7] + ai_html + "</div>\n"
    elif report_text.endswith("</div>"):
        report_text = report_text[:-6] + ai_html + "</div>"
    else:
        report_text += ai_html

    return report_text


def build_combined_pdf(report_sections: list[str]) -> bytes:
    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(left=15, top=15, right=15)
    pdf.set_auto_page_break(auto=True, margin=15)
    for section_html in report_sections:
        pdf.add_page()
        pdf.set_font('Arial', size=11)
        try:
            pdf.write_html(section_html)
        except Exception:
            text_only = re.sub(r'<[^>]+>', '', section_html)
            pdf.multi_cell(0, 8, text_only)
    output = pdf.output(dest='S')
    if isinstance(output, str):
        output = output.encode('latin-1', 'replace')
    return output


@app.post('/api/reports/pdf')
async def create_reports_pdf(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail='Não autenticado')

    payload = await request.json()
    patient_id = payload.get('patient_id')
    report_entries = payload.get('report_entries') or []
    if not patient_id or not isinstance(report_entries, list) or not report_entries:
        raise HTTPException(status_code=400, detail='patient_id e report_entries são obrigatórios')

    report_folders = get_report_folders()

    client = get_authenticated_client(request)
    patient_resp = client.table('patients').select('id, full_name, birth_date').eq('psychologist_id', user['id']).eq('id', patient_id).limit(1).execute()
    if getattr(patient_resp, 'error', None):
        raise HTTPException(status_code=500, detail=str(patient_resp.error))
    raw_data = getattr(patient_resp, 'data', []) or []
    if not raw_data:
        raise HTTPException(status_code=404, detail='Paciente não encontrado')
    patient = raw_data[0]

    report_sections = []
    for entry in report_entries:
        report_name = entry.get('report_name')
        input_data = entry.get('input_data') or {}
        if not report_name or report_name not in report_folders:
            raise HTTPException(status_code=400, detail=f"Relatório inválido: {report_name}")
        report_html = await build_report_html(client, patient, report_name, input_data)
        report_sections.append(report_html)

    pdf_content = build_combined_pdf(report_sections)
    return StreamingResponse(io.BytesIO(pdf_content), media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="relatorios_combinados.pdf"'})


@app.get("/register-patient")
async def register_patient(request: Request):
    return serve_spa()


@app.get("/patients")
async def patients(request: Request):
    return serve_spa()


@app.patch("/api/patients/{patient_id}")
async def update_patient(patient_id: str, request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    if not request.session.get("access_token"):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")

    payload = await request.json()
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Nome completo é obrigatório")

    def parse_birth_date(val):
        if not val:
            return None
        val = str(val).strip()
        from datetime import datetime
        try:
            if '/' in val:
                dt = datetime.strptime(val, '%d/%m/%Y')
            else:
                dt = datetime.strptime(val, '%Y-%m-%d')
            return dt.date().isoformat()
        except Exception:
            return None

    def normalize_phone(val):
        if not val:
            return None
        digits = ''.join(ch for ch in str(val) if ch.isdigit())
        if len(digits) < 10:
            return None
        aa = digits[:2]
        rest = digits[2:]
        if len(rest) == 8:
            return f"({aa}) {rest[:4]}-{rest[4:]}"
        return f"({aa}) {rest[:5]}-{rest[5:]}"

    birth_date = parse_birth_date(payload.get("birth_date") or None)
    if payload.get("birth_date") and birth_date is None:
        raise HTTPException(status_code=400, detail="Data de nascimento inválida. Use o formato dd/mm/aaaa.")
    if birth_date:
        from datetime import date, datetime
        bd = datetime.fromisoformat(birth_date).date()
        age = date.today().year - bd.year - ((date.today().month, date.today().day) < (bd.month, bd.day))
        if age < 0:
            raise HTTPException(status_code=400, detail="Data de nascimento não pode estar no futuro.")
        if age > 120:
            raise HTTPException(status_code=400, detail="A idade não pode ser maior que 120 anos.")
    phone = normalize_phone(payload.get("phone") or None)
    gender = payload.get("gender") or None
    allowed_genders = {"Masculino", "Feminino", "Outro"}
    if gender and gender not in allowed_genders:
        raise HTTPException(status_code=400, detail="Gênero inválido")

    data = {
        "full_name": full_name,
        "birth_date": birth_date,
        "gender": gender,
        "phone": phone,
        "email": payload.get("email") or None,
    }

    client = get_authenticated_client(request)
    response = client.table("patients").update(data).eq("id", patient_id).eq("psychologist_id", user["id"]).execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    updated_data = getattr(response, "data", []) or []
    if not updated_data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")

    return {"ok": True, "patient": updated_data[0]}


@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: str, request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    if not request.session.get("access_token"):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")

    client = get_authenticated_client(request)
    response = client.table("patients").delete().eq("id", patient_id).eq("psychologist_id", user["id"]).execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    deleted = getattr(response, "data", None) or []
    if not deleted:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")

    return {"ok": True, "deleted_id": patient_id}


@app.post("/api/patients")
async def create_patient(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    if not request.session.get("access_token"):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")

    payload = await request.json()
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Nome completo é obrigatório")
    # check duplicate patient name for this psychologist
    client = get_authenticated_client(request)
    try:
        dup_check = client.table("patients").select("id").eq("psychologist_id", user["id"]).eq("full_name", full_name).limit(1).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    existing = getattr(dup_check, "data", None) or []
    if isinstance(existing, list) and existing:
        raise HTTPException(status_code=400, detail="Já existe um paciente com esse nome registrado")

    # normalize and convert types according to supabase schema
    def parse_birth_date(val):
        if not val:
            return None
        val = str(val).strip()
        # accept dd/mm/yyyy or yyyy-mm-dd
        from datetime import datetime
        try:
            if '/' in val:
                dt = datetime.strptime(val, '%d/%m/%Y')
            else:
                dt = datetime.strptime(val, '%Y-%m-%d')
            return dt.date().isoformat()
        except Exception:
            return None

    def normalize_phone(val):
        if not val:
            return None
        digits = ''.join(ch for ch in str(val) if ch.isdigit())
        if len(digits) < 10:
            return None
        # area code first two digits
        aa = digits[:2]
        rest = digits[2:]
        if len(rest) == 8:
            # format (AA) 9999-9999
            return f"({aa}) {rest[:4]}-{rest[4:]}"
        else:
            # assume 9+4 => (AA) 99999-9999
            return f"({aa}) {rest[:5]}-{rest[5:]}"

    birth_date = parse_birth_date(payload.get("birth_date") or None)
    if payload.get("birth_date") and birth_date is None:
        raise HTTPException(status_code=400, detail="Data de nascimento inválida. Use o formato dd/mm/aaaa.")
    if birth_date:
        from datetime import date, datetime
        bd = datetime.fromisoformat(birth_date).date()
        age = date.today().year - bd.year - ((date.today().month, date.today().day) < (bd.month, bd.day))
        if age < 0:
            raise HTTPException(status_code=400, detail="Data de nascimento não pode estar no futuro.")
        if age > 120:
            raise HTTPException(status_code=400, detail="A idade não pode ser maior que 120 anos.")
    phone = normalize_phone(payload.get("phone") or None)
    gender = payload.get("gender") or None
    allowed_genders = {"Masculino", "Feminino", "Outro"}
    if gender and gender not in allowed_genders:
        raise HTTPException(status_code=400, detail="Gênero inválido")

    data = {
        "psychologist_id": user["id"],
        "full_name": full_name,
        "birth_date": birth_date,
        "gender": gender,
        "phone": phone,
        "email": payload.get("email") or None,
    }

    response = client.table("patients").insert(data).execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    return {"ok": True, "patient": getattr(response, "data", [None])[0]}


@app.get("/profiles")
def get_profiles(request: Request):
    client = get_authenticated_client(request)
    response = client.table("profiles").select("id, email, full_name").execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))
    return getattr(response, "data", [])


@app.get("/chat-gemini")
async def chat_gemini_page(request: Request):
    return serve_spa()


@app.post("/api/chat-gemini")
async def api_chat_gemini(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    payload = await request.json()
    contents = payload.get("contents")
    if not contents:
        raise HTTPException(status_code=400, detail="Histórico de mensagens é obrigatório")

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada no servidor")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json={"contents": contents}, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            return {"text": text}
        except httpx.HTTPStatusError as e:
            try:
                err_detail = e.response.json()
            except Exception:
                err_detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=f"Erro na API do Gemini: {err_detail}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/{path:path}")
async def spa_fallback(path: str):
    """Fallback do SPA: serve o index.html para rotas do cliente (React Router).

    /api, /static e /assets têm rotas próprias; se chegarem aqui, devolvem 404.
    """
    if path.startswith(("api/", "static/", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")
    return serve_spa()
