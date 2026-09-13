from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RequestedUiContractsTests(unittest.TestCase):
    """Contratos visuales/estructurales que deben sobrevivir refactors internos."""

    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_analysis_has_real_wide_container_and_fixed_percent_axis(self) -> None:
        src = self._read("app/pages/statistics.py")
        self.assertIn("self.categories_host.setMaximumWidth(1500)", src)
        self.assertIn("self.categories_host.setFixedWidth(int(target))", src)
        self.assertIn("PERCENT_WIDTH = 96", src)
        self.assertIn("AMOUNT_WIDTH = 210", src)
        self.assertIn("grid.setColumnStretch(0, 1)", src)
        self.assertIn("grid.setColumnStretch(2, 1)", src)

    def test_travel_actions_use_non_wrapping_box_layout(self) -> None:
        src = self._read("app/pages/viajes.py")
        self.assertIn("self.actions_layout = QBoxLayout", src)
        self.assertGreaterEqual(src.count("setFixedSize(172, 44)"), 3)
        self.assertIn("self.search.setMinimumWidth(650)", src)
        self.assertNotIn("self.actions_layout = FlowLayout", src)
        self.assertIn("self.stats_layout = QGridLayout", src)
        self.assertIn("self.toolbar_outer.addWidget(self.filter_chip", src)

    def test_day_summary_does_not_use_flow_layout_for_primary_chips(self) -> None:
        src = self._read("app/pages/viajes_widgets.py")
        self.assertIn("self.chip_layout = QHBoxLayout(self.chip_host)", src)
        self.assertIn("mirror.setFixedWidth(16)", src)
        self.assertIn("self.setFixedHeight(112)", src)

    def test_category_parent_is_hierarchical_picker(self) -> None:
        src = self._read("app/dialog_modules/categories.py")
        self.assertIn("class CategoryParentPickerDialog", src)
        self.assertIn("class CategoryParentButton", src)
        self.assertNotIn('form.addRow("Dentro de", self.parent_combo)', src)

    def test_drag_move_is_single_update_and_tree_is_synchronously_rebuilt(self) -> None:
        repo = self._read("app/repositories/categories.py")
        self.assertIn('con.execute("UPDATE categories SET parent_id=? WHERE id=?"', repo)
        cat_src = self._read("app/pages/categories.py")
        self.assertIn("def _clear_groups_now", cat_src)
        self.assertIn("widget.setParent(None)", cat_src)
        self.assertIn("duplicate_requested", cat_src)

    def test_only_requested_dashboard_and_zones_alignment_hooks_exist(self) -> None:
        flex_src = self._read("app/pages/flex.py")
        self.assertIn("self.tool_balance_spacer", flex_src)
        dash_src = self._read("app/pages/dashboard.py")
        self.assertIn("for label in (cap, self.balance, self.balance_hint, privacy):", dash_src)
        self.assertIn("label.setAlignment(Qt.AlignmentFlag.AlignCenter)", dash_src)
        self.assertIn('month_title.setAlignment(Qt.AlignmentFlag.AlignCenter)', dash_src)

    def test_accounts_summary_uses_spread_grid_instead_of_compact_flow(self) -> None:
        src = self._read("app/pages/accounts.py")
        self.assertIn("self.summary_layout = QGridLayout(summary)", src)
        self.assertIn('columns = 4 if mode == "wide" else 2 if mode == "compact" else 1', src)

    def test_trip_rate_editor_has_named_columns(self) -> None:
        src = self._read("app/pages/viajes_dialogs.py")
        self.assertIn('self.rate_factor_label = QLabel("Cantidad")', src)
        self.assertIn('self.rate_price_caption = QLabel("Tarifa")', src)
        self.assertIn('self.rate_total_caption = QLabel("Total calculado")', src)

    def test_work_week_ui_uses_shared_seven_day_calendar(self) -> None:
        calendar = self._read("app/work_calendar.py")
        self.assertIn("WORK_WEEK_DAYS = 7", calendar)
        self.assertIn('"SÁBADO"', calendar)
        self.assertIn('"DOMINGO"', calendar)
        for relative in (
            "app/pages/viajes_dialogs.py",
            "app/pages/viajes_widgets.py",
            "app/pages/extras_widgets.py",
        ):
            src = self._read(relative)
            self.assertIn("iter_week_days", src)
            self.assertNotIn("range(7)", src)

    def test_customization_actions_use_shared_vertical_order_controls(self) -> None:
        src = self._read("app/pages/work_config.py")
        self.assertGreaterEqual(src.count("make_reorder_actions("), 2)
        helper = self._read("app/ui_helpers.py")
        self.assertIn("order = QVBoxLayout(order_host)", helper)
        theme = self._read("app/style_rules.py")
        self.assertIn("QFrame#WorkConfigInset", theme)

    def test_rounded_rect_actions_and_zone_delete_are_explicit(self) -> None:
        helper = self._read("app/ui_helpers.py")
        flex = self._read("app/pages/flex.py")
        theme = self._read("app/style_rules.py")
        self.assertIn('"DangerIconButton" if danger else "CompactIconButton"', helper)
        self.assertIn("COMPACT_ACTION_SIZE = QSize(40, 34)", helper)
        constants = self._read("app/constants.py")
        self.assertIn('NEGATIVE = "#FF7586"', constants)
        self.assertIn('DANGER_ICON_COLOR = NEGATIVE', helper)
        self.assertNotIn("setMask(QRegion(", helper)
        self.assertIn('make_reorder_actions("Eliminar zona")', flex)
        self.assertIn("self.db.flex_zone_delivery_count", flex)
        self.assertIn("QPushButton#CompactIconButton", theme)
        self.assertIn("QPushButton#DangerIconButton:disabled", theme)
        smoke = self._read("scripts/check_app.py")
        self.assertIn("FlexRatesDialog", smoke)

    def test_analysis_rebuilds_after_real_viewport_and_km_value_never_wraps(self) -> None:
        stats = self._read("app/pages/statistics.py")
        trips = self._read("app/pages/viajes_widgets.py")
        self.assertIn("class AnalysisCategoryRow", stats)
        self.assertIn("def showEvent(self, event):", stats)
        self.assertIn("self._left.setSizePolicy(QSizePolicy.Policy.Ignored", stats)
        self.assertIn("self._right.setSizePolicy(QSizePolicy.Policy.Ignored", stats)
        self.assertIn("self.value.setWordWrap(False)", trips)

    def test_smoke_test_expects_seven_day_work_views(self) -> None:
        src = self._read("scripts/check_app.py")
        self.assertIn("trips_tree.day_count() == 7", src)
        self.assertIn("extras_view.day_count() == 7", src)


if __name__ == "__main__":
    unittest.main()
