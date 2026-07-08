import os
from urllib.parse import quote
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from httpx import HTTPStatusError
from db import (
    get_supabase_user,
    load_user_profile,
    save_google_user,
    get_user_patients,
    find_patient_by_name,
    create_patient,
)

load_dotenv(".env")
load_dotenv(".env.local", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
NEXT_PUBLIC_SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL")
LOCAL_REDIRECT_TO = os.getenv("LOCAL_REDIRECT_TO")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required in .env or .env.local")

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        proto = request.headers.get("x-forwarded-proto") or request.headers.get("x-forwarded-protocol")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if proto and host:
            request.scope["scheme"] = proto.split(",")[0]
            request.scope["server"] = (host.split(",")[0], request.scope.get("server", (None, None))[1])
        return await call_next(request)

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Environment(loader=FileSystemLoader("templates"))

def get_current_user(request: Request):
    return request.session.get("user")


def get_auth_redirect_url(request: Request):
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.headers.get("x-forwarded-protocol")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_proto and forwarded_host and "localhost" not in forwarded_host:
        return f"{forwarded_proto.split(',')[0]}://{forwarded_host.split(',')[0]}/auth/callback"

    if RENDER_EXTERNAL_URL:
        return RENDER_EXTERNAL_URL.rstrip("/") + "/auth/callback"

    if NEXT_PUBLIC_SITE_URL and "localhost" not in NEXT_PUBLIC_SITE_URL:
        return NEXT_PUBLIC_SITE_URL.rstrip("/") + "/auth/callback"

    if LOCAL_REDIRECT_TO and "localhost" not in LOCAL_REDIRECT_TO:
        return LOCAL_REDIRECT_TO.rstrip("/") + "/auth/callback"

    if LOCAL_REDIRECT_TO:
        return LOCAL_REDIRECT_TO.replace("localhost", "127.0.0.1")

    redirect_url = request.url_for("auth_callback")
    return str(redirect_url).replace("localhost", "127.0.0.1")


@app.get("/health")
async def health_check():
    return JSONResponse({"status": "ok"})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/")
    redirect_to = quote(get_auth_redirect_url(request), safe="")
    auth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_to}&response_type=token&prompt=select_account"
    template = templates.get_template("login.html")
    return HTMLResponse(template.render(request=request, supabase_auth_url=auth_url))


@app.get("/login-google")
async def login_google(request: Request):
    redirect_to = quote(get_auth_redirect_url(request), safe="")
    return RedirectResponse(f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_to}&response_type=token&prompt=select_account")


@app.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(request: Request):
    template = templates.get_template("auth_callback.html")
    return HTMLResponse(template.render())


@app.post("/auth/session")
async def auth_session(request: Request):
    data = await request.json()
    access_token = data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "access_token_required"}, status_code=400)

    user_info = get_supabase_user(access_token)
    user_meta = user_info.get("user") or {}
    user_id = user_info.get("id") or user_meta.get("id")
    email = user_info.get("email") or user_meta.get("email")
    full_name = (
        user_info.get("user_metadata", {}).get("full_name")
        or user_meta.get("user_metadata", {}).get("full_name")
        or email
    )
    picture = (
        user_info.get("user_metadata", {}).get("avatar_url")
        or user_meta.get("user_metadata", {}).get("avatar_url")
    )

    if not user_id or not email:
        return JSONResponse(
            {"error": "invalid_auth_user", "detail": "missing user id or email from Supabase"},
            status_code=400,
        )

    save_error = None
    try:
        save_google_user(
            user_id=user_id,
            email=email,
            full_name=full_name,
            picture=picture,
            access_token=access_token,
        )
    except HTTPStatusError as exc:
        save_error = exc.response.text
    except Exception as exc:
        save_error = str(exc)

    if save_error:
        return JSONResponse(
            {"error": "profile_save_failed", "detail": save_error},
            status_code=500,
        )

    request.session["user"] = {"id": user_id, "email": email, "full_name": full_name, "picture": picture}
    return JSONResponse({"ok": True})


@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/login")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    # No dashboard. Redirect logged user directly to generate-report.
    return RedirectResponse("/generate-report")


@app.get("/generate-report", response_class=HTMLResponse)
async def page_generate_report(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    template = templates.get_template("generate_report.html")
    return HTMLResponse(template.render(request=request, user=profile or user, current_path=request.url.path))


@app.get("/register-patient", response_class=HTMLResponse)
async def page_register_patient(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    template = templates.get_template("register_patient.html")
    return HTMLResponse(template.render(request=request, user=profile or user, current_path=request.url.path))


@app.get("/account", response_class=HTMLResponse)
async def page_account(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    template = templates.get_template("account.html")
    return HTMLResponse(template.render(request=request, user=profile or user, current_path=request.url.path))


@app.get("/patients", response_class=HTMLResponse)
async def page_patients(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    patients = []
    if profile:
        patients = get_user_patients(profile["id"])
    template = templates.get_template("patients.html")
    return HTMLResponse(template.render(request=request, user=profile or user, patients=patients, current_path=request.url.path))


@app.get("/api/patients")
async def api_get_patients(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")

    patients = get_user_patients(profile["id"])
    return JSONResponse(patients)


@app.post("/api/patients")
async def api_create_patient(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    profile = load_user_profile(user_id=user.get("id"), email=user.get("email"))
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")

    payload = await request.json()
    full_name = payload.get("full_name")
    if not full_name:
        return JSONResponse({"error": "full_name_required"}, status_code=400)

    patient_data = {
        "full_name": full_name,
        "birth_date": payload.get("birth_date"),
        "gender": payload.get("gender"),
        "phone": payload.get("phone"),
        "email": payload.get("email"),
    }

    existing_patient = find_patient_by_name(profile["id"], full_name)
    if existing_patient:
        return JSONResponse({"error": "patient_already_exists", "patient": existing_patient}, status_code=409)

    patient = create_patient(profile["id"], patient_data)
    return JSONResponse(patient)
