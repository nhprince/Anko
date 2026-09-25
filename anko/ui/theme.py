"""Design tokens (colours, radii, fonts) and the application stylesheet."""
from __future__ import annotations

DARK = dict(
    name="dark",
    bg="#0c0d0f", bg2="#131418", panel="#17181c", panel2="#1e2025", border="rgba(255,255,255,0.08)",
    border_strong="rgba(255,255,255,0.16)", text="#ecece8", text2="#9b9da3", text3="#62646b",
    accent="#f2a93b", accent2="#d98a1b", accent_text="#1b1204", alpha="#ee8a92", good="#6fcf97", bad="#eb5757",
    lcd_top="#e4e9dd", lcd_bot="#d3dac9", lcd_ink="#121512", lcd_dim="#8b9587", lcd_status="#4a5346",
    bezel="#0a0a0c",
    key_num_top="#3b3e45", key_num_bot="#2c2e34",
    key_fn_top="#2a2c31", key_fn_bot="#1e2024",
    key_op_top="#454850", key_op_bot="#33353c",
    key_del_top="#63302f", key_del_bot="#4a2222",
    key_eq_top="#f7b24a", key_eq_bot="#d98a1b",
    key_nav_top="#24262b", key_nav_bot="#191b1f",
    key_text="#f3f3f0", key_shift="#f2b04c", key_alpha="#ee8a92",
)
LIGHT = dict(
    name="light",
    bg="#e9e7e2", bg2="#f2f0ec", panel="#faf9f6", panel2="#efede8", border="rgba(0,0,0,0.09)",
    border_strong="rgba(0,0,0,0.18)", text="#1c1c1a", text2="#5f605c", text3="#9a9b96",
    accent="#d97706", accent2="#b45f04", accent_text="#ffffff", alpha="#c2414d", good="#2f8f5b", bad="#c43b3b",
    lcd_top="#eef2e7", lcd_bot="#dfe6d5", lcd_ink="#12150f", lcd_dim="#94a08e", lcd_status="#55604f",
    bezel="#c9c6be",
    key_num_top="#ffffff", key_num_bot="#e8e6e0",
    key_fn_top="#dcdad4", key_fn_bot="#c9c7c0",
    key_op_top="#f1efe9", key_op_bot="#dad8d1",
    key_del_top="#f0c9c4", key_del_bot="#e0aca6",
    key_eq_top="#f7b24a", key_eq_bot="#e0921f",
    key_nav_top="#cfcdc6", key_nav_bot="#bdbbb3",
    key_text="#1c1c1a", key_shift="#b8700a", key_alpha="#b23a48",
)

_current = dict(DARK)


class _T:
    """attribute access to the current palette:  T.accent"""

    def __getattr__(self, k):
        try:
            return _current[k]
        except KeyError:
            raise AttributeError(k)


T = _T()


def set_theme(name: str):
    _current.clear()
    _current.update(LIGHT if name == "light" else DARK)


def qss() -> str:
    c = _current
    return f"""
QWidget {{ color: {c['text']}; font-family: 'Segoe UI', 'Noto Sans', 'DejaVu Sans', sans-serif; font-size: 13px; }}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: 4px 6px; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {c['text2']}; }}
QLabel#title {{ font-size: 15px; font-weight: 600; }}
QFrame#card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; border: 1px solid {c['border_strong']};
    selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; outline: 0; }}
QPushButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border: 1px solid {c['border_strong']}; background: {c['panel']}; }}
QPushButton:pressed {{ background: {c['bg2']}; }}
QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: 1px solid {c['accent2']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {c['accent2']}; }}
QPushButton:checked {{ background: {c['accent']}; color: {c['accent_text']}; border: 1px solid {c['accent2']}; }}
QTableWidget, QListWidget, QTreeWidget {{ background: {c['panel']}; border: 1px solid {c['border']};
    border-radius: 10px; gridline-color: {c['border']}; outline: 0; alternate-background-color: {c['panel2']}; }}
QTableWidget::item, QListWidget::item {{ padding: 4px 6px; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
QHeaderView::section {{ background: {c['panel2']}; color: {c['text2']}; border: none; border-bottom: 1px solid {c['border']};
    border-right: 1px solid {c['border']}; padding: 5px 8px; font-weight: 600; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {c['text2']}; padding: 7px 14px; border-radius: 8px; margin: 2px; }}
QTabBar::tab:selected {{ background: {c['panel2']}; color: {c['text']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QMenu {{ background: {c['panel']}; border: 1px solid {c['border_strong']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
"""
