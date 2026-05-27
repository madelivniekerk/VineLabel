-- Run this in the Supabase SQL Editor (supabase.com → your project → SQL Editor)

create table if not exists products (
  id             text primary key,
  name           text,
  vintage        text,
  variety        text,
  region         text,
  producer_name  text,
  collection     text,
  status         text default 'draft',
  data           jsonb not null,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);

create table if not exists settings (
  id          text primary key default 'default',
  data        jsonb not null,
  updated_at  timestamptz default now()
);

-- Indexes for common reporting queries
create index if not exists idx_products_status     on products(status);
create index if not exists idx_products_producer   on products(producer_name);
create index if not exists idx_products_collection on products(collection);
create index if not exists idx_products_updated    on products(updated_at desc);
