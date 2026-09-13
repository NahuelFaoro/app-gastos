from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UiStabilityRegressionTests(unittest.TestCase):
    """Contratos para bugs de geometría/scroll detectados en uso real."""

    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_flow_layout_does_not_drop_children_when_parent_is_hidden(self) -> None:
        src = self._read("app/layouts.py")
        self.assertIn("widget.isHidden()", src)
        self.assertNotIn("not widget.isVisible()", src)

    def test_tools_smoke_checks_grid_topology_not_provisional_geometry(self) -> None:
        src = self._read("scripts/check_app.py")
        self.assertIn("WA_DontShowOnScreen", src)
        self.assertIn('window.select_page(window.page_index["tools"])', src)
        self.assertIn("home_grid.getItemPosition", src)
        self.assertIn("assert flex_pos != viajes_pos", src)
        self.assertNotIn("intersects(viajes_geo)", src)
        self.assertNotIn("mapTo(host", src)


    def test_qt_font_is_normalized_before_ui_construction(self) -> None:
        helper = self._read("app/qt_runtime.py")
        main = self._read("main.py")
        smoke = self._read("scripts/check_app.py")
        self.assertIn("font.pointSizeF() <= 0", helper)
        self.assertIn("normalize_application_font(app)", main)
        self.assertIn("normalize_application_font(app)", smoke)

    def test_tools_home_uses_explicit_grid_and_second_layout_pass(self) -> None:
        src = self._read("app/pages/tools.py")
        self.assertIn("self.home_grid = QGridLayout", src)
        self.assertNotIn("self.home_flow = FlowLayout", src)
        self.assertIn("QTimer.singleShot(0", src)
        self.assertIn("def _arrange_home_tiles", src)
        self.assertIn("self.setMaximumHeight(118)", src)
        self.assertIn("target_width = min(1020 if mode == \"wide\" else 540, available)", src)
        self.assertIn("self.home_tiles_host.setFixedWidth(int(target_width))", src)
        self.assertIn("self.home_hint.setFixedWidth(int(target_width))", src)
        self.assertIn("QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed", src)

    def test_structural_category_refresh_preserves_scroll(self) -> None:
        src = self._read("app/pages/categories.py")
        self.assertIn("def refresh(self, preserve_scroll: bool = True)", src)
        self.assertIn("previous_scroll = scrollbar.value()", src)
        self.assertIn("scrollbar.setValue(min(value, scrollbar.maximum()))", src)
        self.assertIn("self.refresh(preserve_scroll=False)", src)


if __name__ == "__main__":
    unittest.main()
