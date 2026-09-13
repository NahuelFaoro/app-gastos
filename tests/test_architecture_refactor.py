from __future__ import annotations

import ast
import unittest
from datetime import date
from pathlib import Path

from app.work_calendar import WORK_WEEK_DAYS, iter_week_days, week_end, week_start
from scripts.audit_architecture import audit


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


class ArchitectureRefactorTests(unittest.TestCase):
    """Contratos para que el proyecto no vuelva al acoplamiento de versiones previas."""

    def test_architecture_audit_has_no_errors(self) -> None:
        errors, _notes = audit()
        self.assertEqual(errors, [])

    def test_database_facade_is_small_and_domains_live_in_repositories(self) -> None:
        db_lines = (APP / "db.py").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(db_lines), 1000)
        expected = {
            "accounts.py", "analytics.py", "categories.py", "flex.py",
            "history.py", "import_queue.py", "installments.py", "planning.py",
            "transactions.py", "work_config.py", "work_tracking.py",
        }
        present = {p.name for p in (APP / "repositories").glob("*.py")}
        self.assertTrue(expected.issubset(present))
        self.assertTrue((APP / "schema.py").exists())

    def test_dialogs_are_domain_modules_behind_stable_facade(self) -> None:
        facade = (APP / "dialogs.py").read_text(encoding="utf-8")
        self.assertLess(len(facade.splitlines()), 30)
        self.assertIn("from .dialog_modules import *", facade)
        for name in ("accounts.py", "categories.py", "import_review.py", "planning.py", "transactions.py", "visual.py"):
            self.assertTrue((APP / "dialog_modules" / name).exists(), name)


    def test_theme_api_is_separate_from_declarative_rules(self) -> None:
        theme = (APP / "theme.py").read_text(encoding="utf-8")
        rules = (APP / "style_rules.py").read_text(encoding="utf-8")
        self.assertLess(len(theme.splitlines()), 100)
        self.assertIn("from .style_rules import build_stylesheet", theme)
        self.assertIn("QPushButton#DangerIconButton", rules)

    def test_week_calendar_is_single_source_of_truth(self) -> None:
        monday = date(2026, 9, 7)
        saturday = date(2026, 9, 12)
        self.assertEqual(WORK_WEEK_DAYS, 7)
        self.assertEqual(week_start(saturday), monday)
        self.assertEqual(week_end(monday), date(2026, 9, 13))
        self.assertEqual(len(list(iter_week_days(monday))), 7)

    def test_optional_heavy_dependencies_are_lazy_in_regular_pages(self) -> None:
        imports_source = (APP / "importers.py").read_text(encoding="utf-8")
        settings_source = (APP / "pages" / "settings.py").read_text(encoding="utf-8")
        inbox_source = (APP / "pages" / "imports.py").read_text(encoding="utf-8")
        # No deben volver a cargarse al importar el módulo/pantalla normal.
        top_imports = []
        for source in (imports_source, settings_source, inbox_source):
            tree = ast.parse(source)
            top_imports.extend(
                node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
            )
        rendered = "\n".join(ast.unparse(node) for node in top_imports)
        self.assertNotIn("openpyxl", rendered)
        # Los parsers de reportes pueden importarse; lo pesado que evitamos al
        # iniciar la UI es el cliente HTTP `app.mercadopago` (requests/API).
        self.assertNotIn("from ..mercadopago import", rendered)
        self.assertNotIn("from app.mercadopago import", rendered)

    def test_version_has_one_python_source_of_truth(self) -> None:
        package = (APP / "__init__.py").read_text(encoding="utf-8")
        start = (ROOT / "start.bat").read_text(encoding="utf-8")
        build = (ROOT / "scripts" / "windows" / "build_share.bat").read_text(encoding="utf-8")
        self.assertIn("__version__ = APP_VERSION", package)
        self.assertIn('findstr /b /c:"APP_VERSION ="', start)
        self.assertIn(".smoke_v%APP_VERSION%", start)
        self.assertIn("AppGastos_v%APP_VERSION%_LITE.zip", build)


if __name__ == "__main__":
    unittest.main()
