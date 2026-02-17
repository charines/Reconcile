-- Tabelas do MVP de conciliacao

create table if not exists public.qualifications (
    id uuid primary key default gen_random_uuid(),
    keyword text not null,
    code text not null,
    description text not null,
    priority int not null,
    created_at timestamptz not null default now()
);

create table if not exists public.imports (
    id uuid primary key,
    company text,
    bank text,
    agency text,
    account text,
    input_file_path text,
    output_file_path text,
    row_count int,
    created_at timestamptz not null default now()
);

-- Opcional: criar buckets via SQL (pode ser feito no painel do Supabase)
-- insert into storage.buckets (id, name, public)
-- values ('inputs', 'inputs', false)
-- on conflict (id) do nothing;
--
-- insert into storage.buckets (id, name, public)
-- values ('outputs', 'outputs', false)
-- on conflict (id) do nothing;
