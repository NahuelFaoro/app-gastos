from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsBlurEffect, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QScrollArea,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from .ui_helpers import ensure_page_viewport
from .constants import APP_VERSION
from .theme import build_palette, build_stylesheet
from .layouts import SIDEBAR_COMPACT_WIDTH
from .widgets import SlideSwitch
from .pages import (
    AccountsPage, CalendarPage, CategoriesPage, DashboardPage, ImportInboxPage,
    InstallmentsPage, MobileSyncPage, RecurringPage, SettingsPage, StatisticsPage, TransactionsPage, ToolsPage,
)


class MainWindow(QMainWindow):
    """Shell principal con navegación liviana y refresco perezoso."""

    PAGE_SPECS = (
        ("dashboard", "Dashboard", "mdi6.view-dashboard-outline", DashboardPage),
        ("transactions", "Movimientos", "mdi6.swap-horizontal", TransactionsPage),
        ("calendar", "Calendario", "mdi6.calendar-month-outline", CalendarPage),
        ("imports", "Por revisar", "mdi6.inbox-arrow-down-outline", ImportInboxPage),
        ("accounts", "Cuentas", "mdi6.wallet-outline", AccountsPage),
        ("installments", "Cuotas", "mdi6.credit-card-clock-outline", InstallmentsPage),
        ("stats", "Análisis", "mdi6.chart-donut", StatisticsPage),
        ("categories", "Categorías", "mdi6.shape-outline", CategoriesPage),
        ("recurring", "Recurrentes", "mdi6.autorenew", RecurringPage),
        ("tools", "Herramientas", "mdi6.tools", ToolsPage),
        ("mobile", "Móvil", "mdi6.cellphone-link", MobileSyncPage),
        ("settings", "Ajustes", "mdi6.tune-variant", SettingsPage),
    )

    SIDEBAR_SECTIONS = (
        ("PRINCIPAL", ("dashboard", "transactions", "calendar")),
        ("SEGUIMIENTO", ("imports", "accounts", "installments", "stats")),
        ("ORGANIZAR", ("categories", "recurring", "tools")),
        ("CONECTAR", ("mobile",)),
    )

    MUTATING_PAGE_KEYS = (
        "dashboard", "transactions", "calendar", "imports", "accounts",
        "installments", "categories", "recurring", "tools", "mobile", "settings",
    )

    def __init__(self, db, generated_recurring=0, generated_installments=0):
        super().__init__()
        self.db = db
        QApplication.instance().setProperty("icon_style", db.get_setting("icon_style", "illustrated"))
        self.setWindowTitle("App Gastos")
        self.resize(1480, 900)
        self.setMinimumSize(480, 360)
        area = self.screen().availableGeometry()
        self.resize(min(1480, int(area.width() * 0.94)), min(900, int(area.height() * 0.90)))

        self._compact_sidebar = False
        self.sidebar_captions: list[QLabel] = []
        self._privacy_effect = None
        app = QApplication.instance()
        self._base_font = QFont(app.font()) if app is not None else QFont()
        self._current_theme = self.db.get_setting("theme", "dark_mint")

        outer, sidebar_layout = self._build_shell()
        self._build_brand(sidebar_layout)
        self._build_quick_actions(sidebar_layout)
        self._create_pages()
        self._build_navigation(sidebar_layout)
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setWidget(self.sidebar)
        self.sidebar_scroll.setFixedWidth(self.sidebar.width() + 14)
        outer.addWidget(self.sidebar_scroll)
        outer.addWidget(self.stack, 1)

        self._connect_signals()
        self._install_shortcuts()
        self._finish_startup(generated_recurring, generated_installments)

    def _build_shell(self) -> tuple[QHBoxLayout, QVBoxLayout]:
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(236)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(17, 22, 17, 18)
        sidebar_layout.setSpacing(4)
        return outer, sidebar_layout

    def _build_brand(self, sidebar_layout: QVBoxLayout) -> None:
        self.brand_row = QWidget()
        row = QHBoxLayout(self.brand_row)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(10)

        mark = QFrame()
        mark.setObjectName("BrandMark")
        mark.setFixedSize(42, 42)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel("$")
        glyph.setObjectName("BrandMarkGlyph")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if qta is not None:
            try:
                glyph.setPixmap(qta.icon("mdi6.wallet-outline", color="#082018").pixmap(19, 19))
            except Exception:
                pass
        mark_layout.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.brand = QLabel("App Gastos")
        self.brand.setObjectName("Brand")
        self.brand_sub = QLabel("Finanzas personales")
        self.brand_sub.setObjectName("BrandSubtitle")
        texts.addWidget(self.brand)
        texts.addWidget(self.brand_sub)
        row.addWidget(mark)
        row.addLayout(texts, 1)
        sidebar_layout.addWidget(self.brand_row)
        sidebar_layout.addSpacing(14)

    def _build_quick_actions(self, sidebar_layout: QVBoxLayout) -> None:
        self.quick = QPushButton("  Nuevo movimiento")
        self.quick.setObjectName("QuickAdd")
        self.quick.setProperty("compact", False)
        self.quick.setToolTip("Nuevo movimiento")
        if qta is not None:
            try:
                self.quick.setIcon(qta.icon("mdi6.plus", color="#082018"))
                self.quick.setIconSize(QSize(14, 14))
            except Exception:
                pass
        self.quick.clicked.connect(self.open_new_transaction)
        sidebar_layout.addWidget(self.quick)

        self.privacy_box = QFrame()
        self.privacy_box.setObjectName("PrivacyBox")
        privacy_box_layout = QVBoxLayout(self.privacy_box)
        privacy_box_layout.setContentsMargins(10, 8, 10, 8)
        privacy_box_layout.setSpacing(4)
        privacy_row = QHBoxLayout()
        privacy_row.setContentsMargins(0, 0, 0, 0)
        privacy_row.setSpacing(8)
        self.privacy_label = QLabel("Modo privacidad")
        self.privacy_label.setObjectName("PrivacyLabel")
        self.privacy_switch = SlideSwitch()
        self.privacy_switch.setToolTip("Difumina la información financiera visible · Ctrl+Shift+P")
        privacy_row.addWidget(self.privacy_label, 1)
        privacy_row.addWidget(self.privacy_switch, 0)
        self.privacy_status = QLabel("Datos visibles")
        self.privacy_status.setObjectName("PrivacyStatus")
        privacy_box_layout.addLayout(privacy_row)
        privacy_box_layout.addWidget(self.privacy_status)
        self.privacy_switch.toggled.connect(self.set_privacy_mode)
        sidebar_layout.addWidget(self.privacy_box)
        sidebar_layout.addSpacing(10)

    def _create_pages(self) -> None:
        self.stack = QStackedWidget()
        self.pages: list[tuple[str, str, QWidget]] = []
        self.page_index: dict[str, int] = {}
        for key, label, icon_name, page_class in self.PAGE_SPECS:
            page = page_class(self.db)
            ensure_page_viewport(page)
            setattr(self, key, page)
            index = len(self.pages)
            self.page_index[key] = index
            self.pages.append((label, icon_name, page))
            self.stack.addWidget(page)

        self._all_pages = [item[2] for item in self.pages]
        self._dirty_pages: set[QWidget] = set()
        self.buttons: list[QPushButton | None] = [None] * len(self.pages)

    def _add_sidebar_section(self, layout: QVBoxLayout, text: str) -> None:
        caption = QLabel(text)
        caption.setObjectName("SidebarCaption")
        layout.addWidget(caption)
        self.sidebar_captions.append(caption)

    def _add_sidebar_button(self, layout: QVBoxLayout, key: str) -> None:
        index = self.page_index[key]
        label, icon_name, _ = self.pages[index]
        button = QPushButton(label)
        button.setObjectName("SidebarButton")
        button.setProperty("active", index == 0)
        button.setProperty("pageIcon", icon_name)
        button.setProperty("fullText", label)
        button.setProperty("compact", False)
        button.setToolTip(label)
        if qta is not None:
            try:
                button.setIcon(qta.icon(icon_name, color="#7F8B99"))
                button.setIconSize(QSize(15, 15))
            except Exception:
                pass
        button.clicked.connect(lambda checked=False, i=index: self.select_page(i))
        layout.addWidget(button)
        self.buttons[index] = button

    def _build_navigation(self, layout: QVBoxLayout) -> None:
        for section_index, (caption, keys) in enumerate(self.SIDEBAR_SECTIONS):
            if section_index:
                layout.addSpacing(5)
            self._add_sidebar_section(layout, caption)
            for key in keys:
                self._add_sidebar_button(layout, key)

        layout.addStretch()
        self._add_sidebar_button(layout, "settings")
        layout.addSpacing(8)
        self.footer = QLabel(f"v{APP_VERSION}  ·  local y privado")
        self.footer.setObjectName("SidebarFooter")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)

    def _connect_signals(self) -> None:
        for key in self.MUTATING_PAGE_KEYS:
            page = getattr(self, key)
            page.data_changed.connect(lambda p=page: self._on_data_changed(p))

        self.settings.theme_changed.connect(self.apply_theme)
        self.settings.ui_scale_changed.connect(self.apply_ui_scale)
        self.stats.open_transactions_requested.connect(self.open_transactions_from_analysis)
        self.transactions.back_requested.connect(self.return_to_analysis)

    def _install_shortcuts(self) -> None:
        self.shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self.shortcut_new.activated.connect(self.open_new_transaction)
        for attr, sequence, key in (
            ("shortcut_dashboard", "Ctrl+1", "dashboard"),
            ("shortcut_transactions", "Ctrl+2", "transactions"),
            ("shortcut_calendar", "Ctrl+3", "calendar"),
            ("shortcut_review", "Ctrl+4", "imports"),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(lambda k=key: self.select_page(self.page_index[k]))
            setattr(self, attr, shortcut)
        self.shortcut_privacy = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.shortcut_privacy.activated.connect(
            lambda: self.privacy_switch.setChecked(not self.privacy_switch.isChecked())
        )

    def _finish_startup(self, generated_recurring: int, generated_installments: int) -> None:
        self.stack.setCurrentIndex(self.page_index["dashboard"])
        self._apply_active_button(self.page_index["dashboard"])
        self._update_review_badge()
        self._set_sidebar_compact(self.width() < SIDEBAR_COMPACT_WIDTH)
        self.apply_theme(self._current_theme)

        notices = []
        if generated_recurring:
            notices.append(f"{generated_recurring} movimientos recurrentes")
        if generated_installments:
            notices.append(f"{generated_installments} cuotas de tarjeta")
        if notices:
            self.statusBar().showMessage("Se generaron: " + " · ".join(notices), 8000)
        if self.db.get_setting("mercadopago_auto_sync", "0") == "1":
            QTimer.singleShot(1200, self._auto_sync_mercadopago)

    def _current_scale(self) -> float:
        try:
            return max(0.8, min(2.0, float(self.db.get_setting("ui_scale", "1.00") or 1.0)))
        except (TypeError, ValueError):
            return 1.0

    def apply_theme(self, theme=None):
        """Aplica tema y zoom visual sin reiniciar la aplicación."""
        app = QApplication.instance()
        if app is None:
            return
        if theme is None:
            theme = self.db.get_setting("theme", self._current_theme)
        self._current_theme = theme
        scale = self._current_scale()
        self.setUpdatesEnabled(False)
        try:
            scaled_font = QFont(self._base_font)
            base_point_size = self._base_font.pointSizeF()
            if base_point_size <= 0:
                base_point_size = 10.0
            scaled_font.setPointSizeF(base_point_size * scale)
            app.setFont(scaled_font)
            app.setPalette(build_palette(theme))
            app.setStyleSheet(build_stylesheet(theme, scale))
            self._refresh_sidebar_icons()
            self._refresh_dialog_positions()
        finally:
            self.setUpdatesEnabled(True)
        self.update()

    def apply_ui_scale(self, _scale: float):
        self.apply_theme(self._current_theme)

    def _refresh_dialog_positions(self) -> None:
        for widget in QApplication.topLevelWidgets():
            if widget is self:
                continue
            if hasattr(widget, "recenter_to_parent"):
                try:
                    widget.recenter_to_parent()
                except Exception:
                    pass

    def _refresh_sidebar_icons(self):
        if qta is None: return
        for i, b in enumerate(self.buttons):
            if b is None: continue
            try:
                accent = QApplication.palette().color(QPalette.ColorRole.Highlight).name()
                color = accent if i == self.stack.currentIndex() else "#7F8B99"
                b.setIcon(qta.icon(b.property("pageIcon"), color=color))
            except Exception:
                pass

    def _apply_active_button(self, index: int):
        for i, b in enumerate(self.buttons):
            if b is None: continue
            b.setProperty("active", i == index); b.style().unpolish(b); b.style().polish(b)
        self._refresh_sidebar_icons()

    def _set_sidebar_compact(self, compact: bool):
        if compact == self._compact_sidebar:
            return
        self._compact_sidebar = compact
        self.sidebar.setFixedWidth(86 if compact else 236)
        self.sidebar_scroll.setFixedWidth(self.sidebar.width() + 14)
        self.brand.setVisible(not compact)
        self.brand_sub.setVisible(not compact)
        for cap in self.sidebar_captions:
            cap.setVisible(not compact)
        self.footer.setVisible(not compact)
        self.quick.setProperty("compact", compact)
        self.quick.setText("" if compact else "  Nuevo movimiento")
        self.quick.setFixedHeight(46 if compact else 50)
        self.quick.style().unpolish(self.quick); self.quick.style().polish(self.quick)
        self.privacy_label.setVisible(not compact)
        self.privacy_status.setVisible(not compact)
        self.privacy_box.setToolTip("Modo privacidad" if compact else "")
        for b in self.buttons:
            if b is None:
                continue
            b.setProperty("compact", compact)
            full = b.property("fullText") or b.text()
            b.setText("" if compact else str(full))
            b.style().unpolish(b); b.style().polish(b)

    def set_privacy_mode(self, enabled: bool):
        """Oculta información financiera sin cambiar preferencias permanentes.

        Además del enmascarado de importes, aplicamos un único blur al área de
        contenido. Es barato cuando está apagado (caso normal) y evita tener
        cientos de efectos gráficos independientes.
        """
        enabled = bool(enabled)
        self.db.set_privacy_mode(enabled)
        self.setUpdatesEnabled(False)
        try:
            if enabled:
                effect = QGraphicsBlurEffect(self.stack)
                effect.setBlurRadius(6.5)
                try:
                    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
                except Exception:
                    pass
                self._privacy_effect = effect
                self.stack.setGraphicsEffect(effect)
                self.privacy_status.setText("Datos protegidos")
                self.privacy_box.setProperty("active", True)
            else:
                self.stack.setGraphicsEffect(None)
                self._privacy_effect = None
                self.privacy_status.setText("Datos visibles")
                self.privacy_box.setProperty("active", False)
            self.privacy_box.style().unpolish(self.privacy_box); self.privacy_box.style().polish(self.privacy_box)
            # El formato monetario también se enmascara para cubrir diálogos o
            # widgets que no formen parte del stack difuminado.
            self._dirty_pages.update(self._all_pages)
            current = self.stack.currentWidget()
            if current is not None:
                self._refresh_page(current)
        finally:
            self.setUpdatesEnabled(True)
        self.update()

    def _refresh_page(self, page):
        if page is None: return
        if hasattr(page, "_load_filters"):
            try: page._load_filters()
            except Exception: pass
        if hasattr(page, "_load_accounts"):
            try: page._load_accounts()
            except Exception: pass
        if hasattr(page, "refresh"):
            page.refresh()
        self._dirty_pages.discard(page)

    def select_page(self, index):
        if index < 0 or index >= self.stack.count(): return
        changed = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index); self._apply_active_button(index)
        page = self.stack.currentWidget()
        if page in self._dirty_pages:
            self._refresh_page(page)
        elif changed and hasattr(page, "on_show"):
            try: page.on_show()
            except Exception: pass

    def _on_data_changed(self, source_page=None):
        for page in self._all_pages:
            if page is not source_page: self._dirty_pages.add(page)
        self._update_review_badge()
        current = self.stack.currentWidget()
        if current is not None and current is not source_page and current in self._dirty_pages:
            QTimer.singleShot(0, lambda p=current: self._refresh_page(p) if p is self.stack.currentWidget() else None)

    def refresh_all(self):
        self._on_data_changed(self.stack.currentWidget())

    def _update_review_badge(self):
        try:
            count = self.db.pending_import_count()
            review_index = self.page_index["imports"]
            button = self.buttons[review_index]
            if button is not None:
                button.setProperty("fullText", f"Por revisar   ·   {count}" if count else "Por revisar")
                if not self._compact_sidebar:
                    button.setText(button.property("fullText"))
                button.setToolTip(f"Por revisar: {count} pendientes" if count else "Por revisar")
        except Exception:
            pass

    def _auto_sync_mercadopago(self):
        from datetime import datetime, timedelta
        if self.db.get_setting("mercadopago_pending_task_id", ""):
            self.imports.sync_api(True); return
        last = self.db.get_setting("mercadopago_last_api_sync_iso", "")
        if last:
            try:
                if datetime.now() - datetime.fromisoformat(last) < timedelta(minutes=30): return
            except Exception:
                pass
        self.imports.sync_api(True)

    def open_transactions_from_analysis(self, payload):
        self.transactions.apply_analysis_filter(payload)
        self._dirty_pages.discard(self.transactions)
        self.select_page(1)

    def return_to_analysis(self):
        self.select_page(self.page_index["stats"])

    def open_new_transaction(self):
        self.transactions.add_transaction()
        self._dirty_pages.discard(self.transactions)
        self.select_page(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_sidebar_compact(self.width() < SIDEBAR_COMPACT_WIDTH)

    def closeEvent(self, event):
        try:
            self.mobile.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
