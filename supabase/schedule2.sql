-- График, вторая волна: справочник событий, подвижные границы периодов,
-- гибкие лимиты и мгновенная синхронизация.
-- Выполняется один раз в SQL Editor проекта bar-trainer, после schedule.sql.
--
-- Постановка заказчика 20.08.2026: события старший заводит сам с нуля и правит,
-- границы полумесяца двигает по своему усмотрению, лимиты настраивает полностью,
-- и всё это у всех обновляется сразу.

-- ------------------------------------------------- виды событий (справочник)
-- Раньше вид события был строкой из зашитого списка (квиз, генка, ЕГАИС…).
-- Теперь это таблица: старший добавляет свои, переименовывает и убирает.
-- hour_bonus — дополнительный лимит часов на такой день; понадобится ФОТ,
-- а подсветку перебора он меняет уже сейчас.
create table if not exists public.event_kinds (
  id         uuid primary key default gen_random_uuid(),
  venue_id   uuid not null references public.venues(id) on delete cascade,
  dept       text not null default 'bar',
  name       text not null,
  color      text not null default '#E0A45B',
  hour_bonus smallint not null default 0,
  sort       int not null default 0,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists event_kinds_idx on public.event_kinds (venue_id, dept, active);

-- Событие дня ссылается на вид. title оставлен: разовое событие можно завести
-- без вида, просто текстом, и не засорять справочник.
alter table public.day_events
  add column if not exists kind_id uuid references public.event_kinds(id) on delete set null;
alter table public.day_events alter column title drop not null;
alter table public.day_events
  add constraint day_events_named_ck check (kind_id is not null or title is not null);

-- ------------------------------------------------- подвижные границы периода
-- Полумесяц перестал быть 1–15 и 16–конец: заказчик двигает границы сам.
-- year/month/half остаются подписью и сортировкой, источник истины — даты.
alter table public.periods add column if not exists d_from date;
alter table public.periods add column if not exists d_to   date;
alter table public.periods add column if not exists title  text;

update public.periods set
  d_from = coalesce(d_from, make_date(year, month, case when half = 1 then 1 else 16 end)),
  d_to   = coalesce(d_to,   case when half = 1 then make_date(year, month, 15)
                                 else (make_date(year, month, 1) + interval '1 month - 1 day')::date end)
 where d_from is null or d_to is null;

alter table public.periods alter column d_from set not null;
alter table public.periods alter column d_to   set not null;
alter table public.periods drop constraint if exists periods_range_ck;
alter table public.periods add  constraint periods_range_ck check (d_to >= d_from);

-- Старая уникальность (год, месяц, половина) мешает: в одном месяце теперь может
-- быть сколько угодно периодов с любыми границами.
alter table public.periods drop constraint if exists periods_venue_id_dept_year_month_half_key;
create unique index if not exists periods_from_uk on public.periods (venue_id, dept, d_from);

-- Периоды одной точки не должны пересекаться: иначе смена попадёт сразу в два
-- и часы посчитаются дважды. Проверяет база, а не приложение.
create extension if not exists btree_gist;
alter table public.periods drop constraint if exists periods_no_overlap;
alter table public.periods add constraint periods_no_overlap
  exclude using gist (venue_id with =, dept with =, daterange(d_from, d_to, '[]') with &&);

-- Смена обязана попадать в свой период. Без этого правки границ молча оставляли бы
-- висящие смены за пределами периода, и часы бы не сходились.
create or replace function public.shift_in_period()
returns trigger language plpgsql as $$
declare p record;
begin
  select d_from, d_to into p from public.periods where id = new.period_id;
  if new.day < p.d_from or new.day > p.d_to then
    raise exception 'смена % вне границ периода (% … %)', new.day, p.d_from, p.d_to;
  end if;
  return new;
end $$;
drop trigger if exists shifts_in_period on public.shifts;
create trigger shifts_in_period before insert or update of day, period_id
  on public.shifts for each row execute function public.shift_in_period();

-- ------------------------------------------------------------- RLS для нового
alter table public.event_kinds enable row level security;
drop policy if exists event_kinds_read on public.event_kinds;
create policy event_kinds_read on public.event_kinds
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists event_kinds_write on public.event_kinds;
create policy event_kinds_write on public.event_kinds
  for all to authenticated using (public.is_boss()) with check (public.is_boss());

-- ------------------------------------------------- мгновенная синхронизация
-- Без этой публикации Realtime молчит: изменения в таблицу идут, а подписчики
-- ничего не получают. REPLICA IDENTITY FULL нужна, чтобы в событии удаления
-- приходила вся строка, а не только первичный ключ — иначе клиент не поймёт,
-- какую клетку стирать.
alter table public.shifts         replica identity full;
alter table public.periods        replica identity full;
alter table public.day_events     replica identity full;
alter table public.day_notes      replica identity full;
alter table public.sched_settings replica identity full;
alter table public.staff          replica identity full;
alter table public.event_kinds    replica identity full;

do $$
declare t text;
begin
  foreach t in array array['shifts','periods','day_events','day_notes',
                           'sched_settings','staff','event_kinds','venues'] loop
    if not exists (select 1 from pg_publication_tables
                    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

-- --------------------------------------------------------------- засев видов
-- Стартовый набор — то, что реально писали в клетки рабочей таблицы. Дальше
-- старший правит его как хочет: это данные, а не константы в коде.
insert into public.event_kinds (venue_id, dept, name, color, hour_bonus, sort)
select v.id, 'bar', x.name, x.color, x.bonus, x.sort
  from public.venues v,
       (values ('Квиз','#7C5CFF',8,1), ('Генеральная уборка','#4FB477',6,2),
               ('Инвентаризация','#E0A45B',6,3), ('ЕГАИС','#5AA9E6',4,4),
               ('Концерт','#E2564B',10,5), ('Аттестация','#A78BFA',0,6))
       as x(name, color, bonus, sort)
 where v.is_own
   and not exists (select 1 from public.event_kinds k
                    where k.venue_id = v.id and k.name = x.name);

-- Старые события из импорта привязываем к видам по названию.
update public.day_events e set kind_id = k.id
  from public.event_kinds k
 where e.kind_id is null and k.venue_id = e.venue_id and k.name = e.title;
