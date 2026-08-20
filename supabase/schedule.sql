-- График смен: точки, сотрудники, полумесячные периоды, смены, события и настройки.
-- Выполняется один раз в SQL Editor проекта bar-trainer (bprfxixyqonjboxyrnyc).
--
-- Почему схема именно такая — три решения, которые не выводятся из кода:
--
-- 1. Сотрудник и аккаунт — РАЗНЫЕ сущности. В таблице бара 8 человек, а аккаунтов
--    в приложении пока почти нет. График не может ждать, пока все зарегистрируются,
--    поэтому staff.user_id заполняется потом, когда человек заведёт вход.
-- 2. На один день у одного человека может быть НЕСКОЛЬКО смен: в рабочей таблице
--    встречается «9-12, 18-01» — вышел утром и вечером. Поэтому уникальности
--    на (staff_id, day, layer) нет, это две обычные строки.
-- 3. Пожелания и собранный график — одна таблица с колонкой layer. Так пожелания
--    рисуются подложкой под график одним запросом, а не джойном двух таблиц.

-- ------------------------------------------------------------------ точки
create table if not exists public.venues (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  address    text,
  org        text,
  -- Своя точка сети или чужая. «Нахимовский» и «Коменда» заводятся точками,
  -- чтобы смена на них была обычной сменой с часами, а не пометкой в клетке.
  is_own     boolean not null default false,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------- сотрудники
create table if not exists public.staff (
  id         uuid primary key default gen_random_uuid(),
  venue_id   uuid not null references public.venues(id) on delete cascade,
  dept       text not null default 'bar',
  name       text not null,
  category   smallint not null default 1 check (category between 1 and 3),
  -- Старший бармен — роль в графике, а не в аккаунте: назначает менеджер,
  -- и это не «любой бармен 3-й категории».
  sched_role text not null default 'bartender' check (sched_role in ('bartender','senior')),
  hours_norm numeric(6,2),
  rate       numeric(10,2),                 -- под будущий ФОТ, пока не используется
  user_id    uuid unique references auth.users(id) on delete set null,
  active     boolean not null default true,
  sort       int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists staff_venue_idx on public.staff (venue_id, dept, active);

-- ------------------------------------------------------------- полумесяцы
create table if not exists public.periods (
  id            uuid primary key default gen_random_uuid(),
  venue_id      uuid not null references public.venues(id) on delete cascade,
  dept          text not null default 'bar',
  year          smallint not null,
  month         smallint not null check (month between 1 and 12),
  half          smallint not null check (half in (1, 2)),   -- 1–15 и 16–конец месяца
  -- wish: собираем пожелания · draft: старший собирает · published: выкачен всем
  state         text not null default 'wish' check (state in ('wish','draft','published')),
  wish_deadline date,
  published_at  timestamptz,
  published_by  uuid references auth.users(id),
  unique (venue_id, dept, year, month, half)
);

-- ----------------------------------------------------------------- смены
create table if not exists public.shifts (
  id          uuid primary key default gen_random_uuid(),
  period_id   uuid not null references public.periods(id) on delete cascade,
  staff_id    uuid not null references public.staff(id) on delete cascade,
  -- venue_id дублирует точку периода намеренно: без него каждая RLS-политика
  -- лезла бы в periods через подзапрос
  venue_id    uuid not null references public.venues(id) on delete cascade,
  day         date not null,
  layer       text not null check (layer in ('wish','plan')),
  kind        text not null default 'work' check (kind in ('work','off')),
  start_h     smallint check (start_h between 0 and 23),
  end_h       smallint check (end_h between 0 and 23),
  -- Работа на чужой точке («нахим», «Коменда»): часы человеку считаются,
  -- а в счётчик барменов своей точки такая смена не идёт. NULL = своя.
  at_venue_id uuid references public.venues(id),
  note        text,
  author_id   uuid references auth.users(id),
  updated_at  timestamptz not null default now(),
  -- У смены есть часы, у выходного их нет. Исключение — работа на чужой точке:
  -- в рабочей таблице «нахим» и «Коменда» написаны без времени, часы у нас
  -- просто не записаны. Придумывать их нельзя, поэтому такая смена живёт без часов.
  constraint shifts_hours_ck check (
    (kind = 'work' and ((start_h is not null and end_h is not null) or at_venue_id is not null)) or
    (kind = 'off'  and start_h is null and end_h is null)
  ),
  -- Ночная смена «16-04» считается целиком в день начала: 12 часов, не делится
  -- по полуночи. Так же читается текущая рабочая таблица.
  hours smallint generated always as (
    case when kind <> 'work' or start_h is null or end_h is null then 0
         when end_h = start_h then 24
         else (end_h - start_h + 24) % 24 end
  ) stored
);
create index if not exists shifts_period_idx on public.shifts (period_id, layer);
create index if not exists shifts_staff_idx  on public.shifts (staff_id, day);
create index if not exists shifts_day_idx    on public.shifts (venue_id, day, layer);

-- --------------------------------------------------- события и комментарии
-- Всё, что раньше писали прямо в клетку (квиз, генка, ЕГАИС, инвентаризация,
-- концерт), теперь событие дня. Создать его может любой сотрудник.
create table if not exists public.day_events (
  id         uuid primary key default gen_random_uuid(),
  venue_id   uuid not null references public.venues(id) on delete cascade,
  dept       text not null default 'bar',
  day        date not null,
  kind       text not null default 'other',
  title      text not null,
  author_id  uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create index if not exists day_events_idx on public.day_events (venue_id, dept, day);

create table if not exists public.day_notes (
  id         uuid primary key default gen_random_uuid(),
  venue_id   uuid not null references public.venues(id) on delete cascade,
  dept       text not null default 'bar',
  day        date not null,
  body       text not null,
  author_id  uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create index if not exists day_notes_idx on public.day_notes (venue_id, dept, day);

-- -------------------------------------------------------------- настройки
-- Лимиты часов по дням недели, минимум барменов, норма часов, частые смены
-- для быстрых кнопок и ставки по категориям. Цифры вводит старший в приложении,
-- в коде их нет — поэтому jsonb, а не два десятка колонок.
create table if not exists public.sched_settings (
  venue_id   uuid not null references public.venues(id) on delete cascade,
  dept       text not null default 'bar',
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (venue_id, dept)
);

-- ============================================================ доступ (RLS)
-- Функции SECURITY DEFINER и обязательно они: политика на staff, которая читает
-- staff обычным запросом, уходит в бесконечную рекурсию RLS.

create or replace function public.my_venue()
returns uuid language sql stable security definer set search_path = public as $$
  select venue_id from public.staff where user_id = auth.uid() and active limit 1;
$$;

create or replace function public.my_staff_id()
returns uuid language sql stable security definer set search_path = public as $$
  select id from public.staff where user_id = auth.uid() and active limit 1;
$$;

-- Роль аккаунта приходит в app_metadata при входе и правится только admin API.
create or replace function public.app_role()
returns text language sql stable as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', 'staff');
$$;

-- «Начальник» для графика: старший бармен точки либо менеджер и выше.
-- Заказчик просил, чтобы старший мог править сотрудникам всё — категорию,
-- норму часов, роль, — поэтому одна проверка на все таблицы графика.
create or replace function public.is_boss()
returns boolean language sql stable security definer set search_path = public as $$
  select public.app_role() in ('manager','director','owner')
      or exists (select 1 from public.staff
                  where user_id = auth.uid() and active and sched_role = 'senior');
$$;

-- Владелец и директор смотрят любые точки, остальные — только свою.
create or replace function public.sees_venue(v uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select public.app_role() in ('director','owner') or v = public.my_venue();
$$;

alter table public.venues         enable row level security;
alter table public.staff          enable row level security;
alter table public.periods        enable row level security;
alter table public.shifts         enable row level security;
alter table public.day_events     enable row level security;
alter table public.day_notes      enable row level security;
alter table public.sched_settings enable row level security;

-- Точки видят все вошедшие: без списка точек не показать «работает на Коменде».
drop policy if exists venues_read on public.venues;
create policy venues_read on public.venues
  for select to authenticated using (true);
drop policy if exists venues_write on public.venues;
create policy venues_write on public.venues
  for all to authenticated using (public.is_boss()) with check (public.is_boss());

-- Сотрудники: читает вся точка, правит старший и выше.
drop policy if exists staff_read on public.staff;
create policy staff_read on public.staff
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists staff_write on public.staff;
create policy staff_write on public.staff
  for all to authenticated using (public.is_boss()) with check (public.is_boss());

drop policy if exists periods_read on public.periods;
create policy periods_read on public.periods
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists periods_write on public.periods;
create policy periods_write on public.periods
  for all to authenticated using (public.is_boss()) with check (public.is_boss());

-- Смены. Заказчик решил: видно всё и всегда — и чужие пожелания, и черновик
-- графика до выкатки. Это сознательный выбор, а не недосмотр в политике.
drop policy if exists shifts_read on public.shifts;
create policy shifts_read on public.shifts
  for select to authenticated using (public.sees_venue(venue_id));

-- Пожелания правит сам сотрудник (и старший, когда собирает график).
drop policy if exists shifts_wish_write on public.shifts;
create policy shifts_wish_write on public.shifts
  for all to authenticated
  using      (layer = 'wish' and (staff_id = public.my_staff_id() or public.is_boss()))
  with check (layer = 'wish' and (staff_id = public.my_staff_id() or public.is_boss()));

-- Сам график — только старший и выше.
drop policy if exists shifts_plan_write on public.shifts;
create policy shifts_plan_write on public.shifts
  for all to authenticated
  using      (layer = 'plan' and public.is_boss())
  with check (layer = 'plan' and public.is_boss());

-- События и комментарии заводит любой сотрудник, убирает автор или старший.
drop policy if exists day_events_read on public.day_events;
create policy day_events_read on public.day_events
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists day_events_add on public.day_events;
create policy day_events_add on public.day_events
  for insert to authenticated with check (public.sees_venue(venue_id));
drop policy if exists day_events_edit on public.day_events;
create policy day_events_edit on public.day_events
  for update to authenticated
  using (author_id = auth.uid() or public.is_boss())
  with check (author_id = auth.uid() or public.is_boss());
drop policy if exists day_events_del on public.day_events;
create policy day_events_del on public.day_events
  for delete to authenticated using (author_id = auth.uid() or public.is_boss());

drop policy if exists day_notes_read on public.day_notes;
create policy day_notes_read on public.day_notes
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists day_notes_add on public.day_notes;
create policy day_notes_add on public.day_notes
  for insert to authenticated with check (public.sees_venue(venue_id));
drop policy if exists day_notes_edit on public.day_notes;
create policy day_notes_edit on public.day_notes
  for update to authenticated
  using (author_id = auth.uid() or public.is_boss())
  with check (author_id = auth.uid() or public.is_boss());
drop policy if exists day_notes_del on public.day_notes;
create policy day_notes_del on public.day_notes
  for delete to authenticated using (author_id = auth.uid() or public.is_boss());

drop policy if exists sched_settings_read on public.sched_settings;
create policy sched_settings_read on public.sched_settings
  for select to authenticated using (public.sees_venue(venue_id));
drop policy if exists sched_settings_write on public.sched_settings;
create policy sched_settings_write on public.sched_settings
  for all to authenticated using (public.is_boss()) with check (public.is_boss());

-- ================================================================ засев
-- Точка одна, плюс две чужие — они нужны только как метка «работал не у нас».
insert into public.venues (name, address, org, is_own)
select 'ТС-45', 'ул. Сизова 9', 'ООО «ИНФИНИТИ»', true
where not exists (select 1 from public.venues where name = 'ТС-45');
insert into public.venues (name, is_own)
select 'Нахимовский', false
where not exists (select 1 from public.venues where name = 'Нахимовский');
insert into public.venues (name, is_own)
select 'Коменда', false
where not exists (select 1 from public.venues where name = 'Коменда');

-- Состав бара на 20.08.2026 — восемь человек из последних трёх месяцев рабочей
-- таблицы. Категории в таблице нет, поэтому у всех 1-я: заказчик проставит их
-- в приложении, там же назначит старшего.
insert into public.staff (venue_id, name, sort)
select v.id, x.name, x.sort
  from public.venues v,
       (values ('Уржумов Василий', 1), ('Нурматов Артур', 2), ('Голубев Иван', 3),
               ('Волков Роман', 4),    ('Кузьмина Ксения', 5), ('Дутов Михаил', 6),
               ('Набиев Камил', 7),    ('Михайлов Никита', 8)) as x(name, sort)
 where v.name = 'ТС-45'
   and not exists (select 1 from public.staff s where s.name = x.name and s.venue_id = v.id);

insert into public.sched_settings (venue_id, data)
select v.id, jsonb_build_object(
         -- лимиты часов и минимум барменов по дням недели: 1 = понедельник.
         -- Нули означают «не задано» — подсветки не будет, пока не заполнят.
         'hour_limit', jsonb_build_object('1',0,'2',0,'3',0,'4',0,'5',0,'6',0,'7',0),
         'min_staff',  jsonb_build_object('1',0,'2',0,'3',0,'4',0,'5',0,'6',0,'7',0),
         'hours_norm', 0,
         -- Быстрые кнопки в нижнем листе. Взяты из самых частых смен таблицы.
         'quick', jsonb_build_array('16-04','10-18','10-22','12-01','18-04','09-13'),
         'rates', jsonb_build_object('1',0,'2',0,'3',0))
  from public.venues v
 where v.name = 'ТС-45'
   and not exists (select 1 from public.sched_settings s where s.venue_id = v.id);
