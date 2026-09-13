from __future__ import annotations

import math
from PySide6.QtWidgets import QApplication
from .illustrated_icons import draw_illustrated

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF


from .icon_data import ICON_CATALOG, ICON_KEYS, ICON_LABELS, LEGACY_ICON_MAP, normalize_icon

try:
    import qtawesome as qta
except Exception:  # fallback automático si el paquete no está disponible
    qta = None

# Remix Icon: familia de contornos uniforme, incluida en qtawesome.
QTA_ICON_MAP = {'wallet': 'ri.wallet-3-line',
 'bike': 'ri.motorbike-line',
 'fuel': 'ri.gas-station-line',
 'receipt': 'ri.bill-line',
 'wrench': 'ri.tools-line',
 'shield': 'ri.shield-check-line',
 'road': 'ri.road-map-line',
 'car': 'ri.car-line',
 'oil': 'ri.oil-line',
 'home': 'ri.home-4-line',
 'water': 'ri.drop-line',
 'wifi': 'ri.wifi-line',
 'broom': 'ri.brush-line',
 'flame': 'ri.fire-line',
 'bolt': 'ri.flashlight-line',
 'cart': 'ri.shopping-cart-2-line',
 'food': 'ri.restaurant-line',
 'play': 'ri.play-circle-line',
 'music': 'ri.music-2-line',
 'cloud': 'ri.cloud-line',
 'phone': 'ri.smartphone-line',
 'graduation': 'ri.book-read-line',
 'book': 'ri.book-open-line',
 'game': 'ri.gamepad-line',
 'film': 'ri.film-line',
 'drink': 'ri.goblet-line',
 'user': 'ri.user-line',
 'shirt': 'ri.t-shirt-line',
 'scissors': 'ri.scissors-line',
 'bag': 'ri.shopping-bag-line',
 'gift': 'ri.gift-line',
 'health': 'ri.heart-pulse-line',
 'pill': 'ri.capsule-line',
 'medical': 'ri.stethoscope-line',
 'lab': 'ri.flask-line',
 'briefcase': 'ri.briefcase-line',
 'users': 'ri.group-line',
 'laptop': 'ri.macbook-line',
 'tools': 'ri.tools-line',
 'bank': 'ri.bank-line',
 'card': 'ri.bank-card-line',
 'chart': 'ri.line-chart-line',
 'package': 'ri.archive-line',
 'star': 'ri.star-line',
 'pin': 'ri.map-pin-2-line',
 'store': 'ri.store-2-line',
 'basket': 'ri.shopping-basket-line',
 'soap': 'ri.hand-sanitizer-line',
 'tax': 'ri.file-list-3-line',
 'money': 'ri.money-dollar-box-line',
 'route': 'ri.route-line',
 'parking': 'ri.parking-box-line',
 'coffee': 'ri.cup-line',
 'plane': 'ri.plane-line',
 'paw': 'ri.bear-smile-line',
 'dumbbell': 'ri.run-line',
 'house-medical': 'ri.hospital-line',
 'brain': 'ri.mental-health-line',
 'tools-box': 'ri.hammer-line',
 'building': 'ri.building-2-line',
 'transfer': 'ri.arrow-left-right-line',
 'plus': 'ri.add-line',
 'other': 'ri.more-line'}
QTA_ICON_MAP.update({'piggy-bank': 'ri.safe-line', 'coins': 'ri.coins-line', 'safe': 'ri.safe-2-line', 'ticket': 'ph.ticket', 'handshake': 'ph.handshake', 'tree': 'ph.tree', 'dog': 'ph.dog', 'cat': 'ph.cat', 'baby': 'ph.baby', 'bed': 'ph.bed', 'camera': 'ph.camera', 'pizza': 'ph.pizza', 'cake': 'ph.cake', 'bus': 'ph.bus', 'train': 'ph.train', 'headphones': 'ph.headphones', 'paint': 'ph.paint-brush', 'plant': 'ri.plant-line', 'investment': 'ph.chart-line-up', 'brain': 'ph.brain', 'graduation': 'ph.graduation-cap'})



def _star_points(cx: float, cy: float, outer: float, inner: float, count: int = 5) -> QPolygonF:
    pts = []
    for i in range(count * 2):
        angle = -math.pi / 2 + i * math.pi / count
        radius = outer if i % 2 == 0 else inner
        pts.append(QPointF(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return QPolygonF(pts)


def _draw_qta_icon(p: QPainter, rect: QRectF, key: str, color: QColor) -> bool:
    """Intenta dibujar el icono con qtawesome y devuelve si tuvo éxito."""
    if qta is None or rect.width() <= 1 or rect.height() <= 1:
        return False
    try:
        awesome = qta.icon(QTA_ICON_MAP.get(key, QTA_ICON_MAP["other"]), color=color.name())
        size = max(8, int(min(rect.width(), rect.height())))
        pixmap = awesome.pixmap(size, size)
        target = QRectF(
            rect.center().x() - size / 2,
            rect.center().y() - size / 2,
            size,
            size,
        )
        p.drawPixmap(target.toRect(), pixmap)
        return True
    except Exception:
        return False


def illustrated_style() -> bool:
    app = QApplication.instance()
    return bool(app and app.property("icon_style") == "illustrated")


def draw_icon(
    p: QPainter,
    rect: QRectF,
    icon: str | None,
    color: QColor | str,
    stroke: float = 1.8,
) -> None:
    """Dibuja un ícono consistente con qtawesome y fallback vectorial local."""
    key = normalize_icon(icon)
    resolved_color = QColor(color)
    if illustrated_style() and qta is not None:
        draw_illustrated(p, rect, key, QTA_ICON_MAP.get(key, QTA_ICON_MAP["other"]), qta, resolved_color)
        return
    if _draw_qta_icon(p, rect, key, resolved_color):
        return
    _draw_fallback_icon(p, rect, key, resolved_color, stroke)


def _draw_fallback_icon(
    p: QPainter, rect: QRectF, key: str, color: QColor, stroke: float
) -> None:
    """Renderer vectorial local usado cuando qtawesome no está disponible."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    size = min(rect.width(), rect.height())
    x0 = rect.center().x() - size / 2
    y0 = rect.center().y() - size / 2
    p.translate(x0, y0)
    p.scale(size / 24.0, size / 24.0)
    pen = QPen(color, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    def line(x1, y1, x2, y2): p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    def ell(x, y, w, h): p.drawEllipse(QRectF(x, y, w, h))
    def rr(x, y, w, h, r=2): p.drawRoundedRect(QRectF(x, y, w, h), r, r)

    if key == "fuel":
        rr(5, 3, 9, 18, 1.5); rr(7, 6, 5, 5, 0.7); line(14, 7, 18, 9); line(18, 9, 18, 17); line(18, 17, 16.5, 17); line(6.5, 21, 13.5, 21)
    elif key == "bike":
        ell(3, 14, 6, 6); ell(15, 14, 6, 6); line(6,17,10,10); line(10,10,15,17); line(6,17,15,17); line(10,10,14,10); line(14,10,18,17); line(9,8,12,8)
    elif key == "receipt":
        path=QPainterPath(); path.moveTo(6,3); path.lineTo(18,3); path.lineTo(18,21); path.lineTo(16,19); path.lineTo(14,21); path.lineTo(12,19); path.lineTo(10,21); path.lineTo(8,19); path.lineTo(6,21); path.closeSubpath(); p.drawPath(path); line(9,8,15,8); line(9,12,15,12); line(9,16,13,16)
    elif key == "wrench":
        ell(4,4,6,6); line(8.5,8.5,18.5,18.5); ell(16.5,16.5,3.5,3.5); line(4.8,4.8,8.8,8.8)
    elif key == "shield":
        path=QPainterPath(); path.moveTo(12,3); path.lineTo(19,6); path.lineTo(18,13); path.cubicTo(17,17,14.5,19.5,12,21); path.cubicTo(9.5,19.5,7,17,6,13); path.lineTo(5,6); path.closeSubpath(); p.drawPath(path); line(9,12,11,14); line(11,14,15.5,9.5)
    elif key == "road":
        line(8,21,10,3); line(16,21,14,3); line(12,5,12,8); line(12,11,12,14); line(12,17,12,20)
    elif key == "car":
        path=QPainterPath(); path.moveTo(4,14); path.lineTo(6.5,9); path.lineTo(16.5,9); path.lineTo(20,14); path.lineTo(20,18); path.lineTo(4,18); path.closeSubpath(); p.drawPath(path); ell(6,16.5,3,3); ell(15,16.5,3,3); line(8,9,10,6); line(10,6,15,6); line(15,6,17,9)
    elif key == "oil":
        path=QPainterPath(); path.moveTo(12,3); path.cubicTo(10,7,6,10,6,14); path.cubicTo(6,18,8.8,21,12,21); path.cubicTo(15.2,21,18,18,18,14); path.cubicTo(18,10,14,7,12,3); p.drawPath(path); line(9,15,15,15)
    elif key == "home":
        path=QPainterPath(); path.moveTo(3.5,11); path.lineTo(12,4); path.lineTo(20.5,11); p.drawPath(path); rr(6,10,12,10,1); rr(10,14,4,6,0.5)
    elif key == "water":
        path=QPainterPath(); path.moveTo(12,3); path.cubicTo(9,8,6,11,6,15); path.cubicTo(6,18.5,8.7,21,12,21); path.cubicTo(15.3,21,18,18.5,18,15); path.cubicTo(18,11,15,8,12,3); p.drawPath(path)
    elif key == "wifi":
        p.drawArc(QRectF(3,5,18,14), 35*16, 110*16); p.drawArc(QRectF(7,9,10,8),35*16,110*16); p.setBrush(color); ell(11,17,2,2)
    elif key == "broom":
        line(15,3,10,15); path=QPainterPath(); path.moveTo(8,13); path.lineTo(14,16); path.lineTo(11,21); path.lineTo(5,18); path.closeSubpath(); p.drawPath(path); line(7,17,11,19)
    elif key == "flame":
        path=QPainterPath(); path.moveTo(13,3); path.cubicTo(14,7,19,9,18,15); path.cubicTo(18,19,15.5,21,12,21); path.cubicTo(8,21,6,18,6,15); path.cubicTo(6,11,9,9,10,6); path.cubicTo(11,9,14,11,13,14); p.drawPath(path)
    elif key == "bolt":
        p.setBrush(color); p.setPen(Qt.PenStyle.NoPen); poly=QPolygonF([QPointF(13,2),QPointF(6,13),QPointF(11,13),QPointF(9,22),QPointF(18,10),QPointF(13,10)]); p.drawPolygon(poly)
    elif key == "cart":
        line(3,5,6,5); line(6,5,8,15); line(8,15,18,15); line(18,15,20,8); line(7,8,19.5,8); ell(8,18,2,2); ell(16,18,2,2)
    elif key == "food":
        line(7,3,7,21); line(5,3,5,9); line(9,3,9,9); line(5,9,9,9); line(17,3,17,21); path=QPainterPath(); path.moveTo(17,3); path.cubicTo(21,5,21,11,17,12); p.drawPath(path)
    elif key == "play":
        rr(3,5,18,14,3); p.setBrush(color); p.setPen(Qt.PenStyle.NoPen); p.drawPolygon(QPolygonF([QPointF(10,9),QPointF(16,12),QPointF(10,15)]))
    elif key == "music":
        line(10,5,10,17); line(10,5,18,3); line(18,3,18,15); ell(6,15,4,4); ell(14,13,4,4)
    elif key == "cloud":
        path=QPainterPath(); path.moveTo(6,18); path.cubicTo(3,18,3,13,6.5,12); path.cubicTo(7,7,13,6,15,10); path.cubicTo(20,9,22,14,19,18); path.closeSubpath(); p.drawPath(path)
    elif key == "phone":
        rr(7,2.5,10,19,2); line(10,5,14,5); line(11,18.5,13,18.5)
    elif key == "graduation":
        p.drawPolygon(QPolygonF([QPointF(3,9),QPointF(12,4),QPointF(21,9),QPointF(12,14)])); line(7,12,7,16); path=QPainterPath(); path.moveTo(7,16); path.cubicTo(10,19,14,19,17,16); path.lineTo(17,12); p.drawPath(path); line(21,9,21,15)
    elif key == "book":
        path=QPainterPath(); path.moveTo(4,5); path.cubicTo(7,4,10,5,12,7); path.cubicTo(14,5,17,4,20,5); path.lineTo(20,19); path.cubicTo(17,18,14,19,12,21); path.cubicTo(10,19,7,18,4,19); path.closeSubpath(); p.drawPath(path); line(12,7,12,21)
    elif key == "game":
        path=QPainterPath(); path.moveTo(7,8); path.cubicTo(3,8,3,17,5,19); path.cubicTo(7,21,9,17,10,15); path.lineTo(14,15); path.cubicTo(15,17,17,21,19,19); path.cubicTo(21,17,21,8,17,8); path.closeSubpath(); p.drawPath(path); line(7,10,7,14); line(5,12,9,12); ell(15,10,1.5,1.5); ell(17.5,12.5,1.5,1.5)
    elif key == "film":
        rr(3,5,18,14,2); line(7,5,7,19); line(17,5,17,19); line(3,9,7,9); line(17,9,21,9); line(3,15,7,15); line(17,15,21,15)
    elif key == "drink":
        path=QPainterPath(); path.moveTo(6,4); path.lineTo(8,20); path.lineTo(16,20); path.lineTo(18,4); path.closeSubpath(); p.drawPath(path); line(7,9,17,9); line(18,7,21,5)
    elif key == "user":
        ell(8,3,8,8); path=QPainterPath(); path.moveTo(4,21); path.cubicTo(5,15,8,13,12,13); path.cubicTo(16,13,19,15,20,21); p.drawPath(path)
    elif key == "shirt":
        path=QPainterPath(); path.moveTo(8,4); path.lineTo(4,6); path.lineTo(2,11); path.lineTo(6,13); path.lineTo(7,10); path.lineTo(7,21); path.lineTo(17,21); path.lineTo(17,10); path.lineTo(18,13); path.lineTo(22,11); path.lineTo(20,6); path.lineTo(16,4); path.cubicTo(14,7,10,7,8,4); p.drawPath(path)
    elif key == "scissors":
        ell(3,4,6,6); ell(3,14,6,6); line(8,8,20,18); line(8,16,20,6)
    elif key == "bag":
        rr(5,7,14,14,2); path=QPainterPath(); path.moveTo(9,9); path.cubicTo(9,3,15,3,15,9); p.drawPath(path)
    elif key == "gift":
        rr(4,10,16,11,1); rr(3,7,18,4,1); line(12,7,12,21); path=QPainterPath(); path.moveTo(12,7); path.cubicTo(8,6,7,2,10,3); path.cubicTo(12,4,12,7,12,7); path.cubicTo(12,7,12,4,14,3); path.cubicTo(17,2,16,6,12,7); p.drawPath(path)
    elif key == "health":
        rr(4,4,16,16,4); line(12,8,12,16); line(8,12,16,12)
    elif key == "pill":
        p.save(); p.translate(12,12); p.rotate(-38); rr(-4,-9,8,18,4); line(-4,0,4,0); p.restore()
    elif key == "medical":
        path=QPainterPath(); path.moveTo(6,4); path.lineTo(6,10); path.cubicTo(6,15,12,15,12,10); path.lineTo(12,4); p.drawPath(path); line(9,15,9,17); path=QPainterPath(); path.moveTo(9,17); path.cubicTo(9,21,16,21,16,16); p.drawPath(path); ell(14.5,13,3,3)
    elif key == "lab":
        line(9,3,15,3); line(10,3,10,9); line(14,3,14,9); path=QPainterPath(); path.moveTo(10,9); path.lineTo(5,19); path.cubicTo(4,21,7,21,12,21); path.lineTo(19,21); path.cubicTo(20,21,20,20,19,18); path.lineTo(14,9); p.drawPath(path); line(7,16,17,16)
    elif key == "briefcase":
        rr(3,7,18,13,2); rr(9,4,6,3,1); line(3,12,21,12); rr(10,10.5,4,3,1)
    elif key == "users":
        ell(4,5,6,6); ell(14,5,6,6); path=QPainterPath(); path.moveTo(2,20); path.cubicTo(3,14,11,14,12,20); p.drawPath(path); path=QPainterPath(); path.moveTo(12,20); path.cubicTo(13,14,21,14,22,20); p.drawPath(path)
    elif key == "laptop":
        rr(4,4,16,11,1.5); path=QPainterPath(); path.moveTo(2,18); path.lineTo(22,18); path.lineTo(20,21); path.lineTo(4,21); path.closeSubpath(); p.drawPath(path)
    elif key == "tools":
        line(5,5,19,19); line(19,5,5,19); ell(3.5,3.5,4,4); ell(16.5,16.5,4,4)
    elif key == "bank":
        p.drawPolygon(QPolygonF([QPointF(3,8),QPointF(12,3),QPointF(21,8)])); line(4,9,20,9); line(6,9,6,18); line(10,9,10,18); line(14,9,14,18); line(18,9,18,18); line(3,19,21,19); line(2,21,22,21)
    elif key == "card":
        rr(3,5,18,14,2); line(3,9,21,9); line(6,15,10,15)
    elif key == "chart":
        line(4,20,4,4); line(4,20,21,20); path=QPainterPath(); path.moveTo(6,16); path.lineTo(10,12); path.lineTo(13,14); path.lineTo(19,7); p.drawPath(path); line(16,7,19,7); line(19,7,19,10)
    elif key == "package":
        p.drawPolygon(QPolygonF([QPointF(4,7),QPointF(12,3),QPointF(20,7),QPointF(12,11)])); line(4,7,4,17); line(20,7,20,17); line(4,17,12,21); line(20,17,12,21); line(12,11,12,21); line(8,5,16,9)
    elif key == "star":
        p.drawPolygon(_star_points(12,12,9,4.2))
    elif key == "pin":
        path=QPainterPath(); path.moveTo(12,22); path.cubicTo(9,17,5,13,5,9); path.cubicTo(5,4,8,2,12,2); path.cubicTo(16,2,19,4,19,9); path.cubicTo(19,13,15,17,12,22); p.drawPath(path); ell(9.5,6.5,5,5)
    elif key == "transfer":
        line(4,8,18,8); line(15,5,18,8); line(15,11,18,8); line(20,16,6,16); line(9,13,6,16); line(9,19,6,16)
    elif key == "plus":
        line(12,4,12,20); line(4,12,20,12)
    elif key == "wallet":
        rr(3,6,18,14,3); line(5,6,17,4); rr(14,10,8,6,2); ell(17,12,1,1)
    else:
        ell(4,4,16,16); p.setBrush(color); ell(8,11,2,2); ell(11,11,2,2); ell(14,11,2,2)

    p.restore()
