"""Left pane: vault header, filters (all / favorites / recent), categories, tags, health, trash."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from ..core.model import display_name
from ..i18n import tr
from . import icons, theme
from .widgets import label, tool

ROLE = Qt.ItemDataRole.UserRole


class NavDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):  # noqa: N802
        d = index.data(ROLE) or {}
        if d.get("kind") == "header":
            return QSize(10, 30 if not theme.compact() else 26)
        if d.get("kind") == "sub":
            return QSize(10, 29 if not theme.compact() else 25)
        return QSize(10, 32 if not theme.compact() else 28)

    def paint(self, p: QPainter, opt, index):
        d = index.data(ROLE) or {}
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(opt.rect).adjusted(0, 1, 0, -1)
        f = QFont(opt.font)
        if d.get("kind") == "header":
            f.setPixelSize(max(theme.font_px() - 2, 10))
            p.setFont(f)
            p.setPen(QColor(theme.t("ink3")))
            p.drawText(r.adjusted(8, 6, -8, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       d.get("label", ""))
            p.restore()
            return
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        if selected or hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.t("ai_tint") if selected else theme.t("rule2")))
            p.drawRoundedRect(r, 6, 6)
        x = r.left() + 8 + (28 if d.get("kind") == "sub" else 0)
        cy = r.center().y()
        text_color = theme.t("ai") if selected else (theme.t("ink2") if d.get("kind") == "sub" else theme.t("ink"))
        if d.get("icon"):
            color = d.get("color") or theme.t("ink2")
            if selected:
                color = theme.t("ai")
            pm = icons.pixmap(d["icon"], color, 18)
            p.drawPixmap(int(x), int(cy - 9), pm)
            x += 28
        f.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        if d.get("kind") == "sub":
            f.setPixelSize(max(theme.font_px() - 1, 10))
        p.setFont(f)
        right = r.right() - 8
        if d.get("expandable"):
            chev = icons.pixmap("chev_down" if d.get("expanded") else "chev_right", theme.t("ink3"), 13)
            p.drawPixmap(int(right - 13), int(cy - 6.5), chev)
            right -= 19
        badge = d.get("badge")
        count = d.get("count")
        f2 = QFont(f)
        f2.setWeight(QFont.Weight.Normal)
        f2.setPixelSize(max(theme.font_px() - 2, 10))
        if badge:
            f2.setWeight(QFont.Weight.Bold)
            p.setFont(f2)
            txt = str(badge)
            w = max(20, p.fontMetrics().horizontalAdvance(txt) + 12)
            br = QRectF(right - w, cy - 9, w, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.t("bengara_tint")))
            p.drawRoundedRect(br, 9, 9)
            p.setPen(QColor(theme.t("bengara")))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, txt)
            right -= w + 6
        elif count is not None:
            p.setFont(f2)
            p.setPen(QColor(theme.t("ai") if selected else theme.t("ink3")))
            txt = str(count)
            w = p.fontMetrics().horizontalAdvance(txt)
            p.drawText(QRectF(right - w, r.top(), w, r.height()), Qt.AlignmentFlag.AlignVCenter, txt)
            right -= w + 8
        p.setFont(f)
        p.setPen(QColor(text_color))
        text = p.fontMetrics().elidedText(d.get("label", ""), Qt.TextElideMode.ElideRight, int(right - x))
        p.drawText(QRectF(x, r.top(), right - x, r.height()), Qt.AlignmentFlag.AlignVCenter, text)
        p.restore()


class NavList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(NavDelegate(self))
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QListWidget { background: transparent; border: none; } "
                           "QListWidget::item { background: transparent; border: none; }")

    def add(self, data: dict) -> QListWidgetItem:
        it = QListWidgetItem()
        it.setData(ROLE, data)
        if data.get("kind") == "header":
            it.setFlags(Qt.ItemFlag.NoItemFlags)
        self.addItem(it)
        return it


class Sidebar(QWidget):
    filter_changed = pyqtSignal(tuple)
    settings_requested = pyqtSignal()
    lock_requested = pyqtSignal()
    vault_menu_requested = pyqtSignal(object)  # the button widget

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings = settings
        self.spec: tuple = ("all",)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(6, 2, 2, 12)
        head.setSpacing(10)
        self.mark = QLabel()
        self.mark.setPixmap(icons.mark_pixmap(30, theme.t("mark_bg"), theme.t("mark_fg")))
        head.addWidget(self.mark)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.vault_name = QLabel()
        f = self.vault_name.font()
        f.setWeight(QFont.Weight.Bold)
        f.setPixelSize(theme.font_px() + 1)
        self.vault_name.setFont(f)
        self.vault_count = label("", "smallfaint")
        col.addWidget(self.vault_name)
        col.addWidget(self.vault_count)
        head.addLayout(col, 1)
        self.vault_btn = tool("chev_down", tr("sidebar.vault_menu"), None, 15)
        self.vault_btn.clicked.connect(lambda: self.vault_menu_requested.emit(self.vault_btn))
        head.addWidget(self.vault_btn)
        lock = tool("lock", tr("sidebar.lock"), self.lock_requested.emit, 16, variant="boxed")
        lock.setFixedSize(30, 30)
        head.addWidget(lock)
        lay.addLayout(head)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {theme.t('rule')};")
        lay.addWidget(sep)
        lay.addSpacing(8)

        self.nav = NavList()
        self.nav.itemClicked.connect(self._clicked)
        lay.addWidget(self.nav, 1)
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {theme.t('rule')};")
        lay.addWidget(sep2)
        lay.addSpacing(6)
        self.foot = NavList()
        self.foot.itemClicked.connect(self._clicked)
        lay.addWidget(self.foot)

    # ---------------------------------------------------------------- data
    def refresh(self, vault, index) -> None:
        s = self.settings
        cfg = vault.config
        self.vault_name.setText(vault.name)
        self.vault_count.setText(tr("sidebar.count", n=index.total))
        self.nav.clear()
        self.foot.clear()
        self.nav.add({"kind": "nav", "spec": ("all",), "label": tr("nav.all"), "icon": "grid", "count": index.total})
        if s["show_favorites"]:
            self.nav.add({"kind": "nav", "spec": ("fav",), "label": tr("nav.favorites"), "icon": "star",
                          "count": index.fav_count})
        if s["show_recent"]:
            self.nav.add({"kind": "nav", "spec": ("recent",), "label": tr("nav.recent"), "icon": "clock"})
        self.nav.add({"kind": "header", "label": tr("nav.categories")})
        expanded = set(s["sidebar_expanded"] or [])
        for cat in cfg["categories"]:
            has_subs = bool(cat["subs"])
            is_open = cat["id"] in expanded
            self.nav.add({"kind": "nav", "spec": ("cat", cat["id"]), "label": display_name(cat),
                          "icon": cat.get("icon", "star"), "color": theme.cat_color(cat.get("color", "work")),
                          "count": index.cat_counts.get(cat["id"], 0), "expandable": has_subs,
                          "expanded": is_open, "cat": cat["id"]})
            if has_subs and is_open:
                for sub in cat["subs"]:
                    self.nav.add({"kind": "sub", "spec": ("sub", cat["id"], sub["id"]), "label": display_name(sub),
                                  "count": index.sub_counts.get((cat["id"], sub["id"]), 0)})
        if s["show_tags"] and index.tags:
            self.nav.add({"kind": "header", "label": tr("nav.tags")})
            for tag, n in sorted(index.tags.items(), key=lambda kv: kv[0]):
                self.nav.add({"kind": "nav", "spec": ("tag", tag), "label": tag, "icon": "tag", "count": n})
        if s["show_health"]:
            c = index.level_counts
            # red badge only for accounts to fix soon; the ones that could be better are a plain count
            item = self.foot.add({"kind": "nav", "spec": ("health",), "label": tr("nav.health"), "icon": "shield",
                                  "badge": c["low"] or None, "count": None if c["low"] else c["mid"]})
            item.setToolTip(tr("safety.counts", high=c["high"], mid=c["mid"], low=c["low"]))
        self.foot.add({"kind": "nav", "spec": ("trash",), "label": tr("nav.trash"), "icon": "trash",
                       "count": index.trash_count})
        self.foot.add({"kind": "nav", "spec": ("settings",), "label": tr("nav.settings"), "icon": "sliders"})
        self.foot.setFixedHeight(sum(self.foot.sizeHintForRow(i) for i in range(self.foot.count())) + 4)
        self._select_spec(self.spec, emit=False)

    def _select_spec(self, spec: tuple, emit: bool = True) -> None:
        found = False
        for lst in (self.nav, self.foot):
            lst.blockSignals(True)
            lst.clearSelection()
            for i in range(lst.count()):
                d = lst.item(i).data(ROLE) or {}
                if d.get("spec") == spec:
                    lst.item(i).setSelected(True)
                    lst.setCurrentItem(lst.item(i))
                    found = True
            lst.blockSignals(False)
        if not found and spec != ("all",):
            self.spec = ("all",)
            self._select_spec(self.spec, emit=emit)
            return
        self.spec = spec
        if emit:
            self.filter_changed.emit(spec)

    def select(self, spec: tuple) -> None:
        self._select_spec(spec)

    def _clicked(self, item: QListWidgetItem) -> None:
        d = item.data(ROLE) or {}
        if d.get("kind") == "header":
            return
        spec = d.get("spec")
        if spec == ("settings",):
            self._select_spec(self.spec, emit=False)
            self.settings_requested.emit()
            return
        if d.get("expandable"):
            lst = item.listWidget()
            pos = lst.viewport().mapFromGlobal(lst.cursor().pos())
            on_chevron = pos.x() > lst.viewport().width() - 34
            if on_chevron or self.spec == spec:
                self._toggle(d["cat"])
                self._select_spec(spec, emit=self.spec != spec)
                return
        self._select_spec(spec)

    def _toggle(self, cat_id: str) -> None:
        expanded = list(self.settings["sidebar_expanded"] or [])
        if cat_id in expanded:
            expanded.remove(cat_id)
            if self.spec[:1] == ("sub",) and self.spec[1] == cat_id:
                self.spec = ("cat", cat_id)
        else:
            expanded.append(cat_id)
        self.settings.set("sidebar_expanded", expanded)
        self.request_refresh()

    def request_refresh(self) -> None:
        self._refresher()

    def set_refresher(self, fn) -> None:
        self._refresher = fn
