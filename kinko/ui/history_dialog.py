"""Past values of secret fields (passwords, PINs, ...), newest first."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..core.model import BUILTIN_FIELDS
from ..i18n import tr
from . import theme
from .formatting import fmt_date
from .item_detail import mask
from .widgets import button, hline, label, set_tool_icon, tool


class HistoryDialog(QDialog):
    def __init__(self, parent, vault, iid: str, copy_cb):
        super().__init__(parent)
        rec = vault.items[iid]
        self.setWindowTitle(tr("history.title"))
        self.setMinimumSize(560, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(8)
        lay.addWidget(label(tr("history.heading", title=rec.data.get("title", "")), "h1"))
        lay.addWidget(label(tr("history.lead"), "muted", wrap=True))
        lay.addWidget(hline())
        entries = vault.secret_history(iid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 6, 0, 6)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        if not entries:
            grid.addWidget(label(tr("history.none"), "muted"), 0, 0)
        for i, e in enumerate(entries):
            key = e.get("field", "")
            name = e.get("label") or (tr(BUILTIN_FIELDS[key][1]) if key in BUILTIN_FIELDS else key)
            when = fmt_date(e.get("changed_at"), with_time=True)
            if e.get("note") == "v2":
                when = tr("history.from_v2", d=fmt_date(e.get("changed_at")))
            grid.addWidget(label(name, "fieldkey"), i, 0)
            val = label(mask(e.get("value", "")), "mask")
            grid.addWidget(val, i, 1)
            eye = tool("eye", tr("action.show"), None, 16)
            eye.clicked.connect(lambda _=False, lb=val, v=e.get("value", ""), b=eye: self._reveal(lb, v, b))
            grid.addWidget(eye, i, 2)
            grid.addWidget(tool("copy", tr("action.copy"),
                                lambda _=False, v=e.get("value", ""), n=name: copy_cb(v, n), 16), i, 3)
            grid.addWidget(label(tr("history.replaced", d=when), "smallfaint"), i, 4)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(entries) + 1, 1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("common.close"), "primary", slot=self.accept))
        lay.addLayout(row)

    def _reveal(self, lb, value, btn) -> None:
        if lb.text().startswith("•"):
            lb.setText(value)
            lb.setFont(theme.mono_font(theme.font_px() + 1))
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            set_tool_icon(btn, "eye_off", size=16)
        else:
            lb.setText(mask(value))
            set_tool_icon(btn, "eye", size=16)
