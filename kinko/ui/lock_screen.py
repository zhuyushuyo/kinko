"""Lock screen and welcome screen, drawn over a quiet safe-dial backdrop."""
from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QSizePolicy, QVBoxLayout, QWidget)

from ..i18n import tr
from . import icons, native, theme
from .widgets import button, label, set_tool_icon, tool


class Backdrop(QWidget):
    """Plaster background with a large, faint combination-dial ring behind the card."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("Card")
        self.card.setFixedWidth(420)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 10)
        c = QColor(theme.t("shadow"))
        c.setAlphaF(0.35 if theme.is_dark() else 0.10)
        shadow.setColor(c)
        self.card.setGraphicsEffect(shadow)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(32, 30, 32, 26)
        self.body.setSpacing(0)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.t("shikkui")))
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        r = max(min(w, h) * 0.56, 330)
        ring = QColor(theme.t("rule"))
        tick = QColor(theme.t("ink3"))
        tick.setAlphaF(0.35)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, 1.2))
        p.drawEllipse(c, r, r)
        p.drawEllipse(c, r * 0.83, r * 0.83)
        for i in range(100):
            a = i * 2 * math.pi / 100 - math.pi / 2
            major, mid = i % 10 == 0, i % 5 == 0
            inner = r * 0.865
            outer = r * (0.955 if major else 0.925 if mid else 0.905)
            p.setPen(QPen(tick, 1.8 if major else 1.0))
            p.drawLine(QPointF(c.x() + math.cos(a) * inner, c.y() + math.sin(a) * inner),
                       QPointF(c.x() + math.cos(a) * outer, c.y() + math.sin(a) * outer))
        f = QFont(self.font())
        f.setPixelSize(12)
        p.setFont(f)
        num = QColor(theme.t("ink3"))
        num.setAlphaF(0.55)
        p.setPen(num)
        for k in range(10):
            a = k * 2 * math.pi / 10 - math.pi / 2
            pos = QPointF(c.x() + math.cos(a) * r * 0.765, c.y() + math.sin(a) * r * 0.765)
            p.drawText(QRectF(pos.x() - 16, pos.y() - 9, 32, 18), Qt.AlignmentFlag.AlignCenter, str(k * 10))
        # the index mark at the top of the dial
        mark = QColor(theme.t("ai"))
        mark.setAlphaF(0.55)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mark)
        top = c.y() - r * 1.0
        p.drawPolygon(QPointF(c.x() - 7, top - 12), QPointF(c.x() + 7, top - 12), QPointF(c.x(), top - 1))


def brand_row() -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    mark = QLabel()
    mark.setPixmap(icons.mark_pixmap(44, theme.t("mark_bg"), theme.t("mark_fg")))
    row.addWidget(mark)
    col = QVBoxLayout()
    col.setSpacing(2)
    wm = QLabel("KINKO")
    f = theme.make_font(24, weight=QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 118)
    wm.setFont(f)
    col.addWidget(wm)
    col.addWidget(label(tr("app.tagline"), "muted"))
    row.addLayout(col)
    row.addStretch(1)
    return row


class PasswordBox(QWidget):
    """Large password field with show/hide and a Caps Lock warning."""

    submitted = pyqtSignal()

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setProperty("size", "large")
        self.edit.setPlaceholderText(placeholder)
        self.edit.returnPressed.connect(self.submitted)
        self.edit.installEventFilter(self)
        row.addWidget(self.edit, 1)
        self.eye = tool("eye", tr("action.show"), self._toggle, 18, variant="boxed", checkable=True)
        self.eye.setFixedSize(42, 42)
        row.addWidget(self.eye)
        lay.addLayout(row)
        self.caps = QLabel()
        self.caps.setProperty("role", "warn")
        self.caps.setText(tr("lock.capslock"))
        self.caps.setVisible(False)
        lay.addWidget(self.caps)

    def _toggle(self) -> None:
        hidden = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        set_tool_icon(self.eye, "eye_off" if hidden else "eye", size=18)

    def eventFilter(self, obj, ev):  # noqa: N802
        if ev.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.FocusIn):
            self.caps.setVisible(native.caps_lock_on())
        elif ev.type() == QEvent.Type.FocusOut:
            self.caps.setVisible(False)
        return False

    def text(self) -> str:
        return self.edit.text()

    def clear(self) -> None:
        self.edit.clear()

    def focus(self) -> None:
        self.edit.setFocus()


class LockScreen(Backdrop):
    unlock_requested = pyqtSignal(str)
    recovery_requested = pyqtSignal()
    switch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        b = self.body
        b.addLayout(brand_row())
        b.addSpacing(22)

        box = QFrame()
        box.setProperty("role", "box")
        bl = QHBoxLayout(box)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("folder", theme.t("ink2"), 18))
        bl.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.vault_name = label("", None)
        f = self.vault_name.font()
        f.setWeight(QFont.Weight.DemiBold)
        self.vault_name.setFont(f)
        self.vault_path = label("", "smallfaint")
        self.vault_path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        col.addWidget(self.vault_name)
        col.addWidget(self.vault_path)
        bl.addLayout(col, 1)
        switch = button(tr("lock.other_vault"), "link", slot=self.switch_requested.emit)
        bl.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)
        b.addWidget(box)
        b.addSpacing(18)

        b.addWidget(label(tr("lock.master_password"), "muted"))
        b.addSpacing(6)
        self.pw = PasswordBox()
        self.pw.submitted.connect(self._submit)
        b.addWidget(self.pw)
        self.error = label("", "error", wrap=True)
        self.error.setVisible(False)
        b.addSpacing(4)
        b.addWidget(self.error)
        b.addSpacing(12)
        self.unlock_btn = button(tr("lock.unlock"), "primary", slot=self._submit)
        self.unlock_btn.setMinimumHeight(40)
        b.addWidget(self.unlock_btn)
        b.addSpacing(12)
        links = QHBoxLayout()
        self.hint_btn = button(tr("lock.show_hint"), "link", slot=self._toggle_hint)
        links.addWidget(self.hint_btn)
        links.addStretch(1)
        links.addWidget(button(tr("lock.use_recovery"), "link", slot=self.recovery_requested.emit))
        b.addLayout(links)
        self.hint = label("", "pill_ai", wrap=True)
        self.hint.setVisible(False)
        b.addSpacing(6)
        b.addWidget(self.hint)
        self._hint_text = ""

    def set_vault(self, name: str, path: Path, hint: str) -> None:
        self.vault_name.setText(name)
        p = str(path)
        fm = self.vault_path.fontMetrics()
        self.vault_path.setText(fm.elidedText(p, Qt.TextElideMode.ElideMiddle, 250))
        self.vault_path.setToolTip(p)
        self._hint_text = hint
        self.hint.setVisible(False)
        self.hint_btn.setText(tr("lock.show_hint"))
        self.error.setVisible(False)
        self.pw.clear()

    def _toggle_hint(self) -> None:
        showing = not self.hint.isVisible()
        self.hint.setText(self._hint_text or tr("lock.no_hint"))
        self.hint.setVisible(showing)
        self.hint_btn.setText(tr("lock.hide_hint") if showing else tr("lock.show_hint"))

    def _submit(self) -> None:
        if not self.pw.text():
            self.show_error(tr("lock.empty"))
            return
        self.unlock_requested.emit(self.pw.text())

    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(True)
        self.pw.edit.selectAll()
        self.pw.focus()

    def set_busy(self, busy: bool) -> None:
        self.unlock_btn.setEnabled(not busy)
        self.unlock_btn.setText(tr("lock.unlocking") if busy else tr("lock.unlock"))

    def focus(self) -> None:
        self.pw.focus()

    def showEvent(self, e):  # noqa: N802
        super().showEvent(e)
        self.pw.focus()


class ChoiceButton(QFrame):
    """A large option card; grows with its (wrapped) description."""

    clicked = pyqtSignal()

    def __init__(self, title: str, desc: str, primary: bool = False, icon_name: str = "chev_right", parent=None):
        super().__init__(parent)
        self.setObjectName("ChoicePrimary" if primary else "Choice")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        f = t.font()
        f.setWeight(QFont.Weight.Bold)
        f.setPixelSize(theme.font_px() + 1)
        t.setFont(f)
        d = QLabel(desc)
        d.setWordWrap(True)
        fg = theme.t("btn_ink") if primary else theme.t("ink")
        sub = theme.t("btn_ink") if primary else theme.t("ink2")
        t.setStyleSheet(f"color: {fg}; background: transparent;")
        d.setStyleSheet(f"color: {sub}; background: transparent; font-size: {theme.font_px() - 1}px;")
        for w in (t, d):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        col.addWidget(t)
        col.addWidget(d)
        lay.addLayout(col, 1)
        arrow = QLabel()
        arrow.setPixmap(icons.pixmap(icon_name, fg, 16))
        arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(arrow)

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(e)


class WelcomeScreen(Backdrop):
    create_requested = pyqtSignal()
    migrate_requested = pyqtSignal()
    open_requested = pyqtSignal()
    recent_requested = pyqtSignal(str)

    def __init__(self, recent: list[str], has_v2: bool, parent=None):
        super().__init__(parent)
        self.card.setFixedWidth(460)
        b = self.body
        b.addLayout(brand_row())
        b.addSpacing(18)
        b.addWidget(label(tr("welcome.lead"), "muted", wrap=True))
        b.addSpacing(16)
        recent = [p for p in recent if Path(p).is_file()]
        if recent:
            b.addWidget(label(tr("welcome.recent"), "smallfaint"))
            b.addSpacing(4)
            for p in recent[:3]:
                btn = button(Path(p).name, "ghost", "folder", slot=lambda _=False, path=p: self.recent_requested.emit(path))
                btn.setToolTip(p)
                btn.setStyleSheet("text-align: left;")
                b.addWidget(btn)
            b.addSpacing(12)
        mig = ChoiceButton(tr("welcome.migrate"), tr("welcome.migrate_desc"), primary=has_v2)
        mig.clicked.connect(self.migrate_requested)
        new = ChoiceButton(tr("welcome.create"), tr("welcome.create_desc"), primary=not has_v2)
        new.clicked.connect(self.create_requested)
        opn = ChoiceButton(tr("welcome.open"), tr("welcome.open_desc"))
        opn.clicked.connect(self.open_requested)
        for w in (mig, new, opn):
            b.addWidget(w)
            b.addSpacing(8)


def vault_menu(parent, recent: list[str], current: str, on_open_path, on_open, on_create, on_migrate) -> QMenu:
    m = QMenu(parent)
    for p in recent:
        if p == current or not Path(p).is_file():
            continue
        m.addAction(Path(p).name, lambda path=p: on_open_path(path)).setToolTip(p)
    if m.actions():
        m.addSeparator()
    m.addAction(tr("menu.open_vault"), on_open)
    m.addAction(tr("menu.create_vault"), on_create)
    m.addAction(tr("menu.migrate"), on_migrate)
    return m
