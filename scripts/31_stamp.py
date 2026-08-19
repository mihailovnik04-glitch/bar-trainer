from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
import io, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Во встроенных шрифтах reportlab нет кириллицы, поэтому подкладываем системный TTF.
# Порядок: свой шрифт в fonts/ (если положат), DejaVu на Linux, Arial/Segoe на Windows.
CANDIDATES = [
    ROOT / 'fonts' / 'DejaVuSans.ttf',
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    Path('/Library/Fonts/Arial Unicode.ttf'),
    Path('C:/Windows/Fonts/arial.ttf'),
    Path('C:/Windows/Fonts/segoeui.ttf'),
]
f = next((p for p in CANDIDATES if p.exists()), None)
if f is None:
    raise SystemExit('Не найден TTF с кириллицей. Положите DejaVuSans.ttf в fonts/ '
                     'или укажите свой путь в CANDIDATES (scripts/31_stamp.py).')
pdfmetrics.registerFont(TTFont('DJ', str(f)))
src = PdfReader(str(ROOT/'build'/'manual.pdf'))
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=A4)
W, H = A4
for i in range(len(src.pages)):
    if i > 0:
        c.setFont('DJ', 7)
        c.setFillColorRGB(.55, .52, .47)
        c.drawString(13*2.8346, 9*2.8346, 'Барное пособие · технологические карты')
        c.drawRightString(W-13*2.8346, 9*2.8346, str(i+1))
    c.showPage()
c.save()
buf.seek(0)
ov = PdfReader(buf)
w = PdfWriter()
for i, p in enumerate(src.pages):
    p.merge_page(ov.pages[i])
    w.add_page(p)
w.add_metadata({'/Title': 'Барное пособие — от формулы к напитку', '/Author': 'Бар'})
with open(ROOT/'build'/'manual_final.pdf', 'wb') as fh:
    w.write(fh)
print('stamped', len(src.pages))
