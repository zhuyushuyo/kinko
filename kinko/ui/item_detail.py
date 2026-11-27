"""Right pane, read mode: each field with show / copy / open, password strength and age, issues."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy,
                             QToolButton, QVBoxLayout, QWidget)

from ..core.model import category_path, closed_label, find_category, first_letter, item_fields, twofa_state
from ..i18n import tr
from ..services.index import OLD_DAYS
from . import icons, theme
from .formatting import fmt_age, fmt_date, fmt_relative_day, months_between
from .widgets import (Avatar, Banner, ClickableLabel, StrengthMeter, button, hline, label, set_tool_icon,
                      set_variant, tool)

MASK = "•"


def mask(value: str) -> str:
    return MASK * max(4, min(len(value), 16))


class DetailView(QWidget):
    edit_requested = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str, bool)
    trash_requested = pyqtSignal(str)
    restore_requested = pyqtSignal(str)
    purge_requested = pyqtSignal(str)
    duplicate_requested = pyqtSignal(str)  # another account for the same service
    new_requested = pyqtSignal()
    copy_requested = pyqtSignal(str, str, str, str)  # item id, field key, value, label
    open_url_requested = pyqtSignal(str, str)
    history_requested = pyqtSignal(str)

    def __init__(self, settings, trash_days_getter, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailBody")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings = settings
        self._trash_days = trash_days_getter
        self.iid: str | None = None
        self._rows: dict[str, dict] = {}
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self._content: QWidget | None = None

    # ---------------------------------------------------------------- build
    def show_item(self, vault, index, iid: str) -> None:
        self.iid = iid
        self._rows = {}
        if self._content is not None:
            self._outer.removeWidget(self._content)
            self._content.hide()
            self._content.setParent(None)
            self._content.deleteLater()
        self._content = QWidget()
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._outer.addWidget(self._content)

        rec = vault.items[iid]
        d = rec.data
        cfg = vault.config
        cat = find_category(cfg, d["category"])
        color = theme.cat_color(cat.get("color", "work")) if cat else theme.t("ink3")
        closed = d["status"] == "closed"

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(28, 20, 24, 16)
        hl.setSpacing(14)
        hl.addWidget(Avatar(first_letter(d.get("title", "")), color, 48, muted=closed or rec.trashed),
                     0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(6)
        title = label(d.get("title", ""), "h1", wrap=True, selectable=True)
        col.addWidget(title)
        pills = QHBoxLayout()
        pills.setSpacing(6)
        cat_pill = QLabel(category_path(cfg, d))
        cat_pill.setStyleSheet(f"background: {_tint(color)}; color: {color}; border-radius: 9px; padding: 1px 9px;"
                               f" font-weight: 600; font-size: {theme.font_px() - 1}px;")
        pills.addWidget(cat_pill)
        if closed:
            pills.addWidget(label(closed_label(cfg, d), "pill"))
        sf = None if rec.trashed else index.safety.get(iid)
        if sf is not None:
            pill = label(tr(f"safety.level.{sf.level}"), {"high": "pill_ok", "mid": "pill_warn", "low": "pill_risk"}[sf.level])
            pills.addWidget(pill)
        for tag in d.get("tags", []):
            pills.addWidget(label("#" + tag, "pill"))
        pills.addStretch(1)
        col.addLayout(pills)
        hl.addLayout(col, 1)
        if not rec.trashed:
            fav = tool("star_fill" if d.get("favorite") else "star", tr("detail.favorite"), None, 18,
                       color=theme.t("kincha") if d.get("favorite") else theme.t("ink3"))
            fav.clicked.connect(lambda: self.favorite_toggled.emit(iid, not d.get("favorite")))
            hl.addWidget(fav, 0, Qt.AlignmentFlag.AlignTop)
            edit = button(tr("detail.edit"), None, "pen", slot=lambda: self.edit_requested.emit(iid))
            hl.addWidget(edit, 0, Qt.AlignmentFlag.AlignTop)
            more = tool("more", tr("detail.more"), None, 18, variant="boxed")
            more.setFixedSize(34, 34)
            more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            m = QMenu(more)
            m.setToolTipsVisible(True)
            m.addAction(icons.icon("plus", theme.t("ink2"), 16), tr("detail.new"), self.new_requested.emit)
            same = m.addAction(tr("detail.duplicate"), lambda: self.duplicate_requested.emit(iid))
            same.setToolTip(tr("detail.duplicate_tip"))
            m.addSeparator()
            m.addAction(tr("detail.history"), lambda: self.history_requested.emit(iid))
            m.addSeparator()
            m.addAction(tr("detail.to_trash"), lambda: self.trash_requested.emit(iid))
            more.setMenu(m)
            hl.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(head)
        lay.addWidget(hline())

        scroll = QScrollArea()
        scroll.setObjectName("DetailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DetailBody")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 14, 24, 18)
        bl.setSpacing(10)

        if rec.trashed:
            days = self._trash_days()
            banner = Banner("info", tr("detail.trash_banner", days=days), "trash")
            banner.add_button(tr("detail.restore"), lambda: self.restore_requested.emit(iid), "primary")
            banner.add_button(tr("detail.purge"), lambda: self.purge_requested.emit(iid), "danger")
            bl.addWidget(banner)
        elif sf is not None:
            bl.addWidget(SafetyBox(sf))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(0)
        grid.setColumnMinimumWidth(0, 132)
        grid.setColumnStretch(1, 1)
        row = 0
        try:
            history = vault.secret_history(iid)
        except Exception:  # noqa: BLE001
            history = []
        for f in item_fields(cfg, d):
            row = self._add_field(grid, row, iid, f, d["fields"].get(f["key"]), d, history, index)
        bl.addLayout(grid)
        bl.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(28, 8, 24, 12)
        foot.setSpacing(18)
        foot.addWidget(label(tr("detail.created", d=fmt_date(rec.created_at)), "smallfaint"))
        foot.addWidget(label(tr("detail.updated", d=fmt_date(rec.updated_at)), "smallfaint"))
        foot.addWidget(label(tr("detail.used", d=fmt_relative_day(rec.used_at)), "smallfaint"))
        foot.addStretch(1)
        lay.addLayout(foot)

    def _sep(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(hline(), row, 0, 1, 3)
        return row + 1

    def _key(self, text: str) -> QLabel:
        k = label(text, "fieldkey", wrap=True)
        k.setFixedWidth(140)
        k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return k

    def _add_field(self, grid, row, iid, f, value, d, history, index) -> int:
        key, ftype, lab = f["key"], f["type"], f["label"]
        actions = QHBoxLayout()
        actions.setSpacing(2)
        cell = QVBoxLayout()
        cell.setContentsMargins(0, 10, 0, 10)
        cell.setSpacing(6)
        valrow = QHBoxLayout()
        valrow.setSpacing(10)
        note = label("", "ok")
        note.setVisible(False)
        copy_btn = None

        if ftype in ("secret", "pin"):
            v = label(mask(value), "mask", selectable=False)
            valrow.addWidget(v)
            eye = tool("eye", tr("action.show"), None, 17)
            eye.clicked.connect(lambda _=False, lb=v, val=value, b=eye: self._reveal(lb, val, b))
            actions.addWidget(eye)
            copy_btn = tool("copy", tr("action.copy"), lambda _=False: self.copy_requested.emit(iid, key, value, lab), 17)
            actions.addWidget(copy_btn)
        elif ftype == "url":
            url = value.strip()
            v = ClickableLabel(url)
            v.setStyleSheet(f"color: {theme.t('ai')}; font-size: {theme.font_px() + 1}px;")
            v.setToolTip(url)
            v.clicked.connect(lambda: self.open_url_requested.emit(iid, url))
            valrow.addWidget(v)
            actions.addWidget(tool("external", tr("action.open"), lambda: self.open_url_requested.emit(iid, url), 17))
            copy_btn = tool("copy", tr("action.copy"), lambda: self.copy_requested.emit(iid, key, url, lab), 17)
            actions.addWidget(copy_btn)
        elif ftype == "multiline":
            v = label(value, "note", wrap=True, selectable=True)
            v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            valrow.addWidget(v, 1)
            copy_btn = tool("copy", tr("action.copy"), lambda: self.copy_requested.emit(iid, key, value, lab), 17)
            actions.addWidget(copy_btn)
        elif ftype == "twofa":
            state = twofa_state(value)
            app = (value.get("app") or "") if isinstance(value, dict) else ""
            if state == "on":
                text = tr("detail.twofa_value", app=app) if app else tr("detail.twofa_yes")
            else:
                text = tr(f"twofa.{state}")
            v = label(text, "value", wrap=True)
            if state == "off":
                v.setStyleSheet(f"color: {theme.t('kincha')};")
            valrow.addWidget(v)
        elif ftype == "qa":
            qa = [q for q in (value or []) if isinstance(q, dict) and (q.get("q") or q.get("a"))]
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(6)
            toggle = ClickableLabel(tr("detail.qa_count", n=len(qa)))
            toggle.setStyleSheet(f"color: {theme.t('ink2')};")
            inner = QWidget()
            il = QGridLayout(inner)
            il.setContentsMargins(0, 4, 0, 0)
            il.setHorizontalSpacing(10)
            il.setVerticalSpacing(6)
            for i, q in enumerate(qa):
                il.addWidget(label(q.get("q", ""), "muted", wrap=True, selectable=True), i * 2, 0, 1, 3)
                a = q.get("a", "")
                al = label(mask(a), "mask")
                il.addWidget(al, i * 2 + 1, 0)
                eye = tool("eye", tr("action.show"), None, 16)
                eye.clicked.connect(lambda _=False, lb=al, val=a, b=eye: self._reveal(lb, val, b))
                il.addWidget(eye, i * 2 + 1, 1)
                il.addWidget(tool("copy", tr("action.copy"),
                                  lambda _=False, val=a: self.copy_requested.emit(iid, key, val, lab), 16), i * 2 + 1, 2)
            il.setColumnStretch(0, 1)
            inner.setVisible(False)

            def flip(_=None, w=inner, t=toggle, n=len(qa)):
                w.setVisible(not w.isVisible())
                t.setText(tr("detail.qa_hide") if w.isVisible() else tr("detail.qa_count", n=n))

            toggle.clicked.connect(flip)
            bl.addWidget(toggle)
            bl.addWidget(inner)
            valrow.addWidget(box, 1)
        else:
            v = label(str(value), "value", wrap=True, selectable=True)
            valrow.addWidget(v)
            copy_btn = tool("copy", tr("action.copy"), lambda: self.copy_requested.emit(iid, key, str(value), lab), 17)
            actions.addWidget(copy_btn)
        valrow.addWidget(note)
        if ftype not in ("multiline", "qa"):
            valrow.addStretch(1)
        cell.addLayout(valrow)

        if key == "password" and value:
            st = index.strength.get(iid)
            meta = QHBoxLayout()
            meta.setSpacing(12)
            if st is not None:
                meter = StrengthMeter(st.score)
                meta.addWidget(meter)
                meta.addWidget(label(f"{tr(st.label_key)}（{tr('common.chars', n=len(value))}）", "small"))
            pw_hist = [h for h in history if h.get("field") == "password"]
            if pw_hist:
                hb = button(tr("detail.history_n", n=len(pw_hist)), "link", "history",
                            slot=lambda: self.history_requested.emit(iid))
                meta.addWidget(hb)
            meta.addStretch(1)
            cell.addLayout(meta)
            changed = d.get("pw_changed_at") or ""
            if changed:
                months = months_between(changed) or 0
                text = tr("detail.pw_changed", d=fmt_date(changed), age=fmt_age(changed))
                warn = months * 30 >= OLD_DAYS
                cell.addWidget(label(("⚠ " if warn else "") + text, "warn" if warn else "smallfaint", wrap=True))

        actions_w = QWidget()
        actions_w.setLayout(actions)
        actions.setContentsMargins(0, 6, 0, 6)
        grid.addWidget(self._key(lab), row, 0)
        self._key_pad(grid, row)
        grid.addLayout(cell, row, 1)
        grid.addWidget(actions_w, row, 2, Qt.AlignmentFlag.AlignTop)
        self._rows[key] = {"copy": copy_btn, "note": note}
        row += 1
        return self._sep(grid, row)

    def _key_pad(self, grid, row) -> None:
        item = grid.itemAtPosition(row, 0)
        if item and item.widget():
            item.widget().setContentsMargins(0, 12, 0, 0)

    def _reveal(self, lb: QLabel, value: str, btn: QToolButton) -> None:
        hidden = lb.text().startswith(MASK)
        if hidden:
            lb.setText(value)
            lb.setFont(theme.mono_font(theme.font_px() + 1))
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            set_tool_icon(btn, "eye_off", size=17)
        else:
            lb.setText(mask(value))
            lb.setFont(theme.make_font(theme.font_px() + 1, self.settings["font_family"]))
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            set_tool_icon(btn, "eye", size=17)

    def mark_copied(self, key: str, seconds: int) -> None:
        row = self._rows.get(key)
        if not row:
            return
        btn, note = row["copy"], row["note"]
        if btn is not None:
            set_tool_icon(btn, "check", theme.t("tokiwa"), 17)
            set_variant(btn, "done")
        note.setText(tr("detail.copied_clear", s=seconds) if seconds > 0 else tr("detail.copied"))
        note.setVisible(True)

        def reset():
            try:
                if btn is not None:
                    set_tool_icon(btn, "copy", size=17)
                    set_variant(btn, "")
                note.setVisible(False)
            except RuntimeError:
                pass

        QTimer.singleShot(2500, reset)


class SafetyBox(QFrame):
    """The account's safety level and why: what to fix, or what is already done."""

    def __init__(self, sf, parent=None):
        super().__init__(parent)
        kind = {"high": "ok", "mid": "warn", "low": "risk"}[sf.level]
        color = theme.t({"ok": "tokiwa", "warn": "kincha", "risk": "bengara"}[kind])
        self.setProperty("role", f"banner_{kind}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(9)
        ic = QLabel()
        ic.setPixmap(icons.pixmap({"ok": "shield_check", "warn": "shield_dot", "risk": "shield_alert"}[kind], color, 18))
        ic.setFixedWidth(20)
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.title = label(tr(f"safety.title.{sf.level}"), f"banner_{kind}", wrap=True)
        f = self.title.font()
        f.setWeight(f.Weight.DemiBold)
        self.title.setFont(f)
        col.addWidget(self.title)
        if sf.reasons:
            for r in sf.reasons:
                col.addWidget(label("・" + tr(f"issue.{r}", n=sf.reused), "", wrap=True))
        else:
            done = [tr("safety.ok.password"), tr("safety.ok.unique"), tr("safety.ok.recent")]
            if sf.twofa == "on":
                done.append(tr("safety.twofa.on"))
            text = "　".join("✓ " + x for x in done)
            if sf.twofa in ("none", "unknown"):
                text += "　" + tr(f"safety.twofa.{sf.twofa}")
            col.addWidget(label(text, "small", wrap=True))
        lay.addLayout(col, 1)


def _tint(color: str) -> str:
    return theme.mix(theme.t("paper"), color, 0.2 if theme.is_dark() else 0.12)


class EmptyDetail(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailBody")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        ic = QLabel()
        ic.setPixmap(icons.mark_pixmap(56, theme.t("rule"), theme.t("paper")))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        lay.addSpacing(10)
        t = label(tr("detail.empty"), "muted", wrap=True)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        lay.addStretch(2)
