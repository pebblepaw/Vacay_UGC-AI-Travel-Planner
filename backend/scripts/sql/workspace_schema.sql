-- VacayClaw workspace runtime schema

create table if not exists workspaces (
  id text primary key,
  title text not null,
  trip_id text not null,
  source text not null default 'web',
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists conversation_events (
  id bigint generated always as identity primary key,
  workspace_id text not null,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_conversation_events_workspace_created
  on conversation_events(workspace_id, created_at);

create table if not exists workspace_runtime_state (
  workspace_id text primary key,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists memory_entries (
  id bigint generated always as identity primary key,
  workspace_id text not null,
  user_id text null,
  memory_key text not null,
  memory_value jsonb not null,
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id, memory_key)
);

create table if not exists workspace_snapshots (
  workspace_id text primary key,
  snapshot jsonb not null,
  updated_at timestamptz not null default now()
);
