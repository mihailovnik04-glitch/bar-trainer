# -*- coding: utf-8 -*-
"""Импорт графика смен из рабочей Google-таблицы бара.

    python scripts/50_sched_import.py            разбор и отчёт, база не трогается
    python scripts/50_sched_import.py --push     то же + заливка в Supabase

Таблица открыта на чтение, поэтому CSV забирается прямо по ссылке и в репозитории
не хранится. Разбирается лист «график»: блоки по полумесяцам, строка сотрудника,
клетка дня.

Данные в таблице живые и грязные — за полтора года там накопилось всё сразу:

* выходной пишут четырьмя способами: x, х, Х, ×  (латиница, кириллица, знак умножения);
* разделитель смены то дефис, то слэш: «18-04» и «18/04», плюс опечатка «10--18»;
* в одной клетке бывает ДВЕ смены: «9-12, 18-01» — вышел утром и вечером;
* «нахим» и «Коменда» — работа на другой точке, время не записано;
* «квиз», «генка», «инв», «атестация», «БПС» — события дня, а не смена;
* «до4», «как вс», «!!», «?», «др», «дела» — комментарии к дню;
* однобуквенные клетки (у, е, л, о, т, д…) — кто-то растянул слово по горизонтали;
* числа без тире (34, 66, 639) — строки итогов по часам.

Ничего из этого не угадывается на ходу: всё, что не разобралось, попадает в отчёт,
а не в базу. Заливаются только последние LAST_BLOCKS полумесяцев — заказчик просил
2–3 месяца истории, а не полтора года.
"""
import sys, re, csv, io, json, collections, urllib.request

SHEET = '1T_ZZgToc5YIp_B2galr9bxKB7rstyQWU8S-HqziynYc'
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET}/export?format=csv&gid=0'
PROJECT = 'bprfxixyqonjboxyrnyc'
LAST_BLOCKS = 6                  # шесть полумесяцев = три месяца
FIRST_YEAR = 2025                # первый блок таблицы — 16 сентября 2025 (проверено по дням недели)

PUSH = '--push' in sys.argv

# ------------------------------------------------------------------ разбор
MONTHS = [('янв', 1), ('фев', 2), ('мар', 3), ('апр', 4), ('мая', 5), ('май', 5),
          ('ма', 5), ('июн', 6), ('июл', 7), ('авг', 8), ('сен', 9), ('окт', 10),
          ('ноя', 11), ('дек', 12)]
DATE_RE = re.compile(r'^(\d{1,2})\s*[.\-]\s*([а-яё]+)\.?$', re.I)
SHIFT_RE = re.compile(r'^(\d{1,2})\s*[-/]+\s*(\d{1,2})$')
OFF = {'x', 'х', 'X', 'Х', '×'}
# Пометки, которые заказчик решил сделать событиями дня.
EVENTS = {'квиз': 'Квиз', 'генка': 'Генеральная уборка', 'инв': 'Инвентаризация',
          'инвента': 'Инвентаризация', 'егаис': 'ЕГАИС', 'атестация': 'Аттестация',
          'аттестация': 'Аттестация', 'бпс': 'БПС', 'концерт': 'Концерт'}
# Чужие точки: часы не записаны, но смена была.
OTHER_VENUE = {'нахим': 'Нахимовский', 'коменда': 'Коменда'}
# Всё остальное осмысленное — комментарий к дню. Однобуквенных здесь быть не должно:
# заказчик подтвердил, что это слово, растянутое по клеткам, а не пометка.
NOTES = {'до4', 'как вс', '!!', '?', 'др', 'дела'}


def parse_date(cell):
    """'16.сен' / '1-нояб.' / '15-мая' -> (день, месяц). None, если это не дата."""
    m = DATE_RE.match(cell.strip())
    if not m:
        return None
    day, mon = int(m.group(1)), m.group(2).lower().replace('ё', 'е')
    for pref, num in MONTHS:
        if mon.startswith(pref):
            return day, num
    return None


def load_rows():
    req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'curl/8.4.0'})
    body = urllib.request.urlopen(req).read().decode('utf-8')
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(body))]


def find_blocks(rows):
    """Индексы строк с датами. Блок = эта строка + строки сотрудников под ней."""
    out = []
    for i, r in enumerate(rows):
        if sum(1 for c in r[1:] if parse_date(c)) >= 5:
            out.append(i)
    return out


def block_days(rows, i):
    """[(колонка, день, месяц)] для строки дат."""
    return [(col, *parse_date(c)) for col, c in enumerate(rows[i]) if col and parse_date(c)]


def years_for(blocks_months):
    """Год каждому блоку: идём по порядку и переваливаем через новый год,
    когда номер месяца становится меньше предыдущего."""
    out, year, prev = [], FIRST_YEAR, 0
    for m in blocks_months:
        if prev and m < prev:
            year += 1
        out.append(year)
        prev = m
    return out


def norm_cell(raw):
    """Клетка -> список записей. Каждая запись — словарь с ключом kind:
       shift | off | venue | event | note | drop"""
    c = raw.strip()
    if not c:
        return []
    if c in OFF:
        return [{'kind': 'off'}]
    low = c.lower().replace('ё', 'е')
    # Две смены в одной клетке: «9-12, 18-01»
    if ',' in c and all(SHIFT_RE.match(p.strip()) for p in c.split(',') if p.strip()):
        return [{'kind': 'shift', 'start': int(SHIFT_RE.match(p.strip()).group(1)),
                 'end': int(SHIFT_RE.match(p.strip()).group(2))}
                for p in c.split(',') if p.strip()]
    m = SHIFT_RE.match(c)
    if m:
        s, e = int(m.group(1)), int(m.group(2))
        if s > 23 or e > 23:
            return [{'kind': 'drop', 'why': 'час больше 23', 'raw': c}]
        return [{'kind': 'shift', 'start': s, 'end': e}]
    if low in OTHER_VENUE:
        return [{'kind': 'venue', 'venue': OTHER_VENUE[low]}]
    if low in EVENTS:
        return [{'kind': 'event', 'title': EVENTS[low]}]
    if low in NOTES:
        return [{'kind': 'note', 'body': c}]
    # Однобуквенные клетки — слово, растянутое по горизонтали. Числа без тире —
    # строки итогов по часам. И то, и другое выбрасываем, но считаем.
    if len(c) == 1 and c.isalpha():
        return [{'kind': 'drop', 'why': 'одна буква', 'raw': c}]
    if c.replace(' ', '').isdigit():
        return [{'kind': 'drop', 'why': 'число без тире (итог часов)', 'raw': c}]
    return [{'kind': 'unknown', 'raw': c}]


def parse():
    rows = load_rows()
    blocks = find_blocks(rows)
    months = [block_days(rows, i)[0][2] for i in blocks]
    years = years_for(months)

    out = []
    for n, i in enumerate(blocks):
        days = block_days(rows, i)
        end = blocks[n + 1] - 2 if n + 1 < len(blocks) else len(rows)
        year, month = years[n], days[0][2]
        half = 1 if days[0][1] <= 15 else 2
        people = []
        for r in rows[i + 1:end]:
            if not r or not r[0] or len(r[0]) > 28 or not any(r[1:]):
                continue
            if r[0].lower() in ('часы', 'итог'):        # служебные строки
                continue
            cells = []
            for col, day, mon in days:
                raw = r[col] if col < len(r) else ''
                for rec in norm_cell(raw):
                    rec['day'], rec['raw'] = day, raw
                    cells.append(rec)
            if cells:
                people.append({'name': r[0], 'cells': cells})
        out.append({'year': year, 'month': month, 'half': half,
                    'days': [d for _, d, _ in days], 'people': people})
    return out


# ------------------------------------------------------------------- отчёт
MON_RU = ['', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
          'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']


def report(blocks):
    take = blocks[-LAST_BLOCKS:]
    print(f'блоков в таблице: {len(blocks)} · заливаем последние {len(take)}')
    print()
    tot = collections.Counter()
    unknown = collections.Counter()
    dropped = collections.Counter()
    for b in take:
        cnt = collections.Counter(c['kind'] for p in b['people'] for c in p['cells'])
        hrs = sum((c['end'] - c['start'] + 24) % 24 or 24
                  for p in b['people'] for c in p['cells'] if c['kind'] == 'shift')
        print(f"  {MON_RU[b['month']]} {b['year']} · половина {b['half']} "
              f"({len(b['days'])} дн., {len(b['people'])} чел.)  "
              f"смен {cnt['shift']}, выходных {cnt['off']}, часов {hrs}")
        tot.update(cnt)
        for p in b['people']:
            for c in p['cells']:
                if c['kind'] == 'unknown':
                    unknown[c['raw']] += 1
                elif c['kind'] == 'drop':
                    dropped[c['why']] += 1
    print()
    print('итого:', ', '.join(f'{k} {v}' for k, v in sorted(tot.items())))
    if dropped:
        print('выброшено:', ', '.join(f'{k} — {v}' for k, v in dropped.most_common()))
    if unknown:
        print()
        print('НЕ РАЗОБРАЛОСЬ (в базу не пойдёт, разбирать руками):')
        for raw, n in unknown.most_common():
            print(f'   {raw!r} ×{n}')
    else:
        print('не разобралось: ничего')
    names = sorted({p['name'] for b in take for p in b['people']})
    print()
    print(f'имён в этих блоках: {len(names)} — {", ".join(names)}')
    return take


# ------------------------------------------------------------------ заливка
def api(sql):
    token = None
    for line in io.open('supabase/.token', encoding='utf-8') if False else []:
        pass
    token = TOKEN
    req = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{PROJECT}/database/query',
        data=json.dumps({'query': sql}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                 'User-Agent': 'curl/8.4.0'}, method='POST')
    return json.load(urllib.request.urlopen(req))


def q(s):
    """Строка для SQL-литерала."""
    return "'" + str(s).replace("'", "''") + "'"


def push(take):
    venues = {r['name']: r['id'] for r in api('select id, name from public.venues')}
    staff = {r['name']: r['id'] for r in api('select id, name from public.staff')}
    home = venues['ТС-45']
    miss = sorted({p['name'] for b in take for p in b['people']} - set(staff))
    if miss:
        print('НЕТ В staff (пропущены):', ', '.join(miss))

    for b in take:
        # Границы периода теперь подвижные (их двигает старший), поэтому ключ —
        # дата начала, а не пара «месяц + половина».
        d_from = f"{b['year']}-{b['month']:02d}-{min(b['days']):02d}"
        d_to = f"{b['year']}-{b['month']:02d}-{max(b['days']):02d}"
        api(f"""insert into public.periods (venue_id, dept, year, month, half, d_from, d_to, state)
                values ({q(home)}, 'bar', {b['year']}, {b['month']}, {b['half']},
                        {q(d_from)}, {q(d_to)}, 'published')
                on conflict (venue_id, dept, d_from)
                do update set d_to = excluded.d_to, state = 'published'""")
        pid = api(f"""select id from public.periods where venue_id={q(home)} and dept='bar'
                       and d_from={q(d_from)}""")[0]['id']
        # Перезаливка идемпотентна: слой plan этого периода стираем и пишем заново.
        api(f"delete from public.shifts where period_id={q(pid)} and layer='plan'")
        rows, events, notes = [], [], []
        for p in b['people']:
            sid = staff.get(p['name'])
            if not sid:
                continue
            for c in p['cells']:
                day = f"{b['year']}-{b['month']:02d}-{c['day']:02d}"
                if c['kind'] == 'shift':
                    rows.append(f"({q(pid)},{q(sid)},{q(home)},{q(day)},'plan','work',"
                                f"{c['start']},{c['end']},null)")
                elif c['kind'] == 'off':
                    rows.append(f"({q(pid)},{q(sid)},{q(home)},{q(day)},'plan','off',"
                                f"null,null,null)")
                elif c['kind'] == 'venue':
                    rows.append(f"({q(pid)},{q(sid)},{q(home)},{q(day)},'plan','work',"
                                f"null,null,{q(venues[c['venue']])})")
                elif c['kind'] == 'event':
                    events.append((day, c['title']))
                elif c['kind'] == 'note':
                    notes.append((day, f"{p['name']}: {c['raw']}"))
        for i in range(0, len(rows), 200):
            api('insert into public.shifts (period_id, staff_id, venue_id, day, layer, kind,'
                ' start_h, end_h, at_venue_id) values ' + ','.join(rows[i:i + 200]))
        for day, title in set(events):
            api(f"""insert into public.day_events (venue_id, dept, day, kind, title)
                    select {q(home)}, 'bar', {q(day)}, 'other', {q(title)}
                     where not exists (select 1 from public.day_events
                                        where venue_id={q(home)} and day={q(day)} and title={q(title)})""")
        for day, body in set(notes):
            api(f"""insert into public.day_notes (venue_id, dept, day, body)
                    select {q(home)}, 'bar', {q(day)}, {q(body)}
                     where not exists (select 1 from public.day_notes
                                        where venue_id={q(home)} and day={q(day)} and body={q(body)})""")
        print(f"  залито: {MON_RU[b['month']]} {b['year']} половина {b['half']} — "
              f"строк {len(rows)}, событий {len(set(events))}, комментариев {len(set(notes))}")


TOKEN = ''
if __name__ == '__main__':
    blocks = parse()
    take = report(blocks)
    if PUSH:
        import os
        TOKEN = os.environ.get('SUPABASE_TOKEN', '')
        if not TOKEN:
            sys.exit('\nНужен токен: SUPABASE_TOKEN=sbp_… python scripts/50_sched_import.py --push')
        print()
        push(take)
    else:
        print('\n(это только разбор; заливка — с флагом --push)')
