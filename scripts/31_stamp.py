from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
import io, glob

f = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
pdfmetrics.registerFont(TTFont('DJ', f))

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
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
