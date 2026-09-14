"""Renderiza el catálogo real de escritorio para la interfaz independiente."""
import json
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from app.icons import draw_icon
from app.icon_data import ICON_CATALOG
from app.constants import EXPENSE_CATEGORIES, INCOME_CATEGORIES, CATEGORY_ICON_BY_NAME

app = QApplication.instance() or QApplication([])
app.setProperty('icon_style', 'illustrated')
colors = ['#29A6AA', '#7264FF', '#985CF3', '#EA596F', '#F2A549', '#3DA477', '#4295EF', '#B8A2E8']
out = root / 'mobile' / 'icons'
out.mkdir(exist_ok=True)
for index, color in enumerate(colors):
    sheet=QImage(720, 648, QImage.Format.Format_ARGB32_Premultiplied)
    sheet.fill(Qt.GlobalColor.transparent)
    for number, (key, _) in enumerate(ICON_CATALOG):
        image = QImage(72, 72, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_icon(painter, QRectF(4, 4, 64, 64), key, color)
        painter.end()
        painter=QPainter(sheet); painter.drawImage((number%10)*72,(number//10)*72,image); painter.end()
        previous=out/f'{key}-{index}.png'
        if previous.is_file() and previous.resolve().parent==out.resolve(): previous.unlink()
    if not sheet.save(str(out/f'catalog-{index}.png')): raise RuntimeError('No se pudo exportar catálogo')
categories = []
for kind, groups in [('expense', EXPENSE_CATEGORIES), ('income', INCOME_CATEGORIES)]:
    for index, (name, children) in enumerate(groups.items()):
        parent = f'{kind}-{index}'
        color = colors[index % len(colors)]
        for number, label in enumerate([name, *children]):
            categories.append(dict(id=parent if number == 0 else f'{parent}-{number}', name=label, kind=kind,
                parent='' if number == 0 else parent, color=color, icon=CATEGORY_ICON_BY_NAME.get(label, 'star')))
(root/'mobile'/'design.mjs').write_text('export const palette='+json.dumps(colors)+';\nexport const iconCatalog='+json.dumps(ICON_CATALOG, ensure_ascii=False)+';\nexport const desktopCategories='+json.dumps(categories, ensure_ascii=False)+';\n', encoding='utf-8')
print(f'{len(ICON_CATALOG)} iconos de escritorio × {len(colors)} colores')
