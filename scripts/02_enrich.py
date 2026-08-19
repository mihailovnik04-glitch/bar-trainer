# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d=json.load(open(ROOT/'data'/'drinks.json', encoding='utf-8'))

GLASS_FIX = {
 'Кабуки':'Жестяная банка',
 'Нулевой пациент 0,0':'Шоты (4 шт)',
 'Сицилийский взвар':'Цветная чашка',
 'Малиновый Взвар / с ежевикой':'Цветная чашка',
 'Облепиховый Взвар':'Цветная чашка',
 'Вишневый Взвар с кедром':'Цветная чашка',
 'Рафунтелла':'Цветная чашка',
 'Мохито XL':'Хайбол 620 / Ступенька XL',
}
def glass(m, name, sheet):
    if name in GLASS_FIX: return GLASS_FIX[name]
    ml=m.lower()
    if 'стакан с собой' in ml or 'стакане с собой' in ml or 'прозрачный стакан' in ml or 'прозрачном стакане' in ml: return 'Стакан с собой'
    if 'пластиков' in ml and 'бутылк' in ml: return 'Бутылка ПЭТ'
    if sheet=='Шотики': return 'Шоты'
    if 'кувшин' in ml: return 'Кувшин 1 л'
    q=re.findall(r'(?i)бокал[а-я]*\s*[«"]([^»"]+)[»"]', m)
    if q: return q[0].strip()
    if 'винный бокал' in ml or 'винного бокала' in ml or 'винном бокале' in ml: return 'Винный бокал'
    if 'смесительный стакан' in ml or 'смесительном стакане' in ml: return 'Ступенька М'
    return ''

def tech(m):
    ml=m.lower()
    if 'блендер' in ml: return 'Блендер'
    if 'взбить' in ml or 'шейкерный стакан' in ml or 'шейкерном стакане' in ml or 'взбивать' in ml and 'блендер' not in ml: return 'Шейк'
    if 'питчер' in ml: return 'Питчер'
    if 'стир' in ml: return 'Стир'
    return 'Билд'

def straw(serve):
    s=serve.lower()
    if 'без трубоч' in s: return 'Без трубочки'
    if 'толстой трубочкой' in s: return 'Толстая трубочка'
    if 'изгибом' in s: return 'Трубочка с изгибом'
    if 'коротк' in s: return 'Короткая трубочка'
    if 'джус болл' in s: return 'Трубочка для джус боллов'
    return ''

SHORT=[(r'^ПФ\s+',''),(r'СуперДжус','СДЖ'),(r'Суперджус','СДЖ'),
       (r'Тоник ПЭТ\s*1л','тоник'),(r'Содовая ПЭТ\s*1л','содовая'),(r'Кола ПЭТ\s*1\s*л','кола'),
       (r'Сок Апельсин пакет','сок апельсин'),(r'Сок Персик пакет','сок персик'),
       (r'Сок Ананас пакет','сок ананас'),(r'Вода горячая','гор. вода')]
def short(n):
    s=re.sub(r'\s*укр\.?\s*\*?$','',n.strip())
    for a,b in SHORT: s=re.sub(a,b,s)
    return s.strip()

out=[]
for x in d:
    ing=[];gar=[]
    for n,a in x['ing']:
        (gar if re.search(r'укр', n.lower()) else ing).append([n,a])
    x['ing_main']=ing; x['garnish']=gar
    x['glass']=glass(x['method'],x['name'],x['sheet'])
    x['tech']=tech(x['method'])
    x['straw']=straw(x['serve'])
    parts=[]
    for n,a in ing:
        v=re.search(r'(\d+[.,]?\d*)',a)
        if v: parts.append((v.group(1), short(n).lower()))
    x['formula']=parts
    out.append(x)
json.dump(out, open(ROOT/'data'/'drinks2.json','w', encoding='utf-8'), ensure_ascii=False, indent=1)
for x in out:
    print(f"{x['name'][:33]:35}|{x['tech']:8}|{x['glass'][:20]:22}|{x['straw'][:20]:22}|{x['total']}")
