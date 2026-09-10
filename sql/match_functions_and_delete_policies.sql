-- Vector cosine similarity search for document_chunks
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

-- Vector cosine similarity search for memory_entries
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

-- Add DELETE RLS policies
create policy "company_isolation_delete" on companies
  for delete using (id = (auth.jwt() ->> 'company_id')::uuid);

do $$
declare
  t text;
  tables text[] := array[
    'departments','employees','goals','policies',
    'documents','document_chunks','memory_entries',
    'coo_conversations','coo_messages','decisions','approval_rules'
  ];
begin
  foreach t in array tables loop
    execute format(
      'create policy "company_isolation_delete" on %I for delete using (company_id = (auth.jwt() ->> ''company_id'')::uuid);',
      t
    );
  end loop;
end $$;
