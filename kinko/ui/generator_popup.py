"""Password generator popup. The choices made here become the new defaults (settings.json)."""
from __future__ import annotations

import html

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QSlider, QSpinBox,
                             QStackedWidget, QVBoxLayout, QWidget)

from ..i18n import tr
from ..services import generator
from ..services.strength import estimate
from . import theme
from .widgets import Segmented, StrengthMeter, button, label, tool

SEPARATORS = [("-", "-"), ("_", "_"), (".", "."), (" ", "space"), ("", "none")]


def colorize(pw: str) -> str:
    out = []
    for ch in pw:
        e = html.escape(ch)
        if ch.isdigit():
            out.append(f'<span style="color:{theme.t("ai")}">{e}</span>')
        elif not ch.isalnum():
            out.append(f'<span style="color:{theme.t("bengara")}">{e if ch != " " else "&nbsp;"}</span>')
        else:
            out.append(e)
    return "".join(out)


class GeneratorPopup(QFrame):
    use = pyqtSignal(str)

    def __init__(self, settings, mode: str | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("GeneratorPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings = settings
        self.opts = dict(settings["generator"])
        if mode:
            self.opts["mode"] = mode
        self.setFixedWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(label(tr("gen.title"), "h2"))
        self.seg = Segmented([("random", tr("gen.random")), ("words", tr("gen.words")), ("pin", tr("gen.pin"))],
                             self.opts["mode"])
        self.seg.changed.connect(self._mode)
        lay.addWidget(self.seg)

        prev = QFrame()
        prev.setProperty("role", "note")
        pl = QHBoxLayout(prev)
        pl.setContentsMargins(12, 8, 6, 8)
        self.preview = QLabel()
        self.preview.setTextFormat(Qt.TextFormat.RichText)
        self.preview.setFont(theme.mono_font(theme.font_px() + 4))
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setWordWrap(True)
        pl.addWidget(self.preview, 1)
        pl.addWidget(tool("refresh", tr("gen.again"), self.regenerate, 17))
        lay.addWidget(prev)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._page_random())
        self.pages.addWidget(self._page_words())
        self.pages.addWidget(self._page_pin())
        lay.addWidget(self.pages)

        srow = QHBoxLayout()
        self.meter = StrengthMeter()
        srow.addWidget(self.meter)
        self.meter_label = label("", "small")
        srow.addWidget(self.meter_label)
        srow.addStretch(1)
        lay.addLayout(srow)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(button(tr("common.close"), slot=self.close))
        btns.addWidget(button(tr("gen.use"), "primary", slot=self._use))
        lay.addLayout(btns)
        self._mode(self.opts["mode"], save=False)

    # ---------------------------------------------------------------- pages
    def _page_random(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(6)
        row = QHBoxLayout()
        row.addWidget(label(tr("gen.length"), "small"))
        self.len_slider = QSlider(Qt.Orientation.Horizontal)
        self.len_slider.setRange(8, 64)
        self.len_slider.setValue(int(self.opts["length"]))
        self.len_value = label(str(self.opts["length"]), None)
        self.len_value.setFixedWidth(26)
        self.len_slider.valueChanged.connect(lambda v: (self.len_value.setText(str(v)), self._set("length", v)))
        row.addWidget(self.len_slider, 1)
        row.addWidget(self.len_value)
        g.addLayout(row, 0, 0, 1, 2)
        checks = [("upper", tr("gen.upper")), ("digits", tr("gen.digits")), ("symbols", tr("gen.symbols")),
                  ("lower", tr("gen.lower"))]
        for i, (key, text) in enumerate(checks):
            cb = QCheckBox(text)
            cb.setChecked(bool(self.opts[key]))
            cb.toggled.connect(lambda v, k=key: self._set(k, v))
            g.addWidget(cb, 1 + i // 2, i % 2)
        amb = QCheckBox(tr("gen.avoid_ambiguous"))
        amb.setChecked(bool(self.opts["avoid_ambiguous"]))
        amb.toggled.connect(lambda v: self._set("avoid_ambiguous", v))
        g.addWidget(amb, 3, 0, 1, 2)
        return w

    def _page_words(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(6)
        g.addWidget(label(tr("gen.word_count"), "small"), 0, 0)
        spin = QSpinBox()
        spin.setRange(3, 8)
        spin.setValue(int(self.opts["words"]))
        spin.valueChanged.connect(lambda v: self._set("words", v))
        g.addWidget(spin, 0, 1)
        g.addWidget(label(tr("gen.separator"), "small"), 1, 0)
        sep = QComboBox()
        for value, text in SEPARATORS:
            sep.addItem(tr(f"gen.sep_{text}") if text in ("space", "none") else text, value)
        idx = max(0, sep.findData(self.opts["separator"]))
        sep.setCurrentIndex(idx)
        sep.currentIndexChanged.connect(lambda _: self._set("separator", sep.currentData()))
        g.addWidget(sep, 1, 1)
        cap = QCheckBox(tr("gen.capitalize"))
        cap.setChecked(bool(self.opts["capitalize"]))
        cap.toggled.connect(lambda v: self._set("capitalize", v))
        g.addWidget(cap, 2, 0)
        dig = QCheckBox(tr("gen.word_digit"))
        dig.setChecked(bool(self.opts["word_digit"]))
        dig.toggled.connect(lambda v: self._set("word_digit", v))
        g.addWidget(dig, 2, 1)
        g.addWidget(label(tr("gen.words_note"), "smallfaint", wrap=True), 3, 0, 1, 2)
        return w

    def _page_pin(self) -> QWidget:
        w = QWidget()
        g = QHBoxLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.addWidget(label(tr("gen.pin_length"), "small"))
        spin = QSpinBox()
        spin.setRange(4, 12)
        spin.setValue(int(self.opts["pin_length"]))
        spin.valueChanged.connect(lambda v: self._set("pin_length", v))
        g.addWidget(spin)
        g.addStretch(1)
        return w

    # ---------------------------------------------------------------- logic
    def _mode(self, mode: str, save: bool = True) -> None:
        self.opts["mode"] = mode
        self.pages.setCurrentIndex({"random": 0, "words": 1, "pin": 2}[mode])
        if save:
            self._save()
        self.regenerate()

    def _set(self, key: str, value) -> None:
        self.opts[key] = value
        self._save()
        self.regenerate()

    def _save(self) -> None:
        merged = dict(self.settings["generator"])
        merged.update(self.opts)
        self.settings.set("generator", merged)

    def regenerate(self) -> None:
        self.value = generator.generate(self.opts)
        self.preview.setText(colorize(self.value))
        st = estimate(self.value)
        self.meter.set_score(st.score)
        self.meter_label.setText(f"{tr(st.label_key)}（{tr('common.chars', n=len(self.value))}）")

    def _use(self) -> None:
        self.use.emit(self.value)
        self.close()

    def popup_under(self, widget: QWidget) -> None:
        self.adjustSize()
        pos = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        screen = widget.screen().availableGeometry() if widget.screen() else None
        x, y = pos.x(), pos.y()
        if screen is not None:
            x = min(x, screen.right() - self.width() - 8)
            if y + self.height() > screen.bottom():
                y = widget.mapToGlobal(QPoint(0, 0)).y() - self.height() - 4
        self.move(x, y)
        self.show()
