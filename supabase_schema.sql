-- =====================================================
-- SCHEMA MINIMAL PARA O SITE
-- Login via Supabase Auth + profile + pacientes
-- =====================================================

create extension if not exists pgcrypto;

-- =====================================================
-- PROFILES
-- =====================================================

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    full_name text,
    photo_url text,
    profession text,
    phone text check (phone is null or phone ~ '^\(\d{2}\)\s?\d{4,5}-\d{4}$'),
    gender text check (gender is null or gender in ('Masculino', 'Feminino', 'Outro')),
    role text not null default 'user' check (role in ('admin', 'psychologist', 'user')),
    status text not null default 'active' check (status in ('active', 'inactive', 'pending', 'suspended')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_login timestamptz
);

alter table public.profiles enable row level security;

alter table public.profiles
    add column if not exists profession text;

alter table public.profiles
    add column if not exists phone text;

alter table public.profiles
    add column if not exists gender text;

alter table public.profiles
    add column if not exists role text default 'user';

alter table public.profiles
    add column if not exists status text default 'active';

alter table public.profiles
    drop constraint if exists profiles_phone_format_check;

alter table public.profiles
    add constraint profiles_phone_format_check
    check (phone is null or phone ~ '^\(\d{2}\)\s?\d{4,5}-\d{4}$');

alter table public.profiles
    drop constraint if exists profiles_gender_check;

alter table public.profiles
    add constraint profiles_gender_check
    check (gender is null or gender in ('Masculino', 'Feminino', 'Outro'));

alter table public.profiles
    drop constraint if exists profiles_role_check;

alter table public.profiles
    add constraint profiles_role_check
    check (role in ('admin', 'psychologist', 'user'));

alter table public.profiles
    drop constraint if exists profiles_status_check;

alter table public.profiles
    add constraint profiles_status_check
    check (status in ('active', 'inactive', 'pending', 'suspended'));

drop policy if exists "profiles_select_own" on public.profiles;
drop policy if exists "profiles_insert_own" on public.profiles;
drop policy if exists "profiles_update_own" on public.profiles;

create policy "profiles_select_own"
on public.profiles
for select
using (auth.uid() = id);

create policy "profiles_insert_own"
on public.profiles
for insert
with check (auth.uid() = id);

create policy "profiles_update_own"
on public.profiles
for update
using (auth.uid() = id)
with check (auth.uid() = id);

-- =====================================================
-- PATIENTS
-- =====================================================

create table if not exists public.patients (
    id uuid primary key default gen_random_uuid(),
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    full_name text not null,
    birth_date date,
    gender text,
    phone text,
    email text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.patients enable row level security;

drop policy if exists "patients_select_own" on public.patients;
drop policy if exists "patients_insert_own" on public.patients;
drop policy if exists "patients_update_own" on public.patients;
drop policy if exists "patients_delete_own" on public.patients;

create policy "patients_select_own"
on public.patients
for select
using (psychologist_id = auth.uid());

create policy "patients_insert_own"
on public.patients
for insert
with check (psychologist_id = auth.uid());

create policy "patients_update_own"
on public.patients
for update
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

create policy "patients_delete_own"
on public.patients
for delete
using (psychologist_id = auth.uid());

-- =====================================================
-- ÍNDICES
-- =====================================================

create index if not exists idx_patients_psychologist on public.patients(psychologist_id);

-- =====================================================
-- TRIGGER PARA CRIAR PROFILE AUTOMATICAMENTE
-- =====================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (
        id,
        email,
        full_name,
        photo_url,
        profession,
        phone,
        role,
        status,
        created_at,
        updated_at
    )
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', ''),
        new.raw_user_meta_data->>'avatar_url',
        new.raw_user_meta_data->>'profession',
        new.raw_user_meta_data->>'phone',
        coalesce(new.raw_user_meta_data->>'role', 'user'),
        coalesce(new.raw_user_meta_data->>'status', 'active'),
        now(),
        now()
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = coalesce(excluded.full_name, public.profiles.full_name),
        photo_url = coalesce(excluded.photo_url, public.profiles.photo_url),
        profession = coalesce(excluded.profession, public.profiles.profession),
        phone = coalesce(excluded.phone, public.profiles.phone),
        role = coalesce(excluded.role, public.profiles.role),
        status = coalesce(excluded.status, public.profiles.status),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();

-- =====================================================
-- FUNÇÃO PARA REGISTRAR O ÚLTIMO LOGIN NO PROFILE
-- =====================================================

create or replace function public.update_profile_last_login(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.profiles
    set last_login = now(),
        updated_at = now()
    where id = p_user_id;
end;
$$;
