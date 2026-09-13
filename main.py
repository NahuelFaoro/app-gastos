from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from app.constants import APP_NAME
from app.db import Database


def migrate_legacy_database(db: Database):
    if db.path.exists():
        return
    here = Path(__file__).resolve().parent
    candidates = [here / "app_gastos.db"]
    for folder in here.parent.glob("AppGastos_v0.1*"):
        candidates.append(folder / "app_gastos.db")
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return
    legacy = max(existing, key=lambda p: p.stat().st_mtime)
    db.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, db.path)


def install_exception_logger(db: Database):
    """Evita que una excepción de un callback gráfico mate silenciosamente la app.

    Además deja el traceback en AppData/AppGastos/app_gastos_errors.log para poder
    diagnosticar fallas específicas de Windows/PySide sin depender de una captura.
    """
    log_path = db.path.parent / "app_gastos_errors.log"

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"\n\n===== {datetime.now().isoformat(timespec='seconds')} =====\n{text}")
        except Exception:
            pass
        print(text, file=sys.stderr)
        # Intencionalmente no hacemos sys.exit(): los errores de paintEvent/slots
        # no deberían cerrar toda la aplicación.

    sys.excepthook = hook


def _configure_qt_scale(_db: Database):
    """Deja que Qt use solo el escalado del sistema operativo.

    Desde v0.34 el zoom adicional de App Gastos se aplica en caliente mediante
    stylesheet y fuente global, por lo que ya no dependemos de reiniciar la app
    ni de modificar ``QT_SCALE_FACTOR`` por preferencia del usuario.
    """
    os.environ.setdefault("QT_SCALE_FACTOR", "1.00")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")


def main():
    # La base no depende de Qt, por lo que podemos leer preferencias de DPI
    # antes de crear QApplication. Esto hace que toda la interfaz escale de
    # forma coherente: texto, iconos, márgenes y controles.
    db = Database()
    install_exception_logger(db)
    migrate_legacy_database(db)
    db.initialize()
    _configure_qt_scale(db)

    # Importamos Qt recién después de fijar QT_SCALE_FACTOR. Esto es
    # importante en Windows: el factor debe existir antes de inicializar la
    # capa gráfica para que escalen también iconos, métricas y geometrías.
    from PySide6.QtWidgets import QApplication
    from app.main_window import MainWindow
    from app.theme import build_palette, build_stylesheet
    from app.qt_runtime import normalize_application_font

    app = QApplication(sys.argv)
    normalize_application_font(app)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    theme = db.get_setting("theme", "dark_mint")
    try:
        ui_scale = float(db.get_setting("ui_scale", "1.00") or 1.0)
    except (TypeError, ValueError):
        ui_scale = 1.0
    app.setPalette(build_palette(theme))
    app.setStyleSheet(build_stylesheet(theme, ui_scale))

    generated = db.process_due_recurring()
    generated_installments = db.process_due_installments()
    window = MainWindow(db, generated, generated_installments)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
