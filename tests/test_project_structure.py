from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    """Reglas de dependencia que protegen la arquitectura del proyecto."""

    def test_shared_dialogs_do_not_import_pages_package(self) -> None:
        """`app.dialogs` es infraestructura compartida y no debe depender de páginas.

        Si `app.dialogs` importa `app.pages`, el `__init__` de páginas carga vistas que
        vuelven a importar dialogs y se produce un ciclo durante el arranque.
        """
        source = (ROOT / "app" / "dialogs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        offending: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("pages") or module.startswith("app.pages"):
                    offending.append(module)
        self.assertEqual(offending, [], f"app.dialogs no debe importar páginas: {offending}")

    def test_date_picker_lives_in_shared_app_layer(self) -> None:
        self.assertTrue((ROOT / "app" / "date_picker.py").is_file())

    def test_removed_routing_feature_has_no_active_modules(self) -> None:
        self.assertFalse((ROOT / "app" / "services").exists())
        active_files = [
            ROOT / "app" / "pages" / "viajes.py",
            ROOT / "app" / "pages" / "viajes_dialogs.py",
            ROOT / "app" / "pages" / "viajes_widgets.py",
            ROOT / "app" / "pages" / "work_monthly.py",
            ROOT / "app" / "pages" / "settings.py",
        ]
        forbidden = ("OpenRouteService", "estimated_km", "KM estimados", "Calcular km faltantes")
        for path in active_files:
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source, f"{token!r} sigue activo en {path.name}")

    def test_personal_seed_is_not_packaged(self) -> None:
        # Una instalación nueva debe obtener datos sólo de la base del usuario;
        # no se distribuyen archivos de referencia con viajes/clientes reales.
        self.assertFalse((ROOT / "app" / "viajes_seed.json").exists())
        app_files = {path.name for path in (ROOT / "app").iterdir() if path.is_file()}
        self.assertFalse(any(name.endswith("_seed.json") for name in app_files))

    def test_start_bat_installs_ocr_by_default(self) -> None:
        core = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
        ocr = (ROOT / "requirements-ocr.txt").read_text(encoding="utf-8").casefold()
        start = (ROOT / "start.bat").read_text(encoding="utf-8").casefold()
        for package in ("rapidocr", "onnxruntime", "pymupdf"):
            self.assertNotIn(package, core)
            self.assertIn(package, ocr)
        self.assertIn('-r requirements.txt -r requirements-ocr.txt', start)
        self.assertIn('rapidocr, onnxruntime, fitz', start)

    def test_flow_layout_accepts_standard_add_widget_signature(self) -> None:
        """FlowLayout debe aceptar widget/stretch/alignment como layouts Qt comunes."""
        source = (ROOT / "app" / "layouts.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        flow = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FlowLayout"
        )
        method = next(
            node for node in flow.body
            if isinstance(node, ast.FunctionDef) and node.name == "addWidget"
        )
        argument_names = [arg.arg for arg in method.args.args]
        self.assertEqual(argument_names[:4], ["self", "widget", "stretch", "alignment"])



    def test_theme_stylesheet_fstring_uses_defined_names(self) -> None:
        """Evita NameError dentro del catálogo QSS de build_stylesheet."""
        source = (ROOT / "app" / "style_rules.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "build_stylesheet"
        )

        defined = {arg.arg for arg in func.args.args}
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                defined.add(node.id)

        qss_value = None
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "qss" for target in node.targets
            ):
                qss_value = node.value
                break
        self.assertIsNotNone(qss_value, "build_stylesheet debe construir la variable qss")

        referenced = {
            node.id for node in ast.walk(qss_value)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        undefined = sorted(referenced - defined)
        self.assertEqual(undefined, [], f"Variables no definidas en stylesheet: {undefined}")

    def test_modules_using_qt_namespace_import_qt(self) -> None:
        """Evita NameError como `Qt.AlignmentFlag` sin importar `Qt`."""
        violations: list[str] = []
        for path in (ROOT / "app").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            uses_qt = any(
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Qt"
                for node in ast.walk(tree)
            )
            if not uses_qt:
                continue
            imports_qt = any(
                isinstance(node, ast.ImportFrom)
                and node.module == "PySide6.QtCore"
                and any(alias.name == "Qt" for alias in node.names)
                for node in tree.body
            )
            if not imports_qt:
                violations.append(str(path.relative_to(ROOT)))
        self.assertEqual(violations, [], f"Módulos que usan Qt sin importarlo: {violations}")


if __name__ == "__main__":
    unittest.main()
