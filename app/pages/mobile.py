from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QBoxLayout, QCheckBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QUrl

from ..mobile_server import MobileServer, MobileServerError, ensure_mobile_credentials, rotate_pair_code
from ..layouts import responsive_mode
from .common import page_header


class MobileSyncPage(QWidget):
    data_changed = Signal()
    external_change = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.server = MobileServer(db, port=8765, on_change=self.external_change.emit)
        self._compact = False
        self.external_change.connect(self._mobile_data_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)
        root.addWidget(page_header("Móvil", "PWA sincronizada con App Gastos Desktop"))

        hero = QFrame(); hero.setObjectName("HeroCard")
        hl = QVBoxLayout(hero); hl.setContentsMargins(24, 22, 24, 22); hl.setSpacing(14)
        self.hero_top = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top = self.hero_top
        titles = QVBoxLayout(); titles.setSpacing(3)
        t = QLabel("App Gastos en tu teléfono"); t.setObjectName("HeroTitle")
        sub = QLabel("Misma base de datos · cambios visibles en PC y teléfono"); sub.setObjectName("Muted")
        titles.addWidget(t); titles.addWidget(sub)
        self.status = QLabel("● Detenido"); self.status.setObjectName("IntegrationStatus"); self.status.setProperty("state", "neutral")
        top.addLayout(titles, 1); top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
        hl.addLayout(top)

        self.url_label = QLabel("Activá el acceso móvil para obtener la dirección.")
        self.url_label.setObjectName("MobileUrl")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hl.addWidget(self.url_label)

        self.code_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.code_layout.setSpacing(10)
        code_row = self.code_layout
        code_box = QFrame(); code_box.setObjectName("InsetCard")
        cbl = QVBoxLayout(code_box); cbl.setContentsMargins(16, 12, 16, 12); cbl.setSpacing(2)
        ccap = QLabel("CÓDIGO DE VINCULACIÓN"); ccap.setObjectName("CardCaption")
        self.code_label = QLabel("— — — — — —"); self.code_label.setObjectName("PairCode")
        cbl.addWidget(ccap); cbl.addWidget(self.code_label)
        code_row.addWidget(code_box, 1)

        self.toggle_btn = QPushButton("Activar acceso móvil")
        self.toggle_btn.clicked.connect(self.toggle_server)
        code_row.addWidget(self.toggle_btn)
        hl.addLayout(code_row)

        self.actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.actions_layout.setSpacing(8)
        actions = self.actions_layout
        self.copy_btn = QPushButton("Copiar dirección"); self.copy_btn.setObjectName("SecondaryButton"); self.copy_btn.clicked.connect(self.copy_url)
        self.open_btn = QPushButton("Abrir en esta PC"); self.open_btn.setObjectName("SecondaryButton"); self.open_btn.clicked.connect(self.open_local)
        self.rotate_btn = QPushButton("Nuevo código"); self.rotate_btn.setObjectName("GhostButton"); self.rotate_btn.clicked.connect(self.rotate_code)
        actions.addWidget(self.copy_btn); actions.addWidget(self.open_btn); actions.addWidget(self.rotate_btn); actions.addStretch()
        hl.addLayout(actions)
        root.addWidget(hero)

        steps = QFrame(); steps.setObjectName("Card")
        sl = QVBoxLayout(steps); sl.setContentsMargins(22, 20, 22, 20); sl.setSpacing(12)
        st = QLabel("Cómo probarlo ahora"); st.setObjectName("SectionTitle"); sl.addWidget(st)
        for n, text in [
            ("1", "Conectá la PC y el teléfono a la misma red Wi‑Fi."),
            ("2", "Activá el acceso móvil y abrí la dirección que aparece arriba desde Safari o Chrome."),
            ("3", "Ingresá el código de 6 dígitos una sola vez. El teléfono queda vinculado."),
            ("4", "Usá movimientos, cuentas, cuotas, Flex, análisis, categorías, calendario, Por revisar y escáner desde el teléfono."),
        ]:
            row = QHBoxLayout(); badge = QLabel(n); badge.setObjectName("StepBadge"); badge.setAlignment(Qt.AlignmentFlag.AlignCenter); badge.setFixedSize(28, 28)
            label = QLabel(text); label.setObjectName("Muted"); label.setWordWrap(True)
            row.addWidget(badge); row.addWidget(label, 1); sl.addLayout(row)
        root.addWidget(steps)

        options = QFrame(); options.setObjectName("Card")
        ol = QVBoxLayout(options); ol.setContentsMargins(22, 19, 22, 19); ol.setSpacing(10)
        ot = QLabel("Sincronización local"); ot.setObjectName("SectionTitle"); ol.addWidget(ot)
        self.autostart = QCheckBox("Activar automáticamente al abrir App Gastos")
        self.autostart.setChecked(self.db.get_setting("mobile_server_autostart", "0") == "1")
        self.autostart.toggled.connect(lambda checked: self.db.set_setting("mobile_server_autostart", "1" if checked else "0"))
        ol.addWidget(self.autostart)
        note = QLabel(
            "La PWA ya cubre las funciones principales de uso diario y trabaja contra la misma base que Desktop. "
            "Por ahora la sincronización es local: la PC debe estar encendida y ambos dispositivos en la misma red. "
            "Usá una red de confianza. El acceso desde fuera de casa todavía no está disponible."
        )
        note.setObjectName("SmallMuted"); note.setWordWrap(True); ol.addWidget(note)
        root.addWidget(options)
        root.addStretch()

        self._refresh_state(); self._apply_responsive()
        if self.autostart.isChecked():
            QTimer.singleShot(650, self.start_server)

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        if compact == self._compact:
            return
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.hero_top.setDirection(direction)
        self.code_layout.setDirection(direction)
        self.actions_layout.setDirection(direction)
        margins = 14 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _mobile_data_changed(self):
        self.data_changed.emit()

    def _refresh_state(self):
        _, code = ensure_mobile_credentials(self.db)
        self.code_label.setText("  ".join(code))
        running = self.server.running
        if running:
            self.status.setText("● Activo")
            self.status.setProperty("state", "ok")
            self.url_label.setText(self.server.url)
            self.toggle_btn.setText("Detener acceso móvil")
        else:
            self.status.setText("● Detenido")
            self.status.setProperty("state", "neutral")
            self.url_label.setText("Activá el acceso móvil para obtener la dirección.")
            self.toggle_btn.setText("Activar acceso móvil")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.copy_btn.setEnabled(running); self.open_btn.setEnabled(running)

    def start_server(self):
        if self.server.running:
            self._refresh_state(); return
        try:
            self.server.start()
            self.db.set_setting("mobile_server_enabled", "1")
        except MobileServerError as exc:
            QMessageBox.warning(self, "Acceso móvil", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Acceso móvil", str(exc))
        self._refresh_state()

    def stop_server(self):
        if self.server.running:
            self.server.stop()
        self.db.set_setting("mobile_server_enabled", "0")
        self._refresh_state()

    def toggle_server(self):
        if self.server.running:
            self.stop_server()
        else:
            self.start_server()

    def copy_url(self):
        if not self.server.running:
            return
        QGuiApplication.clipboard().setText(self.server.url)
        self.window().statusBar().showMessage("Dirección móvil copiada", 2500) if hasattr(self.window(), "statusBar") else None

    def open_local(self):
        if self.server.running:
            QDesktopServices.openUrl(QUrl(self.server.url))

    def rotate_code(self):
        code = rotate_pair_code(self.db)
        self.code_label.setText("  ".join(code))
        QMessageBox.information(self, "Nuevo código", "Se generó un nuevo código para vincular teléfonos nuevos. Los dispositivos ya vinculados siguen funcionando.")

    def refresh(self):
        self._refresh_state()

    def shutdown(self):
        self.server.stop()
