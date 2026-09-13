from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


class PackageStructureTests(unittest.TestCase):
    """Reglas estáticas mínimas para evitar imports relativos inválidos."""

    def test_top_level_app_modules_do_not_import_beyond_app_package(self) -> None:
        violations: list[str] = []
        for path in APP.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level > 1:
                    violations.append(
                        f"{path.name}:{node.lineno} usa {'.' * node.level}{node.module or ''}"
                    )
        self.assertEqual(violations, [], "\n".join(violations))

    def test_shared_date_picker_lives_outside_pages(self) -> None:
        self.assertTrue((APP / "date_picker.py").exists())
        dialog_sources = "\n".join(
            path.read_text(encoding="utf-8") for path in (APP / "dialog_modules").glob("*.py")
        )
        self.assertIn("from ..date_picker import WorkDateEdit", dialog_sources)
        self.assertNotIn("pages.work_date_picker", dialog_sources)


if __name__ == "__main__":
    unittest.main()
