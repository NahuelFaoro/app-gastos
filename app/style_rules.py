from __future__ import annotations

"""Catálogo declarativo de estilos QSS.

Cada selector se define una sola vez. La lógica de paleta/tema vive en
``theme.py`` y los helpers cromáticos en ``theme_tokens.py``. Separar este
catálogo evita que una modificación visual contamine la infraestructura del tema.
"""

from .constants import NEGATIVE
from .theme_tokens import _blend, _resolve_theme, _rgba, _scale_qss_pixels

def build_stylesheet(theme: str = "light", scale: float = 1.0) -> str:
    dark, _accent_name, accent_base = _resolve_theme(theme)
    bg = "#0A0F14" if dark else "#F5F7F8"
    sidebar = "#0D1218" if dark else "#FBFCFD"
    panel = "#121920" if dark else "#FFFFFF"
    panel2 = "#172029" if dark else "#F7F9FA"
    panel3 = "#202A33" if dark else "#EEF2F3"
    text = "#F4F7FA" if dark else "#17222C"
    muted = "#8A96A5" if dark else "#778391"
    muted2 = "#657181" if dark else "#9AA5AF"
    border = "#26323D" if dark else "#E2E7E9"
    border_soft = "#1A242D" if dark else "#EDF1F2"
    hover = "#1A242D" if dark else "#F2F5F6"
    input_bg = "#121821" if dark else "#FFFFFF"
    accent = _blend(accent_base, "#FFFFFF", 0.18 if dark else 0.0) if dark else _blend(accent_base, "#0B1620", 0.04)
    accent_hover = _blend(accent, "#FFFFFF", 0.12 if dark else 0.06)
    accent_soft = _rgba(accent_base, 0.16 if dark else 0.12)
    accent_soft_2 = _rgba(accent_base, 0.24 if dark else 0.18)
    positive = "#5AD8A8" if dark else "#22A978"
    negative = NEGATIVE if dark else "#E94F65"
    negative_soft = _rgba(negative, 0.16)
    negative_border = _rgba(negative, 0.42)
    negative_hover = _rgba(negative, 0.26)
    negative_disabled_bg = _rgba(negative, 0.10)
    negative_disabled_text = _blend(negative, panel2, 0.25)
    negative_disabled_border = _rgba(negative, 0.28)
    warning = "#F4BF68" if dark else "#D9952B"
    purple = "#9890FF" if dark else "#736BE8"
    selection = accent_soft
    white = "#FFFFFF"
    hero0 = _blend(accent_base, "#081117" if dark else "#173F35", 0.72 if dark else 0.62)
    hero1 = _blend(accent_base, "#0E151C" if dark else "#FFFFFF", 0.52 if dark else 0.24)
    hero2 = _blend(accent_base, "#FFFFFF", 0.18 if dark else 0.08)
    surface_hi = _blend(panel, "#FFFFFF", 0.025 if dark else 0.0)
    surface_accent = _blend(panel, accent_base, 0.035 if dark else 0.018)
    focus_border = _blend(accent, "#FFFFFF", 0.08 if dark else 0.0)

    qss = f"""
    /* QSS consolidado: cada selector tiene una única fuente de verdad. */
    * {{
        font-family: "Segoe UI Variable", "Segoe UI", "Inter", "Arial";
        font-size: 13px;
        color: {text};
        outline: none;
    }}
    QMainWindow {{
        background: {bg};
    }}
    QWidget#AppRoot {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {'#0A0F14' if dark else '#F6F8F9'}, stop:1 {'#0C1318' if dark else '#F1F5F5'});
    }}
    QScrollArea#PageScroll {{
        background: {bg};
    }}
    QScrollArea#PageScroll > QWidget > QWidget {{
        background: {bg};
    }}
    QWidget#Sidebar {{
        background: {sidebar};
        border-right: 1px solid {'#18222A' if dark else '#E9EDEF'};
    }}
    QFrame#BrandMark {{
        border: none;
        border-radius: 14px;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0,{accent},stop:1,{'#4CCFA9' if dark else '#24B98F'});
    }}
    QLabel#BrandMarkGlyph {{
        color: #072018;
        font-size: 18px;
        font-weight: 900;
        background: transparent;
    }}
    QLabel#Brand {{
        color: {text};
        padding: 0;
        font-size: 18px;
        font-weight: 850;
        letter-spacing: -.2px;
    }}
    QLabel#BrandSubtitle {{
        font-weight: 600;
        font-size: 9px;
        color: {muted2};
    }}
    QLabel#SidebarCaption {{
        color: {muted2};
        font-weight: 800;
        padding: 11px 11px 4px 11px;
        font-size: 8px;
        letter-spacing: 1.35px;
    }}
    QLabel#SidebarFooter {{
        color: {muted2};
        font-size: 10px;
        line-height: 1.3;
    }}
    QPushButton#SidebarButton {{
        background: transparent;
        color: {muted};
        border: none;
        text-align: left;
        font-weight: 680;
        min-height: 25px;
        padding: 10px 12px;
        border-radius: 12px;
        font-size: 12px;
    }}
    QPushButton#SidebarButton:hover {{
        background: {hover};
        color: {text};
    }}
    QPushButton#SidebarButton[active="true"] {{
        font-weight: 780;
        background: {accent_soft};
        color: {accent};
    }}
    QPushButton#SidebarButton[compact="true"] {{
        text-align: center;
        padding: 10px 0;
        min-width: 48px;
    }}
    QPushButton#QuickAdd[compact="true"] {{
        padding: 0;
        min-width: 0;
        min-height: 42px;
    }}
    QPushButton#QuickAdd {{
        background: {accent};
        color: #092017;
        border: none;
        padding: 11px 14px;
        font-weight: 820;
        text-align: center;
        min-height: 26px;
        border-radius: 13px;
        font-size: 12px;
    }}
    QPushButton#QuickAdd:hover {{
        background: {accent_hover};
    }}
    QLabel#PageTitle {{
        color: {text};
        letter-spacing: -.65px;
        font-size: 32px;
        font-weight: 880;
    }}
    QLabel#PageSubtitle {{
        font-weight: 500;
        font-size: 11px;
        color: {muted};
        margin-top: 1px;
    }}
    QLabel#SectionTitle {{
        color: {text};
        font-size: 15px;
        letter-spacing: -.12px;
        font-weight: 840;
    }}
    QLabel#Muted {{
        color: {muted};
    }}
    QLabel#SmallMuted {{
        color: {muted};
        font-size: 10px;
    }}
    QLabel#TinyCaption {{
        color: {muted2};
        font-size: 9px;
        font-weight: 650;
    }}
    QLabel#Positive {{
        color: {positive};
        font-weight: 720;
    }}
    QLabel#Negative {{
        color: {negative};
        font-weight: 720;
    }}
    QLabel#DialogTitle {{
        color: {text};
        font-size: 20px;
        font-weight: 820;
    }}
    QFrame#Card {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 22px;
    }}
    QFrame#SoftCard {{
        border-radius: 18px;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_accent}, stop:1 {panel2});
        border: 1px solid {border_soft};
    }}
    QFrame#MetricCard {{
        border-radius: 17px;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_accent}, stop:1 {panel2});
        border: 1px solid {border_soft};
    }}
    QFrame#MetricCardClickable {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 17px;
    }}
    QFrame#MetricCardClickable:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#MetricCardClickable[active="true"] {{
        background: {accent_soft};
        border: 1px solid {accent};
    }}
    QFrame#MetricsStrip {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 22px;
    }}
    QFrame#MetricsStrip QFrame#MetricCard {{
        background: transparent;
        border: none;
        border-radius: 0;
    }}
    QFrame#HeroCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {hero0}, stop:0.52 {hero1}, stop:1 {hero2});
        border: none;
        border-radius: 26px;
    }}
    QLabel#HeroCaption {{
        color: {'#B9E9DC' if dark else '#CFF7EB'};
        font-size: 11px;
        font-weight: 760;
        letter-spacing: .8px;
    }}
    QLabel#HeroValue {{
        color: white;
        font-size: 37px;
        font-weight: 880;
        letter-spacing: -.9px;
    }}
    QLabel#HeroHint {{
        color: {'#CDEEE5' if dark else '#DDF7F0'};
        font-size: 11px;
    }}
    QFrame#OverviewCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 22px;
    }}
    QFrame#OverviewMetric {{
        background: transparent;
        border: none;
    }}
    QLabel#OverviewMetricLabel {{
        color: {muted};
        font-size: 10px;
        font-weight: 700;
    }}
    QLabel#OverviewMetricValue {{
        color: {text};
        font-size: 23px;
        font-weight: 850;
        letter-spacing: -.35px;
    }}
    QFrame#OverviewDivider {{
        background: {border};
        border: none;
        max-width: 1px;
    }}
    QLabel#CardCaption {{
        color: {muted};
        font-size: 10px;
        font-weight: 700;
    }}
    QLabel#CardValue {{
        color: {text};
        font-size: 22px;
        font-weight: 820;
    }}
    QPushButton {{
        background: {accent};
        color: #082018;
        border: none;
        min-height: 23px;
        padding: 9px 14px;
        border-radius: 12px;
        font-weight: 740;
    }}
    QPushButton:hover {{
        background: {accent_hover};
    }}
    QPushButton:pressed {{
        background: {'#53C9A8' if dark else '#25A983'};
    }}
    QPushButton:disabled {{
        background: {panel3};
        color: {muted2};
    }}
    QPushButton#SecondaryButton {{
        color: {text};
        background: {panel2};
        border: 1px solid {border};
    }}
    QPushButton#SecondaryButton:hover {{
        border-color: {'#364454' if dark else '#D6DDDF'};
        background: {hover};
    }}
    QPushButton#GhostButton {{
        background: transparent;
        color: {muted};
        border: none;
        padding: 7px 8px;
        border-radius: 10px;
    }}
    QPushButton#GhostButton:hover {{
        background: {hover};
        color: {text};
    }}
    QPushButton#GhostDangerButton {{
        background: transparent;
        color: {negative};
        border: none;
        padding: 7px 8px;
    }}
    QPushButton#GhostDangerButton:hover {{
        background: {'#321D24' if dark else '#FFF0F2'};
    }}
    QPushButton#DangerButton {{
        background: {'#321D24' if dark else '#FFF0F2'};
        color: {negative};
        border: 1px solid {'#4B2630' if dark else '#FFD8DE'};
    }}
    QPushButton#SegmentButton {{
        background: transparent;
        color: {muted};
        border: none;
        border-radius: 9px;
        padding: 7px 12px;
        min-height: 18px;
        font-weight: 700;
    }}
    QPushButton#SegmentButton:hover {{
        background: {hover};
        color: {text};
    }}
    QPushButton#SegmentButton:checked {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent_soft}, stop:1 {accent_soft_2});
        color: {accent};
    }}
    QDialog#TransactionDialog {{
        background: {bg};
    }}
    QFrame#DialogSegmentWrap {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 16px;
    }}
    QFrame#AmountHeroCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {panel2}, stop:1 {panel});
        border: 1px solid {border};
        border-radius: 22px;
    }}
    QFrame#InputSectionCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 20px;
    }}
    QFrame#InstallmentCard {{
        background: {panel2};
        border: 1px solid {border};
        border-radius: 20px;
    }}
    QFrame#DialogActionBar {{
        background: transparent;
        border-top: 1px solid {border_soft};
        padding-top: 8px;
    }}
    QPushButton#DialogPrimaryButton {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent}, stop:1 {'#83E8CE' if dark else '#65DCC0'});
        color: #072018;
        border: none;
        border-radius: 13px;
        padding: 10px 16px;
        font-weight: 830;
    }}
    QPushButton#DialogPrimaryButton:hover {{
        background: {accent_hover};
    }}
    QWidget#InlineActionGroup {{
        background: transparent;
    }}
    QLineEdit {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QComboBox {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QDateEdit {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QDoubleSpinBox {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QSpinBox {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QPlainTextEdit {{
        padding: 8px 11px;
        min-height: 25px;
        border-radius: 13px;
        background: {input_bg};
        border: 1px solid {border};
        selection-background-color: {accent};
    }}
    QLineEdit:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QComboBox:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QDateEdit:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QDoubleSpinBox:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QSpinBox:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QPlainTextEdit:hover {{
        border-color: {'#354250' if dark else '#D6DEE1'};
    }}
    QLineEdit:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QComboBox:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QDateEdit:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QDoubleSpinBox:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QSpinBox:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QPlainTextEdit:focus {{
        border: 1px solid {focus_border};
        background: {panel};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}
    QComboBox QAbstractItemView {{
        background: {panel};
        border: 1px solid {border};
        selection-background-color: {accent_soft};
        selection-color: {text};
        padding: 4px;
    }}
    QCalendarWidget {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 14px;
    }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background: {panel2};
        border: none;
        padding: 6px;
    }}
    QCalendarWidget QToolButton {{
        font-weight: 760;
        background: {panel2};
        color: {text};
        border: 1px solid {border_soft};
        border-radius: 10px;
        padding: 7px 10px;
    }}
    QCalendarWidget QToolButton:hover {{
        background: {hover};
    }}
    QCalendarWidget QAbstractItemView {{
        background: {panel};
        color: {text};
        border: none;
        outline: 0;
        selection-background-color: {accent};
        selection-color: #082018;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {text};
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 5px;
        border: 1px solid {border};
        background: {input_bg};
    }}
    QCheckBox::indicator:checked {{
        background: {accent};
        border-color: {accent};
    }}
    QFrame#PrivacyBox {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 13px;
    }}
    QFrame#PrivacyBox[active="true"] {{
        background: {accent_soft};
        border-color: {accent};
    }}
    QLabel#PrivacyLabel {{
        color: {text};
        font-size: 10px;
        font-weight: 760;
    }}
    QLabel#PrivacyStatus {{
        color: {muted};
        font-size: 9px;
        padding-left: 2px;
    }}
    QLabel#FieldLabel {{
        color: {muted};
        font-size: 10px;
        font-weight: 700;
    }}
    QFrame#AmountCard {{
        background: {panel2};
        border: 1px solid {border};
        border-radius: 16px;
    }}
    QLabel#CurrencyPrefix {{
        color: {muted};
        font-size: 24px;
        font-weight: 760;
        padding-left: 4px;
    }}
    QLineEdit#MoneyEdit {{
        background: transparent;
        border: none;
        padding: 3px 7px;
        min-height: 48px;
        font-size: 34px;
        font-weight: 860;
        color: {text};
        letter-spacing: -0.4px;
    }}
    QLineEdit#MoneyEdit[compact="true"] {{
        padding: 8px 11px;
        min-height: 25px;
        font-size: 18px;
        font-weight: 760;
        letter-spacing: 0px;
        background: {input_bg};
        border: 1px solid {border};
    }}
    QLineEdit#MoneyEdit:focus {{
        border: none;
    }}
    QLineEdit#MoneyEdit[compact="true"]:focus {{
        border: 1px solid {accent};
    }}
    QPushButton#CategorySelect {{
        background: {panel2};
        color: {text};
        border: 1px solid {border};
        border-radius: 18px;
        text-align: left;
        padding: 10px 14px;
    }}
    QPushButton#CategorySelect:hover {{
        background: {hover};
        border-color: {accent};
    }}
    QPushButton#CategoryChip {{
        background: {panel2};
        color: {text};
        border: none;
        border-radius: 15px;
        padding: 6px 10px;
        font-size: 10px;
        font-weight: 650;
    }}
    QPushButton#CategoryChip:hover {{
        background: {accent_soft};
        color: {accent};
    }}
    QScrollArea#CategoryPickerScroll {{
        background: transparent;
    }}
    QScrollArea#CategoryPickerScroll > QWidget > QWidget {{
        background: transparent;
    }}
    QPushButton#CategoryPickerGroupButton {{
        background: {panel2};
        color: {text};
        border: 1px solid {border_soft};
        border-radius: 12px;
        padding: 9px 12px;
        text-align: left;
        font-size: 11px;
        font-weight: 780;
    }}
    QPushButton#CategoryPickerGroupButton:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#CategoryToolbar {{
        border: none;
        background: {panel2};
        border-radius: 16px;
    }}
    QFrame#FilterBar {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#MovementSummary {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#CategoryGroupCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 24px;
    }}
    QFrame#CategoryGroupCard:hover {{
        background: {panel2};
    }}
    QFrame#CategoryItemCard {{
        background: transparent;
        border: none;
        border-radius: 15px;
    }}
    QFrame#CategoryItemCard:hover {{
        border-color: {border};
        background: {surface_accent};
    }}
    QLabel#CategoryGroupName {{
        color: {text};
        font-size: 16px;
        font-weight: 810;
    }}
    QLabel#CategoryItemName {{
        color: {text};
        font-size: 11px;
        font-weight: 720;
    }}
    QPushButton#CategoryAddChild {{
        border-radius: 9px;
        padding: 6px 10px;
        font-size: 10px;
        background: transparent;
        color: {accent};
        border: none;
        font-weight: 800;
    }}
    QPushButton#CategoryAddChild:hover {{
        background: {accent_soft};
    }}
    QFrame#CategoryDivider {{
        background: {border_soft};
        border: none;
    }}
    QPushButton#IconChoice {{
        background: transparent;
        color: {text};
        border: none;
        border-radius: 14px;
    }}
    QPushButton#IconChoice:hover {{
        background: {accent_soft};
        border: none;
    }}
    QPushButton#IconChoice:checked {{
        background: {accent_soft};
        border: none;
    }}
    QFrame#DayGroup {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 18px;
    }}
    QLabel#DayTitle {{
        color: {text};
        font-size: 13px;
        font-weight: 800;
    }}
    QFrame#TransactionRow {{
        background: transparent;
        border: none;
        border-radius: 13px;
    }}
    QFrame#TransactionRow:hover {{
        border-color: {border};
        border: none;
        background: {surface_accent};
    }}
    QFrame#TransactionRowFlat {{
        background: transparent;
        border: none;
        border-radius: 10px;
    }}
    QFrame#TransactionRowFlat:hover {{
        background: {surface_accent};
    }}
    QLabel#TransactionTitle {{
        color: {text};
        font-weight: 760;
        font-size: 12px;
    }}
    QLabel#TransactionAmount {{
        color: {text};
        font-size: 12px;
        font-weight: 800;
    }}
    QLabel#TransactionAmountPositive {{
        color: {positive};
        font-size: 12px;
        font-weight: 800;
    }}
    QLabel#TransactionAmountNegative {{
        color: {negative};
        font-size: 12px;
        font-weight: 800;
    }}
    QPushButton#RowActionButton {{
        background: transparent;
        color: {muted};
        border: none;
        border-radius: 8px;
        padding: 5px 8px;
        font-size: 10px;
    }}
    QPushButton#RowActionButton:hover {{
        background: {hover};
        color: {text};
    }}
    QPushButton#RowDeleteButton {{
        background: transparent;
        color: {negative};
        border: none;
        border-radius: 8px;
        padding: 5px 7px;
    }}
    QFrame#AccountCard {{
        background: {panel};
        border-radius: 22px;
        border: 1px solid {border_soft};
    }}
    QFrame#AccountCard:hover {{
        background: {'#171F28' if dark else '#FFFFFF'};
        border-color: {'#34434F' if dark else '#D5DEE1'};
    }}
    QFrame#AccountCardExcluded {{
        background: {panel2};
        border-radius: 22px;
        border: 1px solid {border_soft};
    }}
    QFrame#AccountCardExcluded:hover {{
        border-color: {'#34434F' if dark else '#D5DEE1'};
    }}
    QLabel#AccountName {{
        color: {text};
        font-size: 13px;
        font-weight: 800;
    }}
    QLabel#AccountType {{
        color: {muted};
        font-size: 9px;
        font-weight: 700;
    }}
    QLabel#AccountBalance {{
        color: {text};
        font-size: 24px;
        font-weight: 840;
    }}
    QLabel#BalanceIncludedChip {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 10px;
        padding: 3px 8px;
        font-size: 9px;
        font-weight: 750;
    }}
    QLabel#BalanceExcludedChip {{
        background: {panel3};
        color: {muted};
        border: none;
        border-radius: 10px;
        padding: 3px 8px;
        font-size: 9px;
        font-weight: 750;
    }}
    QFrame#WalletMiniCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#WalletMiniCard:hover {{
        border-color: {'#3A4B57' if dark else '#D7E0E2'};
    }}
    QFrame#WalletMiniCardExcluded {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QLabel#WalletMiniName {{
        color: {text};
        font-size: 11px;
        font-weight: 760;
    }}
    QLabel#WalletMiniBalance {{
        color: {text};
        font-size: 15px;
        font-weight: 810;
    }}
    QFrame#DashboardSection {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 22px;
    }}
    QFrame#DashboardCategoryRow {{
        background: transparent;
        border: none;
        border-radius: 10px;
    }}
    QFrame#DashboardInstallmentRow {{
        background: transparent;
        border: none;
        border-radius: 10px;
    }}
    QFrame#DashboardCategoryRow:hover {{
        background: {hover};
    }}
    QFrame#DashboardInstallmentRow:hover {{
        background: {hover};
    }}
    QLabel#DashboardEyebrow {{
        color: {muted};
        font-size: 9px;
        font-weight: 760;
        letter-spacing: .7px;
    }}
    QFrame#AnalysisControl {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 19px;
    }}
    QPushButton#AnalysisKindButton {{
        background: transparent;
        color: {muted};
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 8px 17px;
        font-size: 12px;
        font-weight: 800;
    }}
    QPushButton#AnalysisKindButton:checked {{
        color: {text};
        border-bottom-color: {accent};
    }}
    QPushButton#AnalysisModeButton {{
        background: transparent;
        color: {muted};
        border: none;
        border-radius: 9px;
        padding: 7px 12px;
        font-size: 10px;
        font-weight: 720;
    }}
    QPushButton#AnalysisModeButton:checked {{
        background: {accent_soft};
        color: {accent};
    }}
    QPushButton#AnalysisModeButton:hover {{
        background: {hover};
        color: {text};
    }}
    QLabel#AnalysisPeriodLabel {{
        color: {text};
        font-size: 16px;
        font-weight: 820;
        padding: 3px 9px;
    }}
    QFrame#AnalysisHero {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 20px;
    }}
    QLabel#AnalysisHeroValue {{
        color: {text};
        font-size: 33px;
        font-weight: 860;
    }}
    QFrame#CategoryStatRow {{
        background: transparent;
        border: none;
        border-radius: 11px;
    }}
    QFrame#CategoryBreakdownRow {{
        background: transparent;
        border: none;
        border-radius: 11px;
    }}
    QFrame#CategoryStatRow:hover {{
        background: {hover};
    }}
    QFrame#CategoryBreakdownRow:hover {{
        background: {hover};
    }}
    QLabel#AnalysisHistoryNote {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 10px;
        padding: 8px 10px;
        font-size: 9px;
        font-weight: 650;
    }}
    QFrame#AnalysisDistributionBar {{
        background: {panel3};
        border: none;
        border-radius: 9px;
    }}
    QFrame#AnalysisCategoryCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#AnalysisCategoryCard:hover {{
        background: {hover};
        border-color: {border};
    }}
    QLabel#AnalysisCategoryName {{
        color: {text};
        font-size: 13px;
        font-weight: 790;
    }}
    QLabel#AnalysisCategoryPercent {{
        color: {muted};
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel#AnalysisCategoryAmount {{
        color: {text};
        font-size: 14px;
        font-weight: 820;
    }}
    QFrame#AnalysisBackBar {{
        background: {accent_soft};
        border: none;
        border-radius: 12px;
    }}
    QLabel#DonutCenterLabel {{
        color: {text};
        font-size: 14px;
        font-weight: 820;
        background: transparent;
    }}
    QLabel#DonutCenterMuted {{
        color: {muted};
        font-size: 11px;
        font-weight: 650;
        background: transparent;
    }}
    QFrame#MiniStatCard {{
        background: {panel2};
        border: none;
        border-radius: 13px;
    }}
    QFrame#InstallmentTimelineRow {{
        background: {panel2};
        border: none;
        border-radius: 12px;
    }}
    QFrame#InstallmentTimelineCurrent {{
        background: {accent_soft};
        border: 1px solid {accent};
        border-radius: 12px;
    }}
    QLabel#InstallmentNumber {{
        background: {panel3};
        color: {text};
        border: none;
        border-radius: 15px;
        font-weight: 820;
    }}
    QLabel#InstallmentNumberCurrent {{
        background: {accent};
        color: #082018;
        border: none;
        border-radius: 15px;
        font-weight: 900;
    }}
    QLabel#InstallmentPercent {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 9px;
        padding: 2px 7px;
        font-size: 9px;
        font-weight: 820;
    }}
    QFrame#MonthlyCommitmentCard {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 14px;
    }}
    QFrame#MonthlyCommitmentCard:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#MonthlyCommitmentCurrent {{
        background: {accent_soft};
        border: 1px solid {accent};
        border-radius: 14px;
    }}
    QFrame#MonthlyCommitmentCurrent:hover {{
        background: {accent_soft_2};
    }}
    QLabel#InstallmentMonthlyHighlight {{
        background: {accent_soft};
        color: {accent};
        border-radius: 10px;
        padding: 5px 9px;
        font-size: 10px;
        font-weight: 800;
    }}
    QFrame#FlatListRow {{
        background: transparent;
        border: none;
        border-radius: 11px;
    }}
    QFrame#FlatListRow:hover {{
        background: {surface_accent};
    }}
    QFrame#Hairline {{
        background: {border_soft};
        border: none;
        min-height: 1px;
        max-height: 1px;
    }}
    QLabel#CalendarPeriod {{
        color: {text};
        font-size: 14px;
        font-weight: 810;
        min-width: 150px;
    }}
    QPushButton#CalendarNavButton {{
        background: {panel};
        color: {text};
        border: 1px solid {border};
        padding: 0;
        font-size: 18px;
        border-radius: 12px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
    }}
    QPushButton#PeriodNavButton {{
        background: {panel};
        color: {text};
        border: 1px solid {border};
        padding: 0;
        font-size: 18px;
        border-radius: 12px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
    }}
    QPushButton#CalendarNavButton:hover {{
        background: {hover};
        border-color: {accent};
    }}
    QPushButton#PeriodNavButton:hover {{
        background: {hover};
        border-color: {accent};
    }}
    QLabel#PeriodLabel {{
        color: {text};
        min-width: 138px;
        font-size: 12px;
        font-weight: 800;
        padding: 0 4px;
    }}
    QLabel#CalendarWeekday {{
        color: {muted};
        font-size: 9px;
        font-weight: 780;
        padding: 2px 0 4px 0;
    }}
    QFrame#CalendarDay {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 13px;
    }}
    QFrame#CalendarDay:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#CalendarDay[selected="true"] {{
        background: {accent_soft};
        border: 1px solid {accent};
    }}
    QFrame#CalendarDay[today="true"] {{
        border-color: {accent};
    }}
    QFrame#CalendarDayEmpty {{
        background: transparent;
        border: 1px solid transparent;
    }}
    QLabel#CalendarDayNumber {{
        color: {text};
        font-size: 12px;
        font-weight: 820;
    }}
    QLabel#CalendarTodayBadge {{
        background: {accent};
        color: #082018;
        border-radius: 7px;
        padding: 2px 6px;
        font-size: 8px;
        font-weight: 850;
    }}
    QLabel#CalendarExpense {{
        color: {negative};
        font-size: 9px;
        font-weight: 760;
    }}
    QLabel#CalendarIncome {{
        color: {positive};
        font-size: 9px;
        font-weight: 760;
    }}
    QLabel#CalendarMeta {{
        color: {muted};
        font-size: 8px;
    }}
    QFrame#ImportInboxHero {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {surface_hi}, stop:1 {panel});
        border: 1px solid {border_soft};
        border-radius: 22px;
    }}
    QLabel#ImportMetricValue {{
        color: {text};
        font-size: 24px;
        font-weight: 850;
    }}
    QLabel#ImportMetricValueReady {{
        color: {accent};
        font-size: 24px;
        font-weight: 850;
    }}
    QFrame#ImportMovementCard {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 13px;
    }}
    QFrame#ImportMovementCard:hover {{
        background: {hover};
        border-color: {border_soft};
    }}
    QFrame#ImportCollapsedGroup {{
        background: {panel2};
        border: none;
        border-radius: 14px;
    }}
    QFrame#ImportEmptyState {{
        background: {panel};
        border: 1px dashed {border};
        border-radius: 18px;
    }}
    QPushButton#ImportCategoryButtonReady {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 10px;
        padding: 5px 9px;
        font-size: 9px;
        font-weight: 760;
    }}
    QPushButton#ImportCategoryButtonReady:hover {{
        background: {accent_soft_2};
    }}
    QPushButton#ImportCategoryButtonPending {{
        background: {'#342A1A' if dark else '#FFF6E7'};
        color: {warning};
        border: none;
        border-radius: 10px;
        padding: 5px 9px;
        font-size: 9px;
        font-weight: 760;
    }}
    QPushButton#ImportCategoryButtonTransfer {{
        background: {'#172C3B' if dark else '#EAF6FC'};
        color: #62B3E8;
        border: none;
        border-radius: 10px;
        padding: 5px 9px;
        font-size: 9px;
        font-weight: 760;
    }}
    QPushButton#ImportAcceptButton {{
        background: {accent};
        color: #082018;
        border: none;
        border-radius: 10px;
        padding: 7px 12px;
        font-weight: 800;
    }}
    QPushButton#ImportShowMore {{
        background: transparent;
        color: {accent};
        border: none;
        padding: 9px 18px;
        font-weight: 780;
    }}
    QPushButton#ImportShowMore:hover {{
        background: {accent_soft};
    }}
    QLabel#ImportAmount {{
        color: {text};
        font-size: 27px;
        font-weight: 840;
    }}
    QLabel#IntegrationTitle {{
        color: {text};
        font-size: 13px;
        font-weight: 790;
    }}
    QLabel#IntegrationStatus {{
        background: {panel3};
        color: {muted};
        border: none;
        border-radius: 9px;
        padding: 4px 8px;
        font-size: 9px;
        font-weight: 780;
    }}
    QLabel#IntegrationStatus[state="ok"] {{
        background: {accent_soft};
        color: {accent};
    }}
    QLabel#IntegrationStatus[state="warn"] {{
        background: {'#382E1E' if dark else '#FFF6E7'};
        color: {warning};
    }}
    QFrame#RecurringCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 17px;
    }}
    QFrame#BudgetCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 17px;
    }}
    QFrame#RecurringCard:hover {{
        border-color: {border};
        background: {hover};
    }}
    QFrame#BudgetCard:hover {{
        border-color: {border};
        background: {hover};
    }}
    QFrame#RecurringCardPaused {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 17px;
    }}
    QLabel#RecurringTitle {{
        color: {text};
        font-size: 12px;
        font-weight: 780;
    }}
    QLabel#RecurringDate {{
        color: {text};
        font-size: 11px;
        font-weight: 720;
    }}
    QLabel#RecurringActiveChip {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 10px;
        padding: 3px 8px;
        font-size: 9px;
        font-weight: 760;
    }}
    QLabel#RecurringPausedChip {{
        background: {panel3};
        color: {muted};
        border: none;
        border-radius: 10px;
        padding: 3px 8px;
        font-size: 9px;
        font-weight: 760;
    }}
    QLabel#BudgetName {{
        color: {text};
        font-size: 14px;
        font-weight: 800;
    }}
    QLabel#BudgetSpent {{
        color: {text};
        font-size: 19px;
        font-weight: 820;
    }}
    QFrame#StatementCategoryGroup {{
        background: transparent;
        border: none;
    }}
    QFrame#StatementCategoryHeader {{
        background: {panel2};
        border: none;
        border-radius: 12px;
    }}
    QFrame#StatementCategoryHeader:hover {{
        background: {hover};
    }}
    QPushButton#DisclosureButton {{
        background: transparent;
        color: {muted};
        border: none;
        padding: 0;
        font-size: 17px;
        font-weight: 800;
    }}
    QPushButton#StatementCategoryName {{
        background: transparent;
        color: {text};
        border: none;
        text-align: left;
        padding: 2px 0;
        font-size: 12px;
        font-weight: 780;
    }}
    QPushButton#StatementCategoryName:hover {{
        color: {accent};
    }}
    QFrame#FlexHero {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 19px;
    }}
    QFrame#FlexSettlementCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 19px;
    }}
    QFrame#FlexZoneCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 19px;
    }}
    QLabel#WorkWeekTitle {{
        color: {text};
        font-size: 14px;
        font-weight: 790;
        min-width: 150px;
    }}
    QFrame#FlexWeekBar {{
        background: {panel2};
        border: none;
        border-radius: 14px;
    }}
    QFrame#FlexActionBar {{
        background: {panel2};
        border: none;
        border-radius: 14px;
    }}
    QFrame#FlexRateRow {{
        background: {panel2};
        border: none;
        border-radius: 14px;
    }}
    QLabel#FlexToolTitle {{
        color: {text};
        font-size: 18px;
        font-weight: 810;
    }}
    QLabel#FlexWeekTitle {{
        color: {text};
        font-size: 14px;
        font-weight: 780;
    }}
    QLabel#FlexZoneName {{
        color: {text};
        font-size: 14px;
        font-weight: 800;
    }}
    QLabel#FlexZoneCount {{
        color: {text};
        font-size: 28px;
        font-weight: 830;
    }}
    QLabel#FlexZoneSubtotal {{
        color: {text};
        font-size: 16px;
        font-weight: 800;
    }}
    QPushButton#FlexAddButton {{
        background: {accent};
        color: #082018;
        border: none;
        border-radius: 11px;
        padding: 9px 13px;
        font-weight: 800;
    }}
    QPushButton#FlexMinusButton {{
        background: {panel3};
        color: {text};
        border: none;
        border-radius: 11px;
        padding: 8px;
        font-size: 17px;
        font-weight: 800;
    }}
    QPushButton#FlexHistoryButton {{
        background: {panel};
        color: {text};
        border: 1px solid {border_soft};
        border-radius: 12px;
        padding: 11px 13px;
        text-align: center;
        font-weight: 700;
    }}
    QPushButton#FlexHistoryButton:hover {{
        background: {hover};
    }}
    QFrame#ToolsSubnav {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 14px;
    }}
    QFrame#ToolChooserCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 20px;
    }}
    QFrame#ToolChooserCard:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#ToolChooserTile {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 16px;
    }}
    QFrame#ToolChooserTile:hover {{
        background: {accent_soft};
        border-color: {accent};
    }}
    QLabel#ToolChooserTitle {{
        color: {text};
        font-size: 17px;
        font-weight: 820;
    }}
    QLabel#ToolChooserArrow {{
        color: {muted};
        font-size: 26px;
        font-weight: 700;
        padding: 0 4px;
    }}
    QPushButton#WorkFilterChip {{
        background: {accent_soft};
        color: {accent};
        border: 1px solid {accent};
        border-radius: 10px;
        padding: 7px 11px;
        font-weight: 760;
    }}
    QPushButton#WorkFilterChip:hover {{
        background: {hover};
    }}
    QFrame#WorkMetricCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#WorkMetricCardClickable {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#WorkMetricCardClickable:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#WorkMetricCardClickable[active="true"] {{
        background: {accent_soft};
        border-color: {accent};
    }}
    QLabel#WorkMetricCaption {{
        color: {muted};
        font-size: 10px;
        font-weight: 760;
    }}
    QLabel#WorkMetricValue {{
        color: {text};
        font-size: 24px;
        font-weight: 860;
    }}
    QLabel#WorkMetricSecondary {{
        color: {text};
        font-size: 14px;
        font-weight: 790;
    }}
    QLabel#WorkMetricHint {{
        color: {muted};
        font-size: 9px;
        font-weight: 560;
    }}
    QScrollArea#WorkDaysScroll {{
        background: transparent;
        border: none;
    }}
    QScrollArea#WorkDaysScroll > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    QFrame#WorkDayCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#WorkDayHeader {{
        background: {panel2};
        border: none;
        border-radius: 14px;
    }}
    QFrame#WorkDayHeader:hover {{
        background: {hover};
    }}
    QFrame#WorkDayHeader[expanded="true"] {{
        background: {accent_soft};
    }}
    QFrame#WorkTripCompactCard {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 12px;
    }}
    QFrame#WorkTripCompactCard:hover {{
        background: {hover};
        border-color: {border};
    }}
    QFrame#WorkTripCompactCard[selected="true"] {{
        background: {accent_soft};
        border-color: {accent};
    }}
    QLabel#WorkDayChevron {{
        color: {muted};
        font-size: 18px;
        font-weight: 800;
    }}
    QLabel#WorkDayTitle {{
        color: {text};
        font-size: 12px;
        font-weight: 840;
    }}
    QLabel#WorkDayChip {{
        color: {muted};
        background: {panel3};
        border: 1px solid {border_soft};
        border-radius: 9px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 700;
    }}
    QLabel#WorkDayEmpty {{
        color: {muted};
        font-size: 11px;
    }}
    QTableWidget#WorkDayTable {{
        background: transparent;
        border: none;
        border-radius: 0;
        outline: 0;
        selection-background-color: {accent_soft};
        selection-color: {text};
    }}
    QTableWidget#WorkDayTable::item {{
        padding: 8px 7px;
        border-bottom: 1px solid {border_soft};
    }}
    QTableWidget#WorkDayTable::item:selected {{
        background: {accent_soft};
        color: {text};
        border: none;
        border-bottom: 1px solid {border_soft};
    }}
    QTableWidget#WorkMonthTable {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 14px;
        outline: 0;
    }}
    QTreeWidget#WorkTripsTree {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 14px;
        alternate-background-color: {panel2};
        selection-background-color: {accent_soft};
        selection-color: {text};
    }}
    QTreeWidget#WorkTripsTree::item {{
        padding: 8px 7px;
        border-bottom: 1px solid {border_soft};
    }}
    QTreeWidget#WorkTripsTree::item:has-children {{
        background: {panel2};
        color: {text};
        font-weight: 800;
        padding: 10px 8px;
    }}
    QTreeWidget#WorkTripsTree::item:selected {{
        background: {accent_soft};
        color: {text};
    }}
    QTableWidget {{
        background: {panel};
        alternate-background-color: {panel2};
        border: 1px solid {border_soft};
        border-radius: 14px;
        gridline-color: transparent;
        selection-background-color: {accent_soft};
        selection-color: {text};
    }}
    QTableWidget::item {{
        padding: 8px 7px;
        border-bottom: 1px solid {border_soft};
    }}
    QHeaderView::section {{
        background: {panel2};
        color: {muted};
        padding: 9px 8px;
        border: none;
        border-bottom: 1px solid {border_soft};
        font-size: 10px;
        font-weight: 760;
    }}
    QTableCornerButton::section {{
        background: {panel2};
        border: none;
    }}
    QProgressBar {{
        background: {panel3};
        border: none;
        border-radius: 4px;
        min-height: 7px;
        max-height: 7px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {accent};
        border-radius: 4px;
    }}
    QTabWidget::pane {{
        border: none;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {muted};
        padding: 8px 13px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {text};
        border-bottom: 2px solid {accent};
        font-weight: 760;
    }}
    QDialog {{
        background: {bg};
    }}
    QMessageBox {{
        background: {bg};
    }}
    QMenu {{
        background: {panel};
        color: {text};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 7px;
    }}
    QMenu::item {{
        border-radius: 9px;
        padding: 9px 30px 9px 13px;
    }}
    QMenu::item:selected {{
        background: {accent_soft};
        color: {text};
    }}
    QMenu::separator {{
        height: 1px;
        background: {border_soft};
        margin: 5px 8px;
    }}
    QToolTip {{
        background: {panel};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 7px 9px;
    }}
    QLabel#HeroTitle {{
        color: white;
        font-size: 21px;
        font-weight: 830;
    }}
    QFrame#HeroCard QLabel#Muted {{
        color: #D6EEE7;
    }}
    QLabel#MobileUrl {{
        color: white;
        font-size: 18px;
        font-weight: 760;
        padding: 6px 0;
    }}
    QFrame#InsetCard {{
        background: rgba(5, 27, 21, 0.34);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 15px;
    }}
    QFrame#WorkConfigCard {{
        background: {panel};
        border: 1px solid {border_soft};
        border-radius: 18px;
    }}
    QFrame#WorkConfigInset {{
        background: {panel2};
        border: 1px solid {border_soft};
        border-radius: 15px;
    }}
    QFrame#CategoryTreeRow {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 13px;
    }}
    QFrame#CategoryTreeRow:hover {{
        background: {hover};
        border-color: {border_soft};
    }}
    QFrame#CategoryTreeRow[dropTarget="true"] {{
        background: {accent_soft};
        border: 1px solid {accent};
    }}
    QPushButton#CompactIconButton {{
        background: {panel2};
        color: {text};
        border: 1px solid {border_soft};
        border-radius: 10px;
        padding: 0px;
        min-width: 40px;
        max-width: 40px;
        min-height: 34px;
        max-height: 34px;
    }}
    QPushButton#CompactIconButton:hover {{
        background: {hover};
        border-color: {border};
    }}
    QPushButton#DangerIconButton {{
        background: {negative_soft};
        color: {negative};
        border: 1px solid {negative_border};
        border-radius: 10px;
        padding: 0px;
        min-width: 40px;
        max-width: 40px;
        min-height: 34px;
        max-height: 34px;
    }}
    QPushButton#DangerIconButton:hover {{
        background: {negative_hover};
        border-color: {negative};
    }}
    QPushButton#DangerIconButton:disabled {{
        background: {negative_disabled_bg};
        color: {negative_disabled_text};
        border-color: {negative_disabled_border};
    }}
    QFrame#HeroCard QLabel#CardCaption {{
        color: #B7DBD1;
        font-size: 9px;
        font-weight: 780;
        letter-spacing: .8px;
    }}
    QLabel#PairCode {{
        color: white;
        font-size: 24px;
        font-weight: 880;
        letter-spacing: 3px;
    }}
    QLabel#StepBadge {{
        background: {accent_soft};
        color: {accent};
        border: none;
        border-radius: 9px;
        font-size: 11px;
        font-weight: 850;
    }}
    QScrollBar:vertical {{
        background: transparent;
        margin: 3px 1px;
        width: 7px;
    }}
    QScrollBar::handle:vertical {{
        background: {'#394450' if dark else '#C8D0D4'};
        min-height: 30px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {'#4B5866' if dark else '#ABB6BC'};
    }}
    QScrollBar::add-line:vertical {{
        height: 0;
    }}
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 1px 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {'#394450' if dark else '#C8D0D4'};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:horizontal {{
        width: 0;
    }}
    QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QWidget#PageHeaderBox {{
        background: transparent;
    }}
    QLabel#PageEyebrow {{
        color: {accent};
        font-size: 8px;
        font-weight: 900;
        letter-spacing: 1.7px;
    }}
    QFrame#AccountAccent {{
        margin-bottom: 2px;
    }}
    """
    return _scale_qss_pixels(qss, scale)
