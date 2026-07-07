import os
from urllib.parse import quote
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.middleware.sessions import SessionMiddleware
from httpx import HTTPStatusError
from db import get_supabase_user, load_user_profile, save_google_user

load_dotenv(".env")
load_dotenv(".env.local", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
LOCAL_REDIRECT_TO = os.getenv("LOCAL_REDIRECT_TO", "http://localhost:8000/auth/callback")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required in .env or .env.local")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Environment(loader=FileSystemLoader("templates"))

def get_current_user(request: Request):
    return request.session.get("user")


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/")
    redirect_to = quote(LOCAL_REDIRECT_TO, safe="")
    auth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_to}"
    template = templates.get_template("login.html")
    return HTMLResponse(template.render(request=request, supabase_auth_url=auth_url))


@app.get("/login-google")
async def login_google(request: Request):
    redirect_to = quote(LOCAL_REDIRECT_TO, safe="")
    return RedirectResponse(f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_to}")


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
    email = user_info.get("email")
    full_name = user_info.get("user_metadata", {}).get("full_name") or user_info.get("email")
    picture = user_info.get("user_metadata", {}).get("avatar_url")

    save_error = None
    try:
        save_google_user(email=email, full_name=full_name, picture=picture)
    except HTTPStatusError as exc:
        save_error = exc.response.text
    except Exception as exc:
        save_error = str(exc)

    request.session["user"] = {"email": email, "full_name": full_name, "picture": picture}

    if save_error:
        return JSONResponse({"ok": True, "warning": "profile_save_failed", "detail": save_error})

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

    profile = load_user_profile(user["email"])
    template = templates.get_template("home.html")
    return HTMLResponse(template.render(request=request, user=profile or user))
