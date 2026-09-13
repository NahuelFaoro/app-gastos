from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, QRegularExpression, QTimer, QSize, Signal, QMargins
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPalette, QRegularExpressionValidator, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QMenu, QSizePolicy, QStackedLayout, QToolTip, QVBoxLayout, QWidget
)


try:
    from PySide6.QtCharts import QChart, QChartView, QPieSeries
except Exception:
    QChart = QChartView = QPieSeries = None

from .constants import NEGATIVE
from .icons import ICON_LABELS, draw_icon, normalize_icon
from .utils import human_date, money


class SlideSwitch(QAbstractButton):
    """Switch visual reutilizable para preferencias booleanas.

    Usa el mismo lenguaje visual que Modo privacidad y evita que cada pantalla
    invente su propio checkbox para opciones importantes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            accent = self.palette().color(QPalette.ColorRole.Highlight)
            inactive = self.palette().color(QPalette.ColorRole.Midlight)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent if self.isChecked() else inactive)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            knob = 20.0
            x = r.right() - knob - 2 if self.isChecked() else r.left() + 2
            p.setBrush(QColor(0, 0, 0, 45))
            p.drawEllipse(QRectF(x, r.top() + 3, knob, knob))
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(x, r.top() + 2, knob, knob))
        finally:
            p.end()


class MoneyEdit(QLineEdit):
    """Campo monetario pensado para carga rápida.

    Desde v0.6 aplica separadores de miles *mientras* se escribe, sin mover el
    valor a cero al cambiar de foco. Ejemplo: 20000 -> 20.000 -> 200.000.

    La coma se usa como separador decimal. Los puntos se tratan como
    separadores de miles para que el formato argentino sea natural.
    """
    valueChanged = Signal(float)

    def __init__(self, symbol="$", allow_negative=False, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.allow_negative = allow_negative
        sign = r"-?" if allow_negative else ""
        self.setValidator(QRegularExpressionValidator(
            QRegularExpression(rf"^{sign}[\d\.,]*$"), self
        ))
        self.setPlaceholderText("0")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumHeight(54)
        self.setObjectName("MoneyEdit")
        self._value = 0.0
        self._formatting = False
        self.textEdited.connect(self._on_text_edited)

    @staticmethod
    def _group_digits(digits: str) -> str:
        if not digits:
            return ""
        # Conservamos un cero si el usuario todavía está empezando a escribir,
        # pero evitamos cadenas como 000.000.
        digits = digits.lstrip("0") or "0"
        groups = []
        while digits:
            groups.append(digits[-3:])
            digits = digits[:-3]
        return ".".join(reversed(groups))

    def _format_live(self, text: str) -> str:
        text = (text or "").strip().replace(" ", "")
        if not text:
            return ""

        negative = self.allow_negative and text.startswith("-")
        text = text.lstrip("-")

        # La coma es el separador decimal visible. Los puntos se eliminan porque
        # son separadores de miles generados por este mismo control.
        if "," in text:
            integer_part, decimal_part = text.split(",", 1)
            had_decimal_separator = True
        else:
            integer_part, decimal_part = text, ""
            had_decimal_separator = False

        integer_digits = "".join(ch for ch in integer_part if ch.isdigit())
        decimal_digits = "".join(ch for ch in decimal_part if ch.isdigit())[:2]

        grouped = self._group_digits(integer_digits)
        if had_decimal_separator:
            grouped += "," + decimal_digits
        if negative and grouped:
            grouped = "-" + grouped
        return grouped

    def _parse_current(self, text: str | None = None) -> float:
        text = self.text() if text is None else text
        cleaned = (text or "").strip().replace(".", "").replace(",", ".")
        if cleaned in {"", "-", ".", "-."}:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _restore_cursor_by_digits_right(self, formatted: str, digits_right: int):
        if digits_right <= 0:
            self.setCursorPosition(len(formatted))
            return
        seen = 0
        pos = len(formatted)
        while pos > 0:
            pos -= 1
            if formatted[pos].isdigit():
                seen += 1
                if seen >= digits_right:
                    break
        self.setCursorPosition(pos)

    def _on_text_edited(self, text: str):
        if self._formatting:
            return

        cursor = self.cursorPosition()
        digits_right = sum(ch.isdigit() for ch in text[cursor:])
        formatted = self._format_live(text)

        self._formatting = True
        try:
            if formatted != text:
                self.setText(formatted)
                self._restore_cursor_by_digits_right(formatted, digits_right)
            self._value = self._parse_current(formatted)
        finally:
            self._formatting = False
        self.valueChanged.emit(self._value)

    def value(self) -> float:
        self._value = self._parse_current()
        return float(self._value)

    def setValue(self, value: float):
        self._value = float(value or 0)
        if not self._value:
            self.setText("")
            return
        negative = self._value < 0
        value = abs(self._value)
        integer = int(value)
        decimals = round((value - integer) * 100)
        text = self._group_digits(str(integer))
        if decimals:
            text += f",{decimals:02d}"
        if negative:
            text = "-" + text
        self.setText(text)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event):
        # Reafirmamos valor y formato, pero nunca lo recalculamos a partir de un
        # texto vacío accidental: el textEdited ya lo fue guardando tecla a tecla.
        current = self._parse_current()
        self._value = current
        if self.text():
            self.setText(self._format_live(self.text()))
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        first_focus = not self.hasFocus()
        super().mousePressEvent(event)
        if first_focus:
            QTimer.singleShot(0, self.selectAll)


class IconBadge(QWidget):
    """Badge de contorno con soporte opcional para dos colores.

    ``secondary_color`` agrega un acento lateral. Se usa
    para categorías jerárquicas como ``Moto / GLH`` sin cambiar el ícono.
    """
    def __init__(self, icon="other", color="#4CCFA9", size=42, parent=None, secondary_color=None):
        super().__init__(parent)
        self.icon = normalize_icon(icon)
        self.color = QColor(color)
        self.secondary_color = QColor(secondary_color) if secondary_color else None
        self.badge_size = size
        self.setFixedSize(size, size)

    def set_icon(self, icon, color=None, secondary_color=None):
        self.icon = normalize_icon(icon)
        if color:
            self.color = QColor(color)
        self.secondary_color = QColor(secondary_color) if secondary_color else None
        self.update()

    def _icon_foreground(self, color: QColor) -> QColor:
        # blanco para la mayoría de acentos; oscuro para tonos muy claros
        luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        return QColor("#0B1320") if luminance > 205 else QColor("#FFFFFF")

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            color = QColor(self.color)
            if color.saturation() < 40:
                color = color.lighter(108)

            # Superficie tenue, sin sombras ni anillos brillantes.
            fill = QColor(color)
            fill.setAlpha(24)
            edge = QColor(color)
            edge.setAlpha(55)
            radius = self.badge_size * 0.27
            p.setPen(QPen(edge, 1))
            p.setBrush(fill)
            p.drawRoundedRect(rect, radius, radius)
            if self.secondary_color and self.secondary_color.isValid():
                # Acento lateral conserva el segundo color sin dividir el símbolo.
                p.setPen(QPen(self.secondary_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(rect.right() - 3, rect.top() + radius),
                           QPointF(rect.right() - 3, rect.bottom() - radius))
            foreground = QColor(color)
            background = self.palette().color(QPalette.ColorRole.Window)
            if background.lightness() < 128 and foreground.lightness() < 110:
                foreground = foreground.lighter(180)
            elif background.lightness() >= 128 and foreground.lightness() > 145:
                foreground = foreground.darker(170)
            icon_margin = max(5.0, self.badge_size * 0.18)
            draw_icon(p, rect.adjusted(icon_margin, icon_margin, -icon_margin, -icon_margin), self.icon, foreground, 1.7)
        finally:
            p.end()


class CategorySelectButton(QAbstractButton):
    def __init__(self, placeholder="Elegir categoría", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.category_id = None
        self.category_data = None
        self.setObjectName("CategorySelect")
        self.setMinimumHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_category(self, category):
        self.category_data = category; self.category_id = category.get("id") if category else None; self.update()

    def clear_category(self): self.set_category(None)
    def sizeHint(self): return QSize(420, 78)

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            pal = self.palette(); panel = pal.color(QPalette.ColorRole.AlternateBase); text = pal.color(QPalette.ColorRole.Text)
            muted = pal.color(QPalette.ColorRole.Mid)
            border = pal.color(QPalette.ColorRole.Midlight)
            if self.underMouse(): border = QColor("#72E0C2")
            p.setBrush(panel)
            p.setPen(QPen(border, 1))
            p.drawRoundedRect(rect, 18, 18)

            if not self.category_data:
                color = QColor("#72E0C2")
                secondary = None
                icon = "plus"
                name = self.placeholder
                parent = "Elegí una categoría y una subcategoría"
                eyebrow = "Categoría"
            else:
                c = self.category_data
                color = QColor(c.get("effective_color") or c.get("color") or "#72E0C2")
                secondary = QColor(c.get("secondary_color")) if c.get("secondary_color") else None
                icon = normalize_icon(c.get("effective_icon") or c.get("icon"), c.get("name"))
                name = c.get("name") or self.placeholder
                parent = c.get("path_parent") or c.get("parent_name") or ""
                eyebrow = parent or "Categoría"
            accent = QColor(color); accent.setAlpha(125)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(QRectF(rect.left()+10, rect.top()+12, 4, rect.height()-24), 2, 2)

            bubble = QRectF(rect.left()+24, rect.center().y()-18, 36, 36)
            soft = QColor(color); soft.setAlpha(18)
            edge = QColor(color); edge.setAlpha(58)
            p.setPen(QPen(edge, 1))
            p.setBrush(soft)
            p.drawRoundedRect(bubble, 12, 12)
            if secondary and secondary.isValid():
                p.save()
                from PySide6.QtGui import QPainterPath
                clip = QPainterPath(); clip.addRoundedRect(bubble, 12, 12)
                p.setClipPath(clip)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(secondary)
                p.drawRect(QRectF(bubble.center().x(), bubble.top(), bubble.width()/2, bubble.height()))
                p.restore()
            draw_icon(p, bubble.adjusted(9, 9, -9, -9), icon, QColor("#FFFFFF") if secondary else color, 1.65)

            title_rect = QRectF(rect.left()+74, rect.top()+14, rect.width()-126, 18)
            name_rect = QRectF(rect.left()+74, rect.top()+29, rect.width()-126, 24)
            hint_rect = QRectF(rect.left()+74, rect.bottom()-22, rect.width()-126, 14)

            f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f); p.setPen(muted)
            p.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter, eyebrow)

            f.setPointSize(11); f.setBold(True); p.setFont(f); p.setPen(text)
            p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter, name)

            if parent:
                f.setPointSize(8); f.setBold(False); p.setFont(f); p.setPen(muted)
                p.drawText(hint_rect, Qt.AlignmentFlag.AlignVCenter, f"{parent} · tocá para cambiar")
            else:
                f.setPointSize(8); f.setBold(False); p.setFont(f); p.setPen(muted)
                p.drawText(hint_rect, Qt.AlignmentFlag.AlignVCenter, parent)

            chevron_pen = QPen(muted, 1.7)
            chevron_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(chevron_pen)
            cx = rect.right()-24; cy = rect.center().y()
            p.drawLine(QPointF(cx-4, cy-5), QPointF(cx+1, cy))
            p.drawLine(QPointF(cx+1, cy), QPointF(cx-4, cy+5))
        finally:
            p.end()


class CategoryTileButton(QAbstractButton):
    """Categoría visual con icono redondo tipo app móvil."""
    def __init__(self, category, show_context=False, parent=None):
        super().__init__(parent)
        self.category = category
        self.show_context = show_context
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumSize(104, 90)
        self.setMaximumHeight(94)
        self.setToolTip(category.get("label") or category.get("name") or "")

    def sizeHint(self):
        return QSize(110, 92)

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
            pal = self.palette()
            text = pal.color(QPalette.ColorRole.Text)
            muted = pal.color(QPalette.ColorRole.Mid)
            color = QColor(self.category.get("effective_color") or self.category.get("color") or "#4CCFA9")
            secondary = QColor(self.category.get("secondary_color")) if self.category.get("secondary_color") else None

            if self.isChecked() or self.underMouse():
                halo = QColor(color)
                halo.setAlpha(22 if self.isChecked() else 12)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawRoundedRect(rect, 18, 18)

            bubble_size = 44
            bubble = QRectF(rect.center().x()-bubble_size/2, rect.top()+6, bubble_size, bubble_size)
            bubble_shadow = QRectF(bubble.left(), bubble.top()+2, bubble.width(), bubble.height())
            shadow = QColor(color); shadow.setAlpha(45)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(shadow); p.drawEllipse(bubble_shadow)
            p.setBrush(color); p.setPen(QPen(QColor(255,255,255,32), 1)); p.drawEllipse(bubble)
            if secondary and secondary.isValid():
                p.save()
                from PySide6.QtGui import QPainterPath
                clip = QPainterPath(); clip.addEllipse(bubble)
                p.setClipPath(clip); p.setPen(Qt.PenStyle.NoPen); p.setBrush(secondary)
                p.drawRect(QRectF(bubble.center().x(), bubble.top(), bubble.width()/2, bubble.height()))
                p.restore()
                p.setPen(QPen(QColor(255,255,255,32), 1)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(bubble)
            draw_icon(p, bubble.adjusted(10,10,-10,-10), self.category.get("effective_icon") or self.category.get("icon"), QColor("#FFFFFF"), 1.8)

            f = p.font(); f.setPointSize(9); f.setBold(True); p.setFont(f); p.setPen(text)
            name = self.category.get("name") or ""
            p.drawText(QRectF(rect.left()+5, rect.top()+54, rect.width()-10, 23), Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop|Qt.TextFlag.TextWordWrap, name)

            if self.show_context:
                context = self.category.get("path_parent") or self.category.get("parent_name") or ""
                if context:
                    f.setPointSize(7); f.setBold(False); p.setFont(f); p.setPen(muted)
                    fm = QFontMetrics(f); context = fm.elidedText(context, Qt.TextElideMode.ElideRight, int(rect.width()-16))
                    p.drawText(QRectF(rect.left()+8, rect.bottom()-16, rect.width()-16, 13), Qt.AlignmentFlag.AlignCenter, context)
        finally:
            p.end()


class CategoryChipButton(QAbstractButton):
    def __init__(self, category, parent=None):
        super().__init__(parent)
        self.category = category
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setMinimumWidth(96)

    def sizeHint(self):
        return QSize(126, 34)

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            pal = self.palette()
            text = pal.color(QPalette.ColorRole.Text)
            muted = pal.color(QPalette.ColorRole.Mid)
            border = pal.color(QPalette.ColorRole.Midlight)
            color = QColor(self.category.get("effective_color") or self.category.get("color") or "#4CCFA9")
            bg = pal.color(QPalette.ColorRole.AlternateBase)
            if self.underMouse():
                hover = QColor(color); hover.setAlpha(10)
                p.setBrush(hover)
                p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 70), 1))
            else:
                p.setBrush(bg)
                p.setPen(QPen(border, 1))
            p.drawRoundedRect(r, 17, 17)

            badge = QRectF(r.left()+8, r.center().y()-9, 18, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(badge)
            draw_icon(p, badge.adjusted(4.3, 4.3, -4.3, -4.3), self.category.get("effective_icon") or self.category.get("icon"), QColor("#FFFFFF"), 1.85)

            f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)
            p.setPen(text if self.underMouse() else muted)
            fm = QFontMetrics(f)
            name = fm.elidedText(self.category.get("name") or "", Qt.TextElideMode.ElideRight, int(r.width()-40))
            p.drawText(QRectF(r.left()+31, r.top(), r.width()-35, r.height()), Qt.AlignmentFlag.AlignVCenter, name)
        finally:
            p.end()


class IconChoiceButton(QAbstractButton):
    def __init__(self, icon, label="", parent=None):
        super().__init__(parent)
        self.icon=normalize_icon(icon); self.label=label or ICON_LABELS.get(self.icon,self.icon)
        self.setCheckable(True); self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFixedSize(98,80); self.setToolTip(self.label)

    def paintEvent(self,event):
        p=QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing); r=QRectF(self.rect()).adjusted(1,1,-1,-1)
            text=self.palette().color(QPalette.ColorRole.Text); muted=self.palette().color(QPalette.ColorRole.Mid); accent=QColor("#4CCFA9")
            if self.isChecked() or self.underMouse():
                bg=QColor(accent); bg.setAlpha(24 if self.isChecked() else 10)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg); p.drawRoundedRect(r,16,16)
            circle=QRectF(r.center().x()-21,r.top()+7,42,42)
            circle_color = QColor(accent) if self.isChecked() else QColor(accent.red(),accent.green(),accent.blue(),210)
            p.setBrush(circle_color); p.setPen(QPen(QColor(255,255,255,30), 1)); p.drawEllipse(circle)
            draw_icon(p,circle.adjusted(10,10,-10,-10),self.icon,QColor("#FFFFFF"),2.0)
            f=p.font(); f.setPointSize(7); f.setBold(self.isChecked()); p.setFont(f); p.setPen(text if self.isChecked() else muted)
            fm=QFontMetrics(f); txt=fm.elidedText(self.label,Qt.TextElideMode.ElideRight,int(r.width()-8))
            p.drawText(QRectF(r.left()+4,r.top()+54,r.width()-8,18),Qt.AlignmentFlag.AlignCenter,txt)
        finally:
            p.end()


class TransactionRowWidget(QFrame):
    edit_requested = Signal(int)
    duplicate_requested = Signal(int)
    delete_requested = Signal(int)
    installments_requested = Signal(int)

    def __init__(self, tx, formatted_amount, parent=None, compact=False):
        super().__init__(parent)
        self.tx = tx
        self.tx_id = int(tx["id"])
        self.compact = compact
        self.setObjectName("TransactionRowFlat" if compact else "TransactionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para editar · clic derecho para más acciones")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(11)
        badge = IconBadge(
            tx.get("category_effective_icon", "other"),
            tx.get("category_effective_color", "#4CCFA9"),
            40,
            secondary_color=tx.get("category_secondary_color"),
        )
        root.addWidget(badge)

        info = QVBoxLayout(); info.setSpacing(2)
        title = QLabel(tx.get("display") or tx.get("category_display") or "Movimiento")
        title.setObjectName("TransactionTitle")
        info.addWidget(title)
        meta_parts = [human_date(tx["tx_date"]), tx.get("category_display") or ""]
        if tx.get("account_name"):
            meta_parts.append(tx["account_name"])
        if tx.get("installment_total") and int(tx.get("installment_total") or 0) > 1:
            meta_parts.append(f"Cuota {int(tx.get('installment_number') or 1)}/{int(tx.get('installment_total'))}")
        if tx.get("source") == "mercado_pago":
            meta_parts.append("Mercado Pago")
        meta = QLabel("  ·  ".join(x for x in meta_parts if x))
        meta.setObjectName("SmallMuted")
        info.addWidget(meta)
        root.addLayout(info, 1)

        amount = QLabel(formatted_amount)
        amount.setObjectName(
            "TransactionAmountPositive" if tx["kind"] == "income"
            else "TransactionAmountNegative" if tx["kind"] == "expense"
            else "TransactionAmount"
        )
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(amount)

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.tx_id)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        edit = menu.addAction("Editar")
        installments = duplicate = delete = None
        if not self.compact:
            if self.tx.get("kind") == "expense":
                label = "Editar plan de cuotas" if self.tx.get("installment_plan_id") else "Configurar cuotas"
                installments = menu.addAction(label)
            duplicate = menu.addAction("Duplicar")
            menu.addSeparator()
            delete = menu.addAction("Eliminar")
        chosen = menu.exec(event.globalPos())
        if chosen == edit:
            self.edit_requested.emit(self.tx_id)
        elif installments is not None and chosen == installments:
            self.installments_requested.emit(self.tx_id)
        elif duplicate is not None and chosen == duplicate:
            self.duplicate_requested.emit(self.tx_id)
        elif delete is not None and chosen == delete:
            self.delete_requested.emit(self.tx_id)


class AccountCard(QFrame):
    edit_requested = Signal(int)
    toggle_balance_requested = Signal(int, bool)
    delete_requested = Signal(int)
    statement_requested = Signal(int)
    payment_requested = Signal(int)

    def __init__(self, account, formatted_balance, formatted_opening, parent=None):
        super().__init__(parent)
        self.account = account
        self.account_id = int(account["id"])
        included = bool(account.get("include_in_balance", 1))
        self.included = included
        self.setObjectName("AccountCard" if included else "AccountCardExcluded")
        self.setFixedHeight(174)
        self.setMinimumWidth(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para editar · clic derecho para más acciones")

        root = QVBoxLayout(self)
        root.setContentsMargins(17, 14, 17, 15)
        root.setSpacing(8)

        accent_line = QFrame(); accent_line.setFixedHeight(3); accent_line.setObjectName("AccountAccent")
        accent_color = account.get("color") or "#4CCFA9"
        accent_line.setStyleSheet(f"background:{accent_color}; border:none; border-radius:1px;")
        root.addWidget(accent_line)

        top = QHBoxLayout(); top.setSpacing(10)
        type_name = account.get("type") or "Cuenta"
        icon_map = {"Tarjeta":"card", "Banco":"bank", "Billetera":"wallet", "Efectivo":"money", "Ahorro":"wallet", "Cuenta":"wallet"}
        top.addWidget(IconBadge(icon_map.get(type_name, "wallet"), account.get("color") or "#4CCFA9", 38))
        texts = QVBoxLayout(); texts.setSpacing(0)
        name = QLabel(account["name"]); name.setObjectName("AccountName")
        type_lbl = QLabel(type_name); type_lbl.setObjectName("AccountType")
        texts.addWidget(name); texts.addWidget(type_lbl)
        top.addLayout(texts, 1)
        root.addLayout(top)

        is_card = type_name == "Tarjeta"
        if is_card and account.get("card_debt_display") is not None:
            balance = QLabel(account.get("card_debt_display") or formatted_balance); balance.setObjectName("AccountBalance")
            root.addWidget(balance)
            if account.get("card_configured"):
                closing = account.get("closing_day") or "—"; due = account.get("due_day") or "—"
                detail_text = f"Cierra {closing} · vence {due}"
            else:
                detail_text = "Configurá cierre y vencimiento"
            if account.get("card_available_display"):
                detail_text += f" · disponible {account['card_available_display']}"
            detail = QLabel(detail_text); detail.setObjectName("SmallMuted"); root.addWidget(detail)
        else:
            balance = QLabel(formatted_balance); balance.setObjectName("AccountBalance"); root.addWidget(balance)
            opening = QLabel(f"Saldo inicial  {formatted_opening}"); opening.setObjectName("SmallMuted"); root.addWidget(opening)

        footer = QHBoxLayout()
        status = QLabel("Tarjeta" if is_card else ("Disponible" if included else "Separada"))
        status.setObjectName("BalanceExcludedChip" if is_card or not included else "BalanceIncludedChip")
        footer.addWidget(status); footer.addStretch()
        root.addLayout(footer)

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.account_id); event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        is_card = self.account.get("type") == "Tarjeta"
        statement = payment = None
        if is_card:
            statement = menu.addAction("Ver resumen")
            payment = menu.addAction("Registrar pago")
            menu.addSeparator()
        edit = menu.addAction("Editar cuenta")
        toggle = menu.addAction("Quitar del saldo disponible" if self.included else "Incluir en saldo disponible")
        menu.addSeparator()
        delete = menu.addAction("Eliminar cuenta")
        chosen = menu.exec(event.globalPos())
        if statement is not None and chosen == statement: self.statement_requested.emit(self.account_id)
        elif payment is not None and chosen == payment: self.payment_requested.emit(self.account_id)
        elif chosen == edit: self.edit_requested.emit(self.account_id)
        elif chosen == toggle: self.toggle_balance_requested.emit(self.account_id, not self.included)
        elif chosen == delete: self.delete_requested.emit(self.account_id)


class StatCard(QFrame):
    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(5)
        self.caption = QLabel(caption)
        self.caption.setObjectName("CardCaption")
        self.value = QLabel("$ 0")
        self.value.setObjectName("CardValue")
        self.hint = QLabel("")
        self.hint.setObjectName("SmallMuted")
        for label in (self.caption, self.value, self.hint):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
        layout.addWidget(self.caption)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)

    def set_value(self, value: str, hint: str = "", hint_tone: str | None = None):
        self.value.setText(value)
        self.hint.setText(hint)
        self.hint.setObjectName("Positive" if hint_tone == "positive" else "Negative" if hint_tone == "negative" else "SmallMuted")
        self.hint.style().unpolish(self.hint)
        self.hint.style().polish(self.hint)


class _FallbackDonutPaint(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data=[]; self.symbol="$"; self.hidden=False; self.empty_text="Sin gastos"
        self.setMinimumSize(190,190)

    def set_data(self, data, symbol="$", hidden=False, empty_text="Sin gastos"):
        self.data=list(data); self.symbol=symbol; self.hidden=hidden; self.empty_text=empty_text; self.update()

    def paintEvent(self, event):
        p=QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            side=max(0,min(self.width(),self.height()))
            if side<60: return
            rect=QRectF((self.width()-side)/2+20,(self.height()-side)/2+20,max(1,side-40),max(1,side-40))
            width=max(18.0,float(side)*0.10)
            total=sum(float(x[1] or 0) for x in self.data)
            muted=self.palette().color(QPalette.ColorRole.Mid); text=self.palette().color(QPalette.ColorRole.Text)
            if total<=0:
                pen=QPen(muted,width); pen.setCapStyle(Qt.PenCap.RoundCap); p.setPen(pen); p.drawArc(rect,0,360*16)
                p.setPen(text); p.drawText(rect,Qt.AlignmentFlag.AlignCenter,self.empty_text); return
            start=90*16
            for _,value,color in self.data:
                value=max(0.0,float(value or 0)); span=-int((value/total)*360*16)
                pen=QPen(QColor(color),width); pen.setCapStyle(Qt.PenCap.RoundCap); p.setPen(pen); p.drawArc(rect,start,span); start+=span
            p.setPen(text); f=p.font(); f.setPointSize(11); f.setBold(True); p.setFont(f)
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,money(total,self.symbol,self.hidden))
        finally:
            p.end()


class DonutChart(QWidget):
    """Donut nativo de Qt Charts con fallback.

    El painter manual de v0.18 podía quedar en blanco en algunos tamaños de
    ventana/GPUs de Windows. Qt Charts renderiza el pie en su propia escena y
    resulta mucho más estable. No usa animaciones para no sumar latencia.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data=[]; self.symbol="$"; self.hidden=False; self.empty_text="Sin gastos"
        self._slice_meta=[]
        self.setMinimumSize(210,210)
        if QChartView is None:
            self._fallback=_FallbackDonutPaint(self)
            layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(self._fallback)
            self._chart_view=None; self._series=None; self._center=None
            return

        self._fallback=None
        self._series=QPieSeries(); self._series.setHoleSize(0.62); self._series.setPieSize(0.86)
        chart=QChart(); chart.addSeries(self._series); chart.legend().hide(); chart.setBackgroundVisible(False); chart.setPlotAreaBackgroundVisible(False)
        chart.setMargins(QMargins(0,0,0,0))
        self._chart_view=QChartView(chart); self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing); self._chart_view.setStyleSheet("background:transparent;border:0;"); self._chart_view.setMouseTracking(True); self._chart_view.viewport().setMouseTracking(True)
        self._center=QLabel(); self._center.setAlignment(Qt.AlignmentFlag.AlignCenter); self._center.setObjectName("DonutCenterLabel"); self._center.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        overlay=QWidget(); overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        ol=QVBoxLayout(overlay); ol.setContentsMargins(60,60,60,60); ol.addStretch(); ol.addWidget(self._center); ol.addStretch()
        stack=QStackedLayout(self); stack.setContentsMargins(0,0,0,0); stack.setStackingMode(QStackedLayout.StackingMode.StackAll); stack.addWidget(self._chart_view); stack.addWidget(overlay)

    def set_data(self, data, symbol="$", hidden=False, empty_text="Sin gastos"):
        self.data=list(data); self.symbol=symbol; self.hidden=hidden; self.empty_text=empty_text
        if self._fallback is not None:
            self._fallback.set_data(data,symbol,hidden,empty_text); return
        self._series.clear(); self._slice_meta=[]
        total=sum(max(0.0,float(item[1] or 0)) for item in self.data)
        if total<=0:
            sl=self._series.append(empty_text,1.0); sl.setColor(self.palette().color(QPalette.ColorRole.Midlight)); sl.setBorderColor(Qt.GlobalColor.transparent)
            self._center.setText(empty_text); self._center.setObjectName("DonutCenterMuted")
        else:
            for label,value,color in self.data:
                value=max(0.0,float(value or 0))
                if value<=0: continue
                sl=self._series.append(str(label),value); sl.setColor(QColor(color)); sl.setBorderColor(Qt.GlobalColor.transparent)
                self._slice_meta.append((sl, str(label), value, total))
                sl.hovered.connect(lambda state, slice_obj=sl, label=str(label), value=value, total=total: self._on_slice_hovered(state, slice_obj, label, value, total))
            self._center.setText(money(total,symbol,hidden)); self._center.setObjectName("DonutCenterLabel")
        self._center.style().unpolish(self._center); self._center.style().polish(self._center)

    def _on_slice_hovered(self, state: bool, slice_obj, label: str, value: float, total: float):
        try:
            slice_obj.setExplodeDistanceFactor(0.045)
            slice_obj.setExploded(bool(state))
        except Exception:
            pass
        if not state:
            QToolTip.hideText(); return
        share = (value / total * 100.0) if total else 0.0
        tooltip = f"{label}\n{money(value, self.symbol, self.hidden)} · {share:.1f}%"
        QToolTip.showText(QCursor.pos(), tooltip, self._chart_view or self)


class CashflowChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.data=[]; self.labels=[]; self.setMinimumHeight(210)

    def set_data(self, data, labels):
        self.data=list(data); self.labels=list(labels); self.update()

    def paintEvent(self, event):
        # Todo se dibuja con QRectF/QPointF. Evita overloads ambiguos de QPainter
        # que en algunos builds de PySide6/Windows podían fallar al maximizar.
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            muted=self.palette().color(QPalette.ColorRole.Mid)
            grid=self.palette().color(QPalette.ColorRole.Midlight)
            left,right,top,bottom=42.0,12.0,16.0,30.0
            w=max(10.0,float(self.width())-left-right); h=max(10.0,float(self.height())-top-bottom)
            values=[]
            for item in self.data:
                values.extend([float(item.get("income",0) or 0), float(item.get("expense",0) or 0)])
            maxv=max(values+[1.0])
            p.setPen(QPen(grid,1))
            for i in range(4):
                y=top+h*i/3.0
                p.drawLine(QPointF(left,y),QPointF(left+w,y))
            n=max(1,len(self.data)); group_w=w/n; bar_w=min(18.0,group_w*.26)
            for i,item in enumerate(self.data):
                center=left+group_w*(i+.5)
                inc_h=max(0.0,h*float(item.get("income",0) or 0)/maxv)
                exp_h=max(0.0,h*float(item.get("expense",0) or 0)/maxv)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#4CCFA9"))
                p.drawRoundedRect(QRectF(center-bar_w-2,top+h-inc_h,bar_w,inc_h),4,4)
                p.setBrush(QColor(NEGATIVE)); p.drawRoundedRect(QRectF(center+2,top+h-exp_h,bar_w,exp_h),4,4)
                p.setPen(muted); label=self.labels[i] if i<len(self.labels) else ""
                p.drawText(QRectF(center-group_w/2,top+h+5,group_w,20),Qt.AlignmentFlag.AlignCenter,label)
        finally:
            p.end()


class BudgetProgress(QProgressBar):
    def __init__(self, value=0, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setValue(int(min(max(value, 0), 100)))
        if value >= 100:
            self.setStyleSheet(f"QProgressBar::chunk {{ background:{NEGATIVE}; border-radius:6px; }}")
        elif value >= 75:
            self.setStyleSheet("QProgressBar::chunk { background:#F0B45D; border-radius:6px; }")
