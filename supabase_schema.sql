-- =====================================================
-- EXTENSÕES
-- =====================================================

create extension if not exists pgcrypto;

-- =====================================================
-- PROFILES (PSICÓLOGOS)
-- =====================================================

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    full_name text,
    photo_url text,
    phone text,
    crp text,
    status text default 'ACTIVE',
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    last_login timestamptz
);

alter table public.profiles enable row level security;

drop policy if exists "Profiles Select Own" on public.profiles;
drop policy if exists "Profiles Insert Own" on public.profiles;
drop policy if exists "Profiles Update Own" on public.profiles;

create policy "Profiles Select Own"
on public.profiles
for select
using (auth.uid() = id);

create policy "Profiles Insert Own"
on public.profiles
for insert
with check (auth.uid() = id);

create policy "Profiles Update Own"
on public.profiles
for update
using (auth.uid() = id);

-- =====================================================
-- PLANS
-- =====================================================

create table if not exists public.plans (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    monthly_price numeric(10,2) not null,
    reports_limit integer,
    active boolean default true,
    created_at timestamptz default now()
);

alter table public.plans enable row level security;

drop policy if exists "Plans Read Public" on public.plans;

create policy "Plans Read Public"
on public.plans
for select
using (true);

-- =====================================================
-- SUBSCRIPTIONS
-- =====================================================

create table if not exists public.subscriptions (
    id uuid primary key default gen_random_uuid(),
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    plan_id uuid references public.plans(id),
    status text default 'ACTIVE',
    gateway text,
    gateway_subscription_id text,
    started_at timestamptz,
    expires_at timestamptz,
    created_at timestamptz default now()
);

alter table public.subscriptions enable row level security;

drop policy if exists "Subscriptions Own" on public.subscriptions;

create policy "Subscriptions Own"
on public.subscriptions
for all
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

-- =====================================================
-- PAYMENTS
-- =====================================================

create table if not exists public.payments (
    id uuid primary key default gen_random_uuid(),
    subscription_id uuid references public.subscriptions(id) on delete cascade,
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    amount numeric(10,2),
    payment_method text,
    gateway_payment_id text,
    status text,
    paid_at timestamptz,
    created_at timestamptz default now()
);

alter table public.payments enable row level security;

drop policy if exists "Payments Own" on public.payments;

create policy "Payments Own"
on public.payments
for all
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

-- =====================================================
-- PATIENTS
-- =====================================================

create table if not exists public.patients (
    id uuid primary key default gen_random_uuid(),
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    full_name text not null,
    birth_date date,
    gender text,
    cpf text,
    phone text,
    email text,
    notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

alter table public.patients enable row level security;

drop policy if exists "Patients Own" on public.patients;

create policy "Patients Own"
on public.patients
for all
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

-- =====================================================
-- TESTS
-- =====================================================

create table if not exists public.tests (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references public.patients(id) on delete cascade,
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    test_type text not null,
    status text default 'IN_PROGRESS',
    created_at timestamptz default now(),
    finished_at timestamptz
);

alter table public.tests enable row level security;

drop policy if exists "Tests Own" on public.tests;

create policy "Tests Own"
on public.tests
for all
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

-- =====================================================
-- TEST ANSWERS
-- =====================================================

create table if not exists public.test_answers (
    id uuid primary key default gen_random_uuid(),
    test_id uuid not null references public.tests(id) on delete cascade,
    question text,
    answer text,
    score numeric,
    created_at timestamptz default now()
);

alter table public.test_answers enable row level security;

drop policy if exists "Answers Own" on public.test_answers;

create policy "Answers Own"
on public.test_answers
for all
using (
    exists (
        select 1
        from public.tests t
        where t.id = test_answers.test_id
        and t.psychologist_id = auth.uid()
    )
)
with check (
    exists (
        select 1
        from public.tests t
        where t.id = test_answers.test_id
        and t.psychologist_id = auth.uid()
    )
);

-- =====================================================
-- REPORTS
-- =====================================================

create table if not exists public.reports (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references public.patients(id) on delete cascade,
    psychologist_id uuid not null references public.profiles(id) on delete cascade,
    test_id uuid references public.tests(id),
    title text,
    summary text,
    pdf_path text,
    status text default 'GENERATED',
    created_at timestamptz default now()
);

alter table public.reports enable row level security;

drop policy if exists "Reports Own" on public.reports;

create policy "Reports Own"
on public.reports
for all
using (psychologist_id = auth.uid())
with check (psychologist_id = auth.uid());

-- =====================================================
-- AUDIT LOGS
-- =====================================================

create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references public.profiles(id) on delete cascade,
    action text,
    entity text,
    entity_id uuid,
    created_at timestamptz default now()
);

alter table public.audit_logs enable row level security;

drop policy if exists "Audit Own" on public.audit_logs;

create policy "Audit Own"
on public.audit_logs
for select
using (user_id = auth.uid());

-- =====================================================
-- ÍNDICES
-- =====================================================

create index if not exists idx_patients_psychologist on public.patients(psychologist_id);
create index if not exists idx_tests_patient on public.tests(patient_id);
create index if not exists idx_tests_psychologist on public.tests(psychologist_id);
create index if not exists idx_reports_patient on public.reports(patient_id);
create index if not exists idx_reports_psychologist on public.reports(psychologist_id);
create index if not exists idx_answers_test on public.test_answers(test_id);
create index if not exists idx_subscriptions_psychologist on public.subscriptions(psychologist_id);
create index if not exists idx_payments_psychologist on public.payments(psychologist_id);

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
        last_login,
        updated_at
    )
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', ''),
        new.raw_user_meta_data->>'avatar_url',
        now(),
        now()
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = excluded.full_name,
        photo_url = excluded.photo_url,
        last_login = now(),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert
on auth.users
for each row
execute function public.handle_new_user();