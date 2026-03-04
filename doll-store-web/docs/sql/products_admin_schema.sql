-- Product catalog schema with cost/sale price and shipping strategy.
create extension if not exists pgcrypto;

create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  description text default '',
  category_id text not null,
  material text default '',
  currency text default 'CNY',
  cost_currency text default 'CNY',
  sale_currency text default 'CNY',
  cost_price numeric not null,
  sale_price numeric not null,
  compare_at_price numeric,
  source_type text default 'origin',
  shipping_quote_mode text default 'quote_after_confirm',
  is_free_shipping_overseas boolean default false,
  asset_status text default 'published',
  images text[] default '{}',
  video_url text,
  specs jsonb default '{}'::jsonb,
  add_on_options text[] default '{}',
  visible_regions text[] default '{"ALL"}',
  shippable_countries text[] default '{}',
  featured boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table products add column if not exists cost_currency text default 'CNY';
alter table products add column if not exists sale_currency text default 'CNY';
alter table products add column if not exists asset_status text default 'published';

alter table products enable row level security;
drop policy if exists "Allow select products" on products;
drop policy if exists "Allow insert products" on products;
drop policy if exists "Allow update products" on products;

create policy "Allow select products" on products for select using (true);
create policy "Allow insert products" on products for insert with check (true);
create policy "Allow update products" on products for update using (true);

