"""Shared widgets: labels with roles, avatar, strength meter, password field, segmented control, toast."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PyQt6.QtWidgets import (QCheckBox, QCompleter, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr
from . import icons, theme


def repolish(w: QWidget) -> None:
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


def set_role(w: QWidget, role: str) -> QWidget:
    w.setProperty("role", role)
    repolish(w)
    return w


def set_variant(w: QWidget, variant: str) -> QWidget:
    w.setProperty("variant", variant)
    repolish(w)
    return w


def label(text: str = "", role: str | None = None, wrap: bool = False, selectable: bool = False) -> QLabel:
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    if wrap:
        lb.setWordWrap(True)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lb


def hline() -> QFrame:
    f = QFrame()
    f.setProperty("role", "hline")
    f.setFixedHeight(1)
    return f


def button(text: str, variant: str | None = None, icon_name: str | None = None, slot=None) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if icon_name:
        color = theme.t("ai_ink") if variant == "primary" else theme.t("ink2")
        b.setIcon(icons.icon(icon_name, color, 16))
        b.setIconSize(QSize(15, 15))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def tool(icon_name: str, tooltip: str = "", slot=None, size: int = 17, variant: str | None = None,
         color: str | None = None, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setIcon(icons.icon(icon_name, color or theme.t("ink2"), size, active_color=theme.t("ai")))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setCheckable(checkable)
    b.setAutoRaise(True)
    if variant:
        b.setProperty("variant", variant)
    if slot:
        b.clicked.connect(slot)
    return b


def set_tool_icon(b: QToolButton, icon_name: str, color: str | None = None, size: int = 17) -> None:
    b.setIcon(icons.icon(icon_name, color or theme.t("ink2"), size, active_color=theme.t("ai")))


class Avatar(QWidget):
    def __init__(self, letter: str = "?", color: str = "#5B636D", size: int = 34, muted: bool = False, parent=None):
        super().__init__(parent)
        self._letter, self._color, self._muted = letter, color, muted
        self.setFixedSize(size, size)

    def set(self, letter: str, color: str, muted: bool = False) -> None:
        self._letter, self._color, self._muted = letter, color, muted
        self.update()

    def paintEvent(self, _):  # noqa: N802
        paint_avatar(QPainter(self), QRectF(0, 0, self.width(), self.height()), self._letter, self._color, self._muted)


def paint_avatar(p: QPainter, rect: QRectF, letter: str, color: str, muted: bool = False) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(theme.t("ink3") if muted else color)
    bg = QColor(c)
    bg.setAlphaF(0.16 if theme.is_dark() else 0.13)
    path = QPainterPath()
    radius = rect.width() * 0.24
    path.addRoundedRect(rect, radius, radius)
    p.fillPath(path, bg)
    f = QFont(p.font())
    f.setPixelSize(int(rect.height() * 0.42))
    f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    p.setPen(c)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)


class StrengthMeter(QWidget):
    """Four short bars. score 0-4."""

    def __init__(self, score: int = 0, parent=None, bar_w: int = 22):
        super().__init__(parent)
        self._score = score
        self._bar_w = bar_w
        self.setFixedSize(bar_w * 4 + 9, 8)

    def set_score(self, score: int | None) -> None:
        self._score = score
        self.update()

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        score = self._score
        bars = 0 if score is None else (1, 1, 2, 3, 4)[score]
        color = theme.t("bengara") if score is not None and score <= 1 else (
            theme.t("kincha") if score == 2 else theme.t("tokiwa"))
        for i in range(4):
            r = QRectF(i * (self._bar_w + 3), 2, self._bar_w, 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color if i < bars else theme.t("rule")))
            p.drawRoundedRect(r, 2, 2)


def strength_color(score: int) -> str:
    if score <= 1:
        return theme.t("bengara")
    if score == 2:
        return theme.t("kincha")
    return theme.t("tokiwa")


class SecretEdit(QWidget):
    """Line edit for secrets with show/hide and an optional generator button."""

    generate_clicked = pyqtSignal()
    textChanged = pyqtSignal(str)

    def __init__(self, generator: bool = True, placeholder: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.textChanged)
        lay.addWidget(self.edit, 1)
        self.eye = tool("eye", tr("action.show"), self.toggle, 16, checkable=True)
        lay.addWidget(self.eye)
        self.gen = None
        if generator:
            self.gen = tool("key", tr("action.generate"), self.generate_clicked.emit, 16)
            lay.addWidget(self.gen)

    def toggle(self) -> None:
        shown = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        set_tool_icon(self.eye, "eye_off" if shown else "eye", size=16)
        self.eye.setChecked(shown)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str) -> None:  # noqa: N802
        self.edit.setText(text)

    def setFocus(self) -> None:  # noqa: N802
        self.edit.setFocus()


class Segmented(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], value: str | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.buttons: dict[str, QToolButton] = {}
        for i, (val, text) in enumerate(options):
            b = QToolButton()
            b.setText(text)
            b.setCheckable(True)
            b.setProperty("variant", "seg")
            b.setProperty("pos", "first" if i == 0 else ("last" if i == len(options) - 1 else "mid"))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=val: self.set_value(v, emit=True))
            lay.addWidget(b)
            self.buttons[val] = b
        lay.addStretch(1)
        self._value = None
        self.set_value(value if value is not None else options[0][0])

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = False) -> None:
        self._value = value
        for v, b in self.buttons.items():
            b.setChecked(v == value)
        if emit:
            self.changed.emit(value)

    def set_text(self, value: str, text: str) -> None:
        if value in self.buttons:
            self.buttons[value].setText(text)


class Switch(QCheckBox):
    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(text, parent)
        self.setProperty("role", "switch")
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Banner(QFrame):
    def __init__(self, kind: str, text: str, icon_name: str = "alert", parent=None):
        super().__init__(parent)
        self.setProperty("role", f"banner_{kind}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)
        color = {"warn": "kincha", "risk": "bengara", "info": "ai", "ok": "tokiwa"}[kind]
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.t(color), 16))
        ic.setFixedWidth(18)
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        self.text = label(text, f"banner_{kind}", wrap=True)
        lay.addWidget(self.text, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        lay.addLayout(self.actions)

    def add_button(self, text: str, slot, variant: str | None = None) -> QPushButton:
        b = button(text, variant, slot=slot)
        self.actions.addWidget(b)
        return b


class TagEdit(QLineEdit):
    """Comma separated tags with completion of existing tags."""

    def __init__(self, existing: list[str], parent=None):
        super().__init__(parent)
        self.setPlaceholderText(tr("editor.tags_placeholder"))
        self._existing = sorted(existing)
        comp = QCompleter(self._existing, self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.activated.connect(self._insert)
        self._comp = comp
        self.textEdited.connect(self._update_prefix)

    def _update_prefix(self, text: str) -> None:
        part = text.split(",")[-1].split("、")[-1].strip()
        self._comp.setCompletionPrefix(part)
        if part:
            self._comp.complete()

    def _insert(self, value: str) -> None:
        parts = [p.strip() for p in self.text().replace("、", ",").split(",")]
        parts = parts[:-1] + [value]
        self.setText(", ".join(p for p in parts if p) + ", ")

    def tags(self) -> list[str]:
        out = []
        for p in self.text().replace("、", ",").split(","):
            p = p.strip()
            if p and p not in out:
                out.append(p)
        return out

    def set_tags(self, tags: list[str]) -> None:
        self.setText(", ".join(tags))


class Toast(QWidget):
    """Message strip at the bottom of the window, with an optional action."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(10)
        self.text = QLabel()
        lay.addWidget(self.text)
        self.action = QPushButton()
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self._run)
        lay.addWidget(self.action)
        self._callback = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, action: str | None = None, callback=None, ms: int = 4000) -> None:
        self.text.setText(text)
        self._callback = callback
        self.action.setVisible(bool(action))
        self.action.setText(action or "")
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def reposition(self) -> None:
        par = self.parentWidget()
        if not par:
            return
        self.adjustSize()
        x = (par.width() - self.width()) // 2
        y = par.height() - self.height() - 44
        self.move(QPoint(max(x, 8), max(y, 8)))

    def _run(self) -> None:
        cb = self._callback
        self.hide()
        if cb:
            cb()


def elide(text: str, font: QFont, width: int) -> str:
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, max(width, 10))


def vbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if isinstance(w, int):
            lay.addSpacing(w)
        elif w is None:
            lay.addStretch(1)
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return lay


def hbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if isinstance(w, int):
            lay.addSpacing(w)
        elif w is None:
            lay.addStretch(1)
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return lay


def expanding(w: QWidget) -> QWidget:
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return w


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)
