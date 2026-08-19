-- Прогресс тренажёра: одна строка на пользователя, всё содержимое localStorage в jsonb.
-- Выполнить один раз в SQL Editor нового проекта Supabase.
--
-- Схема намеренно простая: приложение офлайн-первое, база — только копия для переноса
-- между устройствами и отчёта владельцу. Разбирать прогресс на таблицы смысла нет.

create table if not exists public.bar_progress (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.bar_progress enable row level security;

-- Каждый видит и правит только свою строку.
drop policy if exists "bar_progress_select_own" on public.bar_progress;
create policy "bar_progress_select_own" on public.bar_progress
  for select using (auth.uid() = user_id);

drop policy if exists "bar_progress_insert_own" on public.bar_progress;
create policy "bar_progress_insert_own" on public.bar_progress
  for insert with check (auth.uid() = user_id);

drop policy if exists "bar_progress_update_own" on public.bar_progress;
create policy "bar_progress_update_own" on public.bar_progress
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Отчёт «кто как сдаёт» для владельца: смотреть в SQL Editor под service-ключом.
--   select u.email,
--          (p.data->'stats'->>'runs')::int   as попыток,
--          (p.data->'stats'->>'best')::int   as лучший,
--          jsonb_object_keys_count(p.data->'errors') as ошибок,
--          p.updated_at
--     from public.bar_progress p join auth.users u on u.id = p.user_id
--    order by p.updated_at desc;
