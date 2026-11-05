"""Design tokens and the app-wide style sheet.

Palette: 漆喰 (plaster white) surfaces, 墨 (sumi) ink, an accent that defaults
to 藍 (indigo), plus 弁柄 / 金茶 / 常盤 for warnings and good states.
"""
from __future__ import annotations

import sys
from pathlib import Path
from string import Template

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette

from ..paths import config_dir
from . import icons

LIGHT = {
    "desk": "#E7E8E5", "chrome": "#F6F6F4", "shikkui": "#F0F1EE", "paper": "#FFFFFF", "paper2": "#FAFAF8",
    "ink": "#23262B", "ink2": "#5E656F", "ink3": "#8C929A", "rule": "#DEE0E2", "rule2": "#EDEEEF",
    "bengara": "#9A3C2B", "bengara_tint": "#F5E6E2", "kincha": "#8F5E0C", "kincha_tint": "#F5EDDB",
    "tokiwa": "#2D6C50", "tokiwa_tint": "#E2EFE8", "field": "#F6F7F5", "shadow": "#23262B",
}
DARK = {
    "desk": "#101215", "chrome": "#1A1D21", "shikkui": "#1D2025", "paper": "#23272D", "paper2": "#1F2227",
    "ink": "#E6E7E9", "ink2": "#A2A8B1", "ink3": "#7B828C", "rule": "#343940", "rule2": "#2C3036",
    "bengara": "#DB8572", "bengara_tint": "#3A2622", "kincha": "#D8A64B", "kincha_tint": "#362C1B",
    "tokiwa": "#7AC29F", "tokiwa_tint": "#1F3329", "field": "#1B1E23", "shadow": "#000000",
}
# name: (light, dark)
ACCENTS = {
    "ai": ("#28457A", "#94AADA"),      # 藍
    "tokiwa": ("#2D6C50", "#7AC29F"),  # 常盤
    "shu": ("#A8412A", "#E89A84"),     # 朱
    "fuji": ("#5B4B9A", "#AE9CE0"),    # 藤
    "sumi": ("#3A3F46", "#C3C8CF"),    # 墨
}
CAT_COLORS = {
    "shop": ("#9C6714", "#D5A04B"), "svc": ("#366AA2", "#80A8DA"), "fin": ("#2D6C50", "#7AC29F"),
    "game": ("#6857A2", "#AE9CE0"), "gov": ("#9A3C2B", "#DB8572"), "work": ("#5B636D", "#A2A8B1"),
    "teal": ("#1F6F78", "#6CC3CB"), "plum": ("#8A3E6B", "#D98CBB"), "olive": ("#5F6B1F", "#B5C46A"),
    "rust": ("#A0522D", "#E0A07A"),
}

_state = {"tokens": dict(LIGHT), "dark": False, "density": "standard", "font_px": 13}


def mix(a: str, b: str, t: float) -> str:
    ca, cb = QColor(a), QColor(b)
    r = round(ca.red() + (cb.red() - ca.red()) * t)
    g = round(ca.green() + (cb.green() - ca.green()) * t)
    bl = round(ca.blue() + (cb.blue() - ca.blue()) * t)
    return QColor(r, g, bl).name()


def _accent_pair(accent: str) -> tuple[str, str]:
    if accent in ACCENTS:
        return ACCENTS[accent]
    c = QColor(accent)
    if not c.isValid():
        return ACCENTS["ai"]
    return c.name(), mix(c.name(), "#FFFFFF", 0.5)


def resolve(dark: bool, accent: str) -> dict:
    tok = dict(DARK if dark else LIGHT)
    light_ac, dark_ac = _accent_pair(accent)
    ai = dark_ac if dark else light_ac
    tok["ai"] = ai
    tok["ai_hover"] = mix(ai, "#FFFFFF", 0.15) if dark else mix(ai, "#000000", 0.18)
    tok["ai_ink"] = "#121722" if dark else "#FFFFFF"
    tok["ai_tint"] = mix(tok["paper"], ai, 0.20 if dark else 0.11)
    tok["ai_line"] = mix(tok["paper"], ai, 0.45 if dark else 0.33)
    tok["mark_bg"] = light_ac
    tok["mark_fg"] = "#F0F1EE"
    return tok


def system_is_dark() -> bool:
    app = QGuiApplication.instance()
    try:
        return app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def is_dark() -> bool:
    return _state["dark"]


def t(key: str) -> str:
    return _state["tokens"][key]


def tokens() -> dict:
    return _state["tokens"]


def cat_color(key: str) -> str:
    pair = CAT_COLORS.get(key) or CAT_COLORS["work"]
    return pair[1] if _state["dark"] else pair[0]


def density() -> str:
    return _state["density"]


def compact() -> bool:
    return _state["density"] == "compact"


def font_px() -> int:
    return _state["font_px"]


def ui_families() -> list[str]:
    if sys.platform == "darwin":
        fams = [QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family(), "Hiragino Sans",
                "Hiragino Kaku Gothic ProN"]
    elif sys.platform == "win32":
        fams = ["Segoe UI", "Yu Gothic UI", "Meiryo UI"]
    else:
        fams = ["Noto Sans CJK JP", "Noto Sans JP", "IPAPGothic", "DejaVu Sans"]
    return fams


def mono_family() -> str:
    if sys.platform == "darwin":
        return "Menlo"
    if sys.platform == "win32":
        return "Consolas"
    return "DejaVu Sans Mono"


def make_font(px: int, family: str = "", weight: QFont.Weight | None = None) -> QFont:
    f = QFont()
    fams = ([family] if family else []) + ui_families()
    f.setFamilies(fams)
    f.setPixelSize(px)
    if weight is not None:
        f.setWeight(weight)
    return f


def mono_font(px: int) -> QFont:
    f = QFont()
    f.setFamilies([mono_family()] + ui_families())
    f.setPixelSize(px)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def _asset_dir() -> Path:
    d = config_dir() / "cache"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        import tempfile

        d = Path(tempfile.gettempdir()) / "kinko-cache"
        d.mkdir(parents=True, exist_ok=True)
    return d


def _asset(name: str, color: str, width: float = 2.4) -> str:
    path = _asset_dir() / f"{name}_{color.strip('#')}.svg"
    if not path.exists():
        try:
            path.write_text(icons.svg_markup(name, color, width), encoding="utf-8")
        except OSError:
            pass
    return path.as_posix()


_QSS = Template("""
* { outline: none; }
QWidget { color: $ink; }
QMainWindow, QDialog { background: $paper; }
QDialog#Sheet { background: $paper; }
QWidget#Sidebar { background: $shikkui; border-right: 1px solid $rule; }
QWidget#ListPane { background: $paper2; border-right: 1px solid $rule; }
QWidget#DetailPane, QWidget#DetailBody, QScrollArea#DetailScroll { background: $paper; }
QWidget#SettingsBody { background: $paper; }
QListWidget#SettingsNav { background: $shikkui; border: none; border-right: 1px solid $rule; padding: 10px 8px; }
QListWidget#SettingsNav::item { padding: ${navpad}px 10px; border-radius: 6px; color: $ink; }
QListWidget#SettingsNav::item:selected { background: $ai_tint; color: $ai; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

QLabel { background: transparent; }
QLabel[role="title"] { font-size: ${fs_title}px; font-weight: 700; }
QLabel[role="h1"] { font-size: ${fs_h1}px; font-weight: 700; }
QLabel[role="h2"] { font-size: ${fs_h2}px; font-weight: 700; }
QLabel[role="muted"] { color: $ink2; }
QLabel[role="faint"] { color: $ink3; }
QLabel[role="small"] { color: $ink2; font-size: ${fs_small}px; }
QLabel[role="smallfaint"] { color: $ink3; font-size: ${fs_small}px; }
QLabel[role="fieldkey"] { color: $ink2; font-size: ${fs_key}px; }
QLabel[role="ok"] { color: $tokiwa; font-size: ${fs_small}px; }
QLabel[role="warn"] { color: $kincha; font-size: ${fs_small}px; }
QLabel[role="error"] { color: $bengara; font-size: ${fs_small}px; }
QLabel[role="link"] { color: $ai; }
QLabel[role="pill"] { background: $rule2; color: $ink2; border-radius: 9px; padding: 1px 8px; font-size: ${fs_small}px; }
QLabel[role="pill_ok"] { background: $tokiwa_tint; color: $tokiwa; border-radius: 9px; padding: 1px 8px; font-size: ${fs_small}px; font-weight: 600; }
QLabel[role="pill_warn"] { background: $kincha_tint; color: $kincha; border-radius: 9px; padding: 1px 8px; font-size: ${fs_small}px; font-weight: 600; }
QLabel[role="pill_risk"] { background: $bengara_tint; color: $bengara; border-radius: 9px; padding: 1px 8px; font-size: ${fs_small}px; font-weight: 600; }
QLabel[role="pill_ai"] { background: $ai_tint; color: $ai; border-radius: 9px; padding: 1px 8px; font-size: ${fs_small}px; font-weight: 600; }
QLabel[role="value"] { font-size: ${fs_value}px; }
QLabel[role="mask"] { font-size: ${fs_value}px; letter-spacing: 2px; }
QLabel[role="kbd"] { color: $ink3; border: 1px solid $rule; border-bottom: 2px solid $rule; border-radius: 4px; padding: 1px 5px; font-size: ${fs_tiny}px; background: $paper2; }
QFrame[role="note"], QLabel[role="note"] { background: $field; border: 1px solid $rule2; border-radius: 8px; padding: 8px 12px; }
QFrame[role="hline"] { background: $rule2; border: none; min-height: 1px; max-height: 1px; }
QFrame[role="vline"] { background: $rule; border: none; min-width: 1px; max-width: 1px; }
QFrame#Card { background: $paper; border: 1px solid $rule; border-radius: 12px; }
QFrame#Choice { background: $paper; border: 1px solid $rule; border-radius: 10px; }
QFrame#Choice:hover { border-color: $ai; background: $ai_tint; }
QFrame#Choice:focus { border-color: $ai; }
QFrame#ChoicePrimary { background: $ai; border: 1px solid $ai; border-radius: 10px; }
QFrame#ChoicePrimary:hover { background: $ai_hover; border-color: $ai_hover; }
QFrame#ChoicePrimary:focus { border: 2px solid $ai_line; }
QFrame[role="box"] { background: $paper2; border: 1px solid $rule; border-radius: 8px; }
QFrame[role="banner_warn"] { background: $kincha_tint; border-radius: 8px; }
QFrame[role="banner_risk"] { background: $bengara_tint; border-radius: 8px; }
QFrame[role="banner_info"] { background: $ai_tint; border-radius: 8px; }
QFrame[role="banner_ok"] { background: $tokiwa_tint; border-radius: 8px; }
QLabel[role="banner_warn"] { color: $kincha; }
QLabel[role="banner_risk"] { color: $bengara; }
QLabel[role="banner_info"] { color: $ai; }
QLabel[role="banner_ok"] { color: $tokiwa; }

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QKeySequenceEdit QLineEdit {
    background: $field; border: 1px solid $rule; border-radius: 7px; padding: ${inpad}px 9px;
    selection-background-color: $ai_line; selection-color: $ink; color: $ink;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid $ai; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { color: $ink3; }
QLineEdit[size="large"] { padding: ${inpad_l}px 12px; font-size: ${fs_large}px; }
QLineEdit[role="mono"] { font-family: "$mono"; }
QLineEdit#SearchField { background: $paper; border-radius: 8px; padding: ${inpad_l}px 8px; }
QLineEdit#SearchField:focus { border: 1px solid $ai; }
QLineEdit[role="titleedit"] { font-size: ${fs_h1}px; font-weight: 700; padding: 4px 10px; }
QPlainTextEdit { padding: 6px 8px; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url("$chev_up"); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url("$chev_down"); width: 10px; height: 10px; }
QComboBox { padding-right: 24px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url("$chev_down"); width: 11px; height: 11px; }
QComboBox QAbstractItemView { background: $paper; border: 1px solid $rule; border-radius: 6px; padding: 4px;
    selection-background-color: $ai_tint; selection-color: $ai; outline: none; }
QComboBox[role="flat"] { background: transparent; border: 1px solid transparent; }
QComboBox[role="flat"]:hover { background: $rule2; }

QPushButton { background: $paper; color: $ink; border: 1px solid $rule; border-radius: 7px;
    padding: ${btnpad}px 14px; font-weight: 600; }
QPushButton:hover { background: $rule2; }
QPushButton:pressed { background: $rule; }
QPushButton:disabled { color: $ink3; background: $paper2; }
QPushButton[variant="primary"] { background: $ai; color: $ai_ink; border: 1px solid $ai; }
QPushButton[variant="primary"]:hover { background: $ai_hover; border-color: $ai_hover; }
QPushButton[variant="primary"]:disabled { background: $ai_line; border-color: $ai_line; color: $ai_ink; }
QPushButton[variant="ghost"] { background: transparent; border: 1px solid transparent; color: $ink2; }
QPushButton[variant="ghost"]:hover { background: $rule2; color: $ink; }
QPushButton[variant="danger"] { color: $bengara; }
QPushButton[variant="danger"]:hover { background: $bengara_tint; border-color: $bengara; }
QPushButton[variant="link"] { background: transparent; border: none; color: $ai; padding: 2px 0; font-weight: 500; text-align: left; }
QPushButton[variant="link"]:hover { text-decoration: underline; }
QPushButton[variant="choice"] { text-align: left; padding: 14px 16px; border-radius: 10px; font-size: ${fs_value}px; }
QPushButton[variant="choice"]:hover { border-color: $ai; background: $ai_tint; }
QPushButton[variant="choiceprimary"] { text-align: left; padding: 14px 16px; border-radius: 10px; font-size: ${fs_value}px;
    background: $ai; color: $ai_ink; border: 1px solid $ai; }
QPushButton[variant="choiceprimary"]:hover { background: $ai_hover; }
QPushButton[variant="swatch"] { border-radius: 12px; min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0; border: 2px solid $paper; }
QPushButton[variant="swatch"]:checked { border: 2px solid $ink; }
QPushButton[variant="quick"] { padding: 2px 8px; font-size: ${fs_small}px; font-weight: 500; color: $ink2; }

QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px; color: $ink2; }
QToolButton:hover { background: $rule2; }
QToolButton:pressed { background: $rule; }
QToolButton:checked { background: $ai_tint; }
QToolButton[variant="boxed"] { border: 1px solid $rule; background: $paper; }
QToolButton[variant="boxed"]:hover { background: $rule2; }
QToolButton[variant="done"] { background: $tokiwa_tint; }
QToolButton[variant="seg"] { background: $paper; border: 1px solid $rule; border-radius: 0; padding: 3px 10px; color: $ink2; font-size: ${fs_small}px; }
QToolButton[variant="seg"][pos="first"] { border-top-left-radius: 6px; border-bottom-left-radius: 6px; }
QToolButton[variant="seg"][pos="last"] { border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
QToolButton[variant="seg"]:checked { background: $ai_tint; color: $ai; font-weight: 600; }
QToolButton[variant="text"] { color: $ink2; font-size: ${fs_small}px; padding: 3px 6px; }
QToolButton[variant="text"]::menu-indicator { image: none; width: 0; }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton[variant="iconpick"] { border: 1px solid $rule; background: $paper; padding: 4px; }
QToolButton[variant="iconpick"]:checked { border: 2px solid $ai; background: $ai_tint; }

QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid $ink3; background: $field; }
QCheckBox::indicator:checked { background: $ai; border-color: $ai; image: url("$check"); }
QCheckBox::indicator:disabled { background: $rule2; border-color: $rule; }
QCheckBox[role="switch"]::indicator { width: 32px; height: 18px; border-radius: 9px; border: none; background: $rule; image: url("$knob_off"); }
QCheckBox[role="switch"]::indicator:checked { background: $ai; image: url("$knob_on"); }
QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 1px solid $ink3; background: $field; }
QRadioButton::indicator:checked { border: 5px solid $ai; background: $paper; }

QSlider::groove:horizontal { height: 4px; background: $rule; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ai; border-radius: 2px; }
QSlider::handle:horizontal { background: $paper; border: 2px solid $ai; width: 12px; height: 12px; margin: -6px 0; border-radius: 8px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 1px; }
QScrollBar::handle:vertical { background: $rule; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: $ink3; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: $rule; border-radius: 4px; min-width: 32px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QListView, QListWidget, QTreeWidget, QTableWidget { background: transparent; border: none; }
QListWidget[role="plain"] { background: $paper; border: 1px solid $rule; border-radius: 8px; padding: 4px; }
QListWidget[role="plain"]::item { padding: 6px 8px; border-radius: 5px; }
QListWidget[role="plain"]::item:selected { background: $ai_tint; color: $ai; }
QTableWidget { gridline-color: $rule2; }
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background: $ai_tint; color: $ink; }
QHeaderView::section { background: $paper2; color: $ink2; border: none; border-bottom: 1px solid $rule; padding: 6px 8px; font-weight: 600; }

QMenu { background: $paper; border: 1px solid $rule; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 5px; color: $ink; }
QMenu::item:selected { background: $ai_tint; color: $ai; }
QMenu::item:disabled { color: $ink3; }
QMenu::separator { height: 1px; background: $rule2; margin: 4px 6px; }
QMenu::indicator { width: 14px; height: 14px; }
QToolTip { background: $ink; color: $paper; border: none; padding: 4px 8px; border-radius: 4px; }

QStatusBar { background: $chrome; border-top: 1px solid $rule; color: $ink2; font-size: ${fs_small}px; min-height: 26px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $ink2; font-size: ${fs_small}px; }
QSplitter::handle { background: $rule; }
QSplitter::handle:horizontal { width: 1px; }
QProgressBar { background: $rule2; border: none; border-radius: 3px; height: 6px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $ai; border-radius: 3px; }
QWidget#Toast { background: $ink; border-radius: 9px; }
QWidget#Toast QLabel { color: $paper; }
QWidget#Toast QPushButton { background: transparent; border: none; color: $ai_line; font-weight: 700; padding: 2px 6px; }
QWidget#GeneratorPopup { background: $paper; border: 1px solid $rule; border-radius: 10px; }
""")


def build_qss(tok: dict, px: int, compact_mode: bool) -> str:
    values = dict(tok)
    values.update({
        "fs_title": px + 9, "fs_h1": px + 6, "fs_h2": px + 1, "fs_small": max(px - 2, 10),
        "fs_tiny": max(px - 2, 9), "fs_key": max(px - 1, 10), "fs_value": px + 1, "fs_large": px + 2,
        "inpad": 4 if compact_mode else 6, "inpad_l": 6 if compact_mode else 8,
        "btnpad": 4 if compact_mode else 6, "navpad": 6 if compact_mode else 8,
        "check": _asset("check", tok["ai_ink"], 3.0), "chev_down": _asset("chev_down", tok["ink2"]),
        "chev_up": _asset("chev_up", tok["ink2"]), "knob_on": _knob(tok["ai_ink"]), "knob_off": _knob(tok["paper"], left=True),
        "mono": mono_family(),
    })
    return _QSS.substitute(values)


def _knob(color: str, left: bool = False) -> str:
    path = _asset_dir() / f"knob_{'l' if left else 'r'}_{color.strip('#')}.svg"
    if not path.exists():
        cx = 9 if left else 23
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 18">'
                        f'<circle cx="{cx}" cy="9" r="7" fill="{color}"/></svg>', encoding="utf-8")
    return path.as_posix()


def apply(app, settings) -> None:
    mode = settings["theme"]
    dark = system_is_dark() if mode == "system" else mode == "dark"
    tok = resolve(dark, settings["accent"])
    px = int(settings["font_px"] or 13)
    _state.update(tokens=tok, dark=dark, density=settings["density"], font_px=px)
    icons.clear_cache()

    app.setFont(make_font(px, settings["font_family"]))
    pal = QPalette()
    roles = QPalette.ColorRole
    pal.setColor(roles.Window, QColor(tok["paper"]))
    pal.setColor(roles.WindowText, QColor(tok["ink"]))
    pal.setColor(roles.Base, QColor(tok["field"]))
    pal.setColor(roles.AlternateBase, QColor(tok["paper2"]))
    pal.setColor(roles.ToolTipBase, QColor(tok["ink"]))
    pal.setColor(roles.ToolTipText, QColor(tok["paper"]))
    pal.setColor(roles.Text, QColor(tok["ink"]))
    pal.setColor(roles.Button, QColor(tok["paper"]))
    pal.setColor(roles.ButtonText, QColor(tok["ink"]))
    pal.setColor(roles.BrightText, QColor(tok["bengara"]))
    pal.setColor(roles.Highlight, QColor(tok["ai"]))
    pal.setColor(roles.HighlightedText, QColor(tok["ai_ink"]))
    pal.setColor(roles.PlaceholderText, QColor(tok["ink3"]))
    pal.setColor(roles.Link, QColor(tok["ai"]))
    pal.setColor(roles.Light, QColor(tok["paper"]))
    pal.setColor(roles.Midlight, QColor(tok["rule2"]))
    pal.setColor(roles.Mid, QColor(tok["rule"]))
    pal.setColor(roles.Dark, QColor(tok["ink3"]))
    pal.setColor(roles.Shadow, QColor(tok["shadow"]))
    app.setPalette(pal)
    app.setStyleSheet(build_qss(tok, px, settings["density"] == "compact"))
