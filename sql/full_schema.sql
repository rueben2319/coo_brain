-- Full PostgreSQL Schema for COO Brain (Supabase)

create extension if not exists "pgcrypto";
create extension if not exists "vector";

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Companies table
create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  industry text,
  mission text,
  vision text,
  fiscal_year_start date,
  timezone text not null default 'Africa/Blantyre',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace trigger trg_companies_updated_at
  before update on companies
  for each row execute function set_updated_at();

-- Departments table
create table if not exists departments (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  name text not null,
  description text,
  parent_department_id uuid references departments(id) on delete set null,
  head_employee_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_departments_company on departments(company_id);

create or replace trigger trg_departments_updated_at
  before update on departments
  for each row execute function set_updated_at();

-- Employee roles and table
do $$ begin
  create type employee_role as enum ('owner', 'executive', 'manager', 'staff', 'ai_agent');
exception
  when duplicate_object then null;
end $$;

create table if not exists employees (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  department_id uuid references departments(id) on delete set null,
  auth_user_id uuid references auth.users(id) on delete set null,
  full_name text not null,
  email text,
  role employee_role not null default 'staff',
  title text,
  reports_to_id uuid references employees(id) on delete set null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table departments
  drop constraint if exists fk_departments_head,
  add constraint fk_departments_head foreign key (head_employee_id) references employees(id) on delete set null;

create index if not exists idx_employees_company on employees(company_id);
create index if not exists idx_employees_department on employees(department_id);

create or replace trigger trg_employees_updated_at
  before update on employees
  for each row execute function set_updated_at();

-- Goal status and table
do $$ begin
  create type goal_status as enum ('not_started', 'on_track', 'at_risk', 'off_track', 'achieved', 'abandoned');
exception
  when duplicate_object then null;
end $$;

create table if not exists goals (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  department_id uuid references departments(id) on delete set null,
  parent_goal_id uuid references goals(id) on delete cascade,
  title text not null,
  description text,
  metric_name text,
  target_value numeric,
  current_value numeric,
  unit text,
  status goal_status not null default 'not_started',
  starts_at date,
  due_at date,
  created_by uuid references employees(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_goals_company on goals(company_id);
create index if not exists idx_goals_department on goals(department_id);
create index if not exists idx_goals_status on goals(status);

create or replace trigger trg_goals_updated_at
  before update on goals
  for each row execute function set_updated_at();

-- Policy type and table
do $$ begin
  create type policy_type as enum ('spending_limit', 'approval_rule', 'sop', 'hr_policy', 'compliance', 'other');
exception
  when duplicate_object then null;
end $$;

create table if not exists policies (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  department_id uuid references departments(id) on delete set null,
  policy_type policy_type not null,
  title text not null,
  description text,
  rule jsonb not null default '{}',
  is_active boolean not null default true,
  effective_from date not null default current_date,
  effective_to date,
  created_by uuid references employees(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_policies_company on policies(company_id);
create index if not exists idx_policies_type on policies(policy_type);

create or replace trigger trg_policies_updated_at
  before update on policies
  for each row execute function set_updated_at();

-- Documents and Document Chunks
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  department_id uuid references departments(id) on delete set null,
  title text not null,
  doc_type text,
  source_url text,
  raw_text text,
  uploaded_by uuid references employees(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  company_id uuid not null references companies(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding vector(768),
  created_at timestamptz not null default now()
);

create index if not exists idx_documents_company on documents(company_id);
create index if not exists idx_document_chunks_document on document_chunks(document_id);
create index if not exists idx_document_chunks_company on document_chunks(company_id);

create or replace trigger trg_documents_updated_at
  before update on documents
  for each row execute function set_updated_at();

-- Memory type and table
do $$ begin
  create type memory_type as enum ('experience', 'decision', 'lesson', 'observation');
exception
  when duplicate_object then null;
end $$;

create table if not exists memory_entries (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  memory_type memory_type not null,
  summary text not null,
  detail text,
  related_goal_id uuid references goals(id) on delete set null,
  related_department_id uuid references departments(id) on delete set null,
  embedding vector(768),
  importance smallint not null default 3 check (importance between 1 and 5),
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_memory_company on memory_entries(company_id);
create index if not exists idx_memory_type on memory_entries(memory_type);

-- COO Conversations and Messages
create table if not exists coo_conversations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  employee_id uuid references employees(id) on delete set null,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

do $$ begin
  create type message_role as enum ('user', 'assistant', 'system');
exception
  when duplicate_object then null;
end $$;

create table if not exists coo_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references coo_conversations(id) on delete cascade,
  company_id uuid not null references companies(id) on delete cascade,
  role message_role not null,
  content text not null,
  cited_document_ids uuid[] default '{}',
  cited_memory_ids uuid[] default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_coo_messages_conversation on coo_messages(conversation_id);
create index if not exists idx_coo_messages_company on coo_messages(company_id);

create or replace trigger trg_coo_conversations_updated_at
  before update on coo_conversations
  for each row execute function set_updated_at();

-- Vector similarity search functions
create or replace function match_document_chunks (
  query_embedding vector(768),
  match_threshold float default 0.0,
  match_count int default 5,
  p_company_id uuid default null
)
returns table (
  id uuid,
  document_id uuid,
  chunk_index int,
  content text,
  document_title text,
  similarity float
)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  select
    dc.id,
    dc.document_id,
    dc.chunk_index,
    dc.content,
    d.title as document_title,
    (1 - (dc.embedding <=> query_embedding))::float as similarity
  from document_chunks dc
  join documents d on dc.document_id = d.id
  where (p_company_id is null or dc.company_id = p_company_id)
    and dc.embedding is not null
    and (1 - (dc.embedding <=> query_embedding)) > match_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
end;
$$;

create or replace function match_memory_entries (
  query_embedding vector(768),
  match_threshold float default 0.0,
  match_count int default 5,
  p_company_id uuid default null
)
returns table (
  id uuid,
  memory_type memory_type,
  summary text,
  detail text,
  importance smallint,
  occurred_at timestamptz,
  similarity float
)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  select
    m.id,
    m.memory_type,
    m.summary,
    m.detail,
    m.importance,
    m.occurred_at,
    (1 - (m.embedding <=> query_embedding))::float as similarity
  from memory_entries m
  where (p_company_id is null or m.company_id = p_company_id)
    and m.embedding is not null
    and (1 - (m.embedding <=> query_embedding)) > match_threshold
  order by m.embedding <=> query_embedding
  limit match_count;
end;
$$;
