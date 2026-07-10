import os
from typing import Optional
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = (
    os.getenv('SUPABASE_ANON_KEY')
    or os.getenv('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

templates = Jinja2Templates(directory='templates')


def build_display_name(user: Optional[dict]) -> str:
    if not user:
        return ''

    full_name = (user.get('full_name') or '').strip()
    if not full_name:
        return user.get('email') or ''

    profession = (user.get('profession') or '').strip()
    gender = (user.get('gender') or '').strip()

    if profession in {'Psicólogo(a)', 'Neuropsicólogo(a)'} and gender == 'Masculino':
        return f'Dr. {full_name}'
    if profession in {'Psicólogo(a)', 'Neuropsicólogo(a)'} and gender == 'Feminino':
        return f'Dra. {full_name}'

    return full_name


def get_user_from_session(request: Request) -> Optional[dict]:
    user = request.session.get('user') if hasattr(request, 'session') else None
    if not user or not user.get('id'):
        return user

    try:
        client = get_authenticated_client(request)
        response = client.table('profiles').select('id, email, full_name, profession, gender, phone, photo_url').eq('id', user['id']).execute()
        data = response.data or []
        profile = data[0] if isinstance(data, list) and data else None
        if profile:
            refreshed_user = {
                'id': user.get('id'),
                'email': profile.get('email') or user.get('email'),
                'full_name': profile.get('full_name') or user.get('full_name'),
                'profession': profile.get('profession') or user.get('profession'),
                'gender': profile.get('gender') or user.get('gender'),
                'phone': profile.get('phone') or user.get('phone'),
                'picture': profile.get('photo_url') or user.get('picture'),
            }
            request.session['user'] = refreshed_user
            return refreshed_user
    except Exception:
        pass

    return user


def _get_metadata_value(user_metadata, *keys):
    if not user_metadata:
        return ''
    if hasattr(user_metadata, 'get'):
        for key in keys:
            value = user_metadata.get(key)
            if value:
                return value
        return ''
    for key in keys:
        value = getattr(user_metadata, key, None)
        if value:
            return value
    return ''


def get_authenticated_client(request: Request) -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail='Supabase não configurado')

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    if hasattr(request, 'session'):
        access_token = request.session.get('access_token')
        refresh_token = request.session.get('refresh_token')
        if access_token:
            try:
                client.auth.set_session(access_token, refresh_token or '')
            except Exception:
                pass

    return client


async def login_user(email: str, password: str, request: Request):
    if not supabase:
        raise HTTPException(status_code=503, detail='Supabase não configurado')

    response = supabase.auth.sign_in_with_password({
        'email': email,
        'password': password,
    })

    if not getattr(response, 'user', None) or not getattr(response, 'session', None):
        raise HTTPException(status_code=401, detail='Credenciais inválidas')

    user_metadata = getattr(response.user, 'user_metadata', None) or {}
    profile_full_name = _get_metadata_value(user_metadata, 'full_name', 'name')
    profile_profession = _get_metadata_value(user_metadata, 'profession', '')
    profile_gender = _get_metadata_value(user_metadata, 'gender', '')
    profile_phone = _get_metadata_value(user_metadata, 'phone', '')
    profile_picture = _get_metadata_value(user_metadata, 'avatar_url', 'picture')

    try:
        client = get_authenticated_client(request)
        profile_response = client.table('profiles').select('id, email, full_name, profession, gender, phone, photo_url').eq('id', response.user.id).execute()
        profile_data = profile_response.data or []
        profile = profile_data[0] if isinstance(profile_data, list) and profile_data else None
        if profile:
            profile_full_name = profile.get('full_name') or profile_full_name
            profile_profession = profile.get('profession') or profile_profession
            profile_gender = profile.get('gender') or profile_gender
            profile_phone = profile.get('phone') or profile_phone
            profile_picture = profile.get('photo_url') or profile_picture
    except Exception:
        pass

    request.session['user'] = {
        'id': response.user.id,
        'email': response.user.email,
        'full_name': profile_full_name,
        'profession': profile_profession,
        'gender': profile_gender,
        'phone': profile_phone,
        'picture': profile_picture,
    }
    request.session['access_token'] = response.session.access_token
    request.session['refresh_token'] = response.session.refresh_token

    try:
        client = get_authenticated_client(request)
        upsert_data = {
            'id': response.user.id,
            'email': response.user.email,
            'photo_url': profile_picture,
        }
        # do not overwrite full_name on login; preserve existing value
        client.table('profiles').upsert(upsert_data, on_conflict='id').execute()
    except Exception:
        pass

    return response


async def logout_user(request: Request):
    if hasattr(request, 'session'):
        request.session.clear()


def build_login_redirect() -> RedirectResponse:
    return RedirectResponse(url='/account', status_code=303)
