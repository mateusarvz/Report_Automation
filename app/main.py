import os
import json
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.auth import login_user, logout_user, get_user_from_session, templates, get_authenticated_client, build_display_name
from app.report_store import ensure_report_folders, save_dataframe, get_report_input_fields, get_report_folders
from app.report_data import build_tac2_dataframes

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))

app = FastAPI(title="Report Psicologia API", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key"),
    same_site="lax",
    https_only=False,
    max_age=None,
)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_event():
    ensure_report_folders()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase URL and key must be configured")


@app.get("/health")
def health_check():
    return {"status": "ok", "supabase": "connected"}


@app.get("/")
async def root(request: Request):
    user = get_user_from_session(request)
    if user:
        return RedirectResponse(url="/generate-report", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login")
async def login_page(request: Request):
    user = get_user_from_session(request)
    if user:
        return RedirectResponse(url="/generate-report", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


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


@app.get("/logout")
async def logout(request: Request):
    await logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/account")
async def account(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    updated = request.query_params.get("updated") == "1"
    return templates.TemplateResponse(request, "account.html", {"request": request, "user": user, "user_display_name": build_display_name(user), "current_path": request.url.path, "updated": updated})


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


@app.get("/generate-report")
async def generate_report(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "generate_report.html", {"request": request, "user": user, "user_display_name": build_display_name(user), "current_path": request.url.path})


@app.get("/api/patients")
async def api_patients(request: Request):
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    client = get_authenticated_client(request)
    response = client.table("patients").select("id, full_name").eq("psychologist_id", user["id"]).order("created_at", desc=True).execute()
    if getattr(response, "error", None):
        raise HTTPException(status_code=500, detail=str(response.error))

    raw_patients = getattr(response, "data", []) or []
    return [{"id": p.get("id"), "full_name": p.get("full_name") or "Paciente"} for p in raw_patients]


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
    patient_resp = client.table("patients").select("id, full_name").eq("psychologist_id", user["id"]).eq("id", patient_id).limit(1).execute()
    if getattr(patient_resp, "error", None):
        raise HTTPException(status_code=500, detail=str(patient_resp.error))
    raw_data = getattr(patient_resp, "data", []) or []
    if not raw_data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    patient = raw_data[0]

    if report_name == "TAC 2":
        report_dfs = build_tac2_dataframes(
            client,
            patient["id"],
            patient.get("full_name") or "Paciente",
            input_data,
        )
        results_df = report_dfs.get("results")
        report_results = None
        if results_df is not None and not results_df.empty:
            try:
                report_results = results_df.fillna("").to_dict(orient="records")[0]
            except Exception:
                report_results = None
        return {
            "ok": True,
            "report_name": report_name,
            "patient_id": patient_id,
            "report_results": report_results,
        }
    else:
        report_module = None
        try:
            from app.report_store import load_report_module
            report_module = load_report_module(report_name)
        except Exception:
            report_module = None

        if not report_module or not hasattr(report_module, 'build_report'):
            raise HTTPException(status_code=400, detail="Relatório não suportado")
        report_module.build_report(patient["id"], patient.get("full_name") or "Paciente", input_data)

    return {"ok": True, "report_name": report_name, "patient_id": patient_id}


@app.get("/register-patient")
async def register_patient(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    client = get_authenticated_client(request)
    response = client.table("patients").select("id, full_name, birth_date, phone, created_at").eq("psychologist_id", user["id"]).order("created_at", desc=True).execute()
    raw_patients = getattr(response, "data", []) or []

    from datetime import date, datetime
    today = date.today()
    patients = []
    for p in raw_patients:
        birth_value = p.get("birth_date")
        birth_date_display = ""
        age = ""
        if birth_value:
            try:
                birth_date = datetime.fromisoformat(str(birth_value)).date()
                birth_date_display = birth_date.strftime("%d/%m/%Y")
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            except Exception:
                birth_date_display = str(birth_value)
                age = ""

        patients.append({
            "id": p.get("id"),
            "full_name": p.get("full_name") or "",
            "age": age,
            "birth_date": birth_date_display,
            "phone": p.get("phone") or "",
        })

    return templates.TemplateResponse(request, "register_patient.html", {"request": request, "user": user, "user_display_name": build_display_name(user), "current_path": request.url.path, "patients": patients})


@app.get("/patients")
async def patients(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    client = get_authenticated_client(request)
    response = client.table("patients").select("id, full_name, birth_date, gender, email, phone, created_at").eq("psychologist_id", user["id"]).order("created_at", desc=True).execute()
    raw_patients = getattr(response, "data", []) or []

    from datetime import date, datetime
    today = date.today()
    patients = []
    for p in raw_patients:
        birth_value = p.get("birth_date")
        birth_date_display = ""
        age = ""
        if birth_value:
            try:
                birth_date = datetime.fromisoformat(str(birth_value)).date()
                birth_date_display = birth_date.strftime("%d/%m/%Y")
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            except Exception:
                birth_date_display = str(birth_value)
                age = ""

        patients.append({
            "id": p.get("id"),
            "full_name": p.get("full_name") or "",
            "birth_date": birth_date_display,
            "age": age,
            "gender": p.get("gender") or "",
            "email": p.get("email") or "",
            "phone": p.get("phone") or "",
        })

    return templates.TemplateResponse(request, "patients.html", {"request": request, "user": user, "user_display_name": build_display_name(user), "current_path": request.url.path, "patients": patients})


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
