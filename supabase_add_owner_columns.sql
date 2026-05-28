-- Run in Supabase SQL Editor before deploying the auth update.

-- 1. Add owner columns to products table
alter table products add column if not exists owner_id    text default '';
alter table products add column if not exists owner_email text default '';
alter table products add column if not exists winery_name text default '';

-- 2. Index for fast per-owner queries
create index if not exists idx_products_owner on products(owner_id);

-- 3. Update reporting view to include owner fields
create or replace view products_report as
select
  id, name, vintage, variety, region, producer_name, collection, status,
  owner_id, owner_email, winery_name, updated_at,
  data->>'product_category'        as product_category,
  data->>'country'                 as country,
  data->>'abv'                     as abv,
  data->>'net_quantity'            as net_quantity,
  data->>'lot_number'              as lot_number,
  data->>'sweetness_descriptor'    as sweetness_descriptor,
  (data->>'pregnancy_warning')::boolean    as pregnancy_warning,
  (data->>'responsible_drinking')::boolean as responsible_drinking,
  (data->'nutrition'->>'energy_kj')::numeric     as energy_kj,
  (data->'nutrition'->>'energy_kcal')::numeric    as energy_kcal,
  (data->'nutrition'->>'fat_g')::numeric          as fat_g,
  (data->'nutrition'->>'carbohydrate_g')::numeric as carbohydrate_g,
  (data->'nutrition'->>'sugars_g')::numeric       as sugars_g,
  (data->'nutrition'->>'protein_g')::numeric      as protein_g,
  (data->'nutrition'->>'salt_g')::numeric         as salt_g,
  data->'packaging'->>'bottle_material'    as bottle_material,
  data->'packaging'->>'closure_type'       as closure_type,
  data->'packaging'->>'label_material'     as label_material,
  (data->'sustainability'->>'carbon_footprint_kg')::numeric as carbon_footprint_kg,
  (data->'sustainability'->>'water_usage_l')::numeric       as water_usage_l,
  (data->'sustainability'->>'renewable_energy')::boolean    as renewable_energy,
  data->'supply_chain'->>'vineyard_name'        as vineyard_name,
  data->'supply_chain'->>'vineyard_country'     as vineyard_country,
  data->'supply_chain'->>'grape_origin_country' as grape_origin_country,
  data->'supply_chain'->>'importer_name'        as importer_name,
  (data->>'created_at')::timestamptz as created_at
from products;
