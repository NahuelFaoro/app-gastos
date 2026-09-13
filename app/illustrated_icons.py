"""Variante ilustrada vectorial: colores pastel, contornos y detalles amables."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

PASTELS = ("#B7A2E8", "#FFADC1", "#83C6FA", "#FFD88A", "#7CDBBD")


def draw_illustrated(p, rect, key, line_name, qta):
    p.save()
    size = min(rect.width(), rect.height())
    p.translate(rect.center().x() - size / 2, rect.center().y() - size / 2)
    p.scale(size / 24, size / 24)
    ink = QColor("#202034")
    pastel = QColor(PASTELS[sum(map(ord, key)) % len(PASTELS)])
    p.setPen(QPen(ink, 1.15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    def box(x, y, w, h, color, radius=1.5):
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    def face(x, y):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        for offset in (-2, 2):
            p.drawEllipse(QRectF(x + offset - .55, y - .6, 1.1, 1.3))
        p.setBrush(QColor("#FF9EB9"))
        for offset in (-3.3, 3.3):
            p.drawEllipse(QRectF(x + offset - .7, y + .7, 1.4, .9))
        p.setPen(QPen(ink, .7))
        p.drawArc(QRectF(x - 1, y + .2, 2, 1.6), 180 * 16, 180 * 16)

    if key == "dumbbell":
        box(3, 10, 18, 4, "#B7A2E8")
        box(2, 6, 4, 12, "#9695D4")
        box(6, 4, 3, 16, "#B7A2E8")
        box(15, 4, 3, 16, "#B7A2E8")
        box(18, 6, 4, 12, "#9695D4")
        face(12, 11)
    elif key in ("wallet", "card", "money"):
        box(2, 5, 20, 15, "#B7A2E8", 3)
        box(2, 7, 20, 3, "#FFD88A", .5)
        face(11, 14)
        box(17, 12, 5, 5, "#83C6FA")
    elif key == "phone":
        box(5, 1, 14, 22, "#9695D4", 3)
        box(7, 5, 10, 13, "#83C6FA")
        face(12, 11)
        box(10, 20, 4, 1, "#FFD88A", .5)
    else:
        # La misma geometría de relleno y contorno mantiene el símbolo reconocible.
        fill_name = line_name.removesuffix("-line") + "-fill"
        fill = qta.icon(fill_name, color=pastel.name()).pixmap(96, 96)
        outline = qta.icon(line_name, color=ink.name()).pixmap(96, 96)
        p.drawPixmap(QRectF(1, 1, 22, 22), fill, QRectF(fill.rect()))
        p.drawPixmap(QRectF(1, 1, 22, 22), outline, QRectF(outline.rect()))
        if key in ("cloud", "bag", "coffee", "shirt", "water", "pill", "package", "basket"):
            face(12, 13)
    p.restore()
