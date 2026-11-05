"""Middle pane: search, status filter, sort, and the item list with hover quick-copy buttons."""
from __future__ import annotations

from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QPainter
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout, QLineEdit, QListView, QMenu, QStackedWidget,
                             QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget)

from ..core.model import closed_label, find_category, first_letter
from ..i18n import tr
from . import icons, theme
from .widgets import Segmented, button, label, paint_avatar

ID_ROLE = Qt.ItemDataRole.UserRole


class ItemModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ids: list[str] = []
        self.vault = None
        self.idx = None
        self.subtitle_mode = "username"

    def set_data(self, ids, vault, index, subtitle_mode) -> None:
        self.beginResetModel()
        self.ids, self.vault, self.idx, self.subtitle_mode = list(ids), vault, index, subtitle_mode
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.ids)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.ids):
            return None
        iid = self.ids[index.row()]
        if role == ID_ROLE:
            return iid
        if role == Qt.ItemDataRole.DisplayRole:
            return self.vault.items[iid].data.get("title", "")
        return None

    def row_of(self, iid: str) -> int:
        try:
            return self.ids.index(iid)
        except ValueError:
            return -1


class RowDelegate(QStyledItemDelegate):
    copy_requested = pyqtSignal(str, str)  # item id, "username" | "password"

    def __init__(self, model: ItemModel, parent=None):
        super().__init__(parent)
        self.model = model

    def sizeHint(self, option, index):  # noqa: N802
        return QSize(10, 46 if theme.compact() else 58)

    def _buttons(self, rect: QRectF, iid: str) -> list[tuple[str, QRectF, str]]:
        d = self.model.vault.items[iid].data["fields"]
        out = []
        x = rect.right() - 10
        h = 26
        f = QFont(QApplication.font())
        f.setPixelSize(max(theme.font_px() - 2, 10))
        fm = QFontMetrics(f)
        for key, text in (("password", tr("list.copy_password")), ("username", tr("list.copy_id"))):
            value = d.get(key) or (d.get("email") if key == "username" else "")
            if not value:
                continue
            w = 24 + fm.horizontalAdvance(text) + 8
            r = QRectF(x - w, rect.center().y() - h / 2, w, h)
            out.append((key, r, text))
            x -= w + 6
        return out

    def paint(self, p: QPainter, opt, index):
        iid = index.data(ID_ROLE)
        vault, idx = self.model.vault, self.model.idx
        rec = vault.items.get(iid)
        if rec is None:
            return
        d = rec.data
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(opt.rect).adjusted(8, 1, -8, -1)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            p.setPen(QColor(theme.t("ai_line")))
            p.setBrush(QColor(theme.t("paper")))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.t("ai")))
            p.drawRoundedRect(QRectF(r.left(), r.top() + 12, 3, r.height() - 24), 1.5, 1.5)
        elif hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.t("rule2")))
            p.drawRoundedRect(r, 8, 8)
        closed = d["status"] == "closed" or rec.trashed
        cat = find_category(vault.config, d["category"])
        color = theme.cat_color(cat.get("color", "work")) if cat else theme.t("ink3")
        av = 30 if theme.compact() else 34
        paint_avatar(p, QRectF(r.left() + 10, r.center().y() - av / 2, av, av), first_letter(d.get("title", "")),
                     color, muted=closed)
        x = r.left() + 10 + av + 12
        right = r.right() - 10

        # right side: quick buttons on hover, otherwise badges
        if hover and not rec.trashed:
            for key, br, text in self._buttons(r, iid):
                p.setPen(QColor(theme.t("rule")))
                p.setBrush(QColor(theme.t("paper")))
                p.drawRoundedRect(br, 6, 6)
                p.drawPixmap(int(br.left() + 7), int(br.center().y() - 7), icons.pixmap("copy", theme.t("ink2"), 14))
                f = QFont(opt.font)
                f.setPixelSize(max(theme.font_px() - 2, 10))
                p.setFont(f)
                p.setPen(QColor(theme.t("ink2")))
                p.drawText(br.adjusted(24, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
                right = min(right, br.left() - 8)
        else:
            badge = None
            if rec.trashed:
                badge = (tr("list.in_trash"), "rule2", "ink2")
            elif d["status"] == "closed":
                badge = (closed_label(vault.config, d), "rule2", "ink2")
            else:
                issues = idx.issues.get(iid, [])
                if "reused" in issues:
                    badge = (tr("issue.reused_short"), "bengara_tint", "bengara")
                elif "weak" in issues:
                    badge = (tr("issue.weak_short"), "kincha_tint", "kincha")
            if badge:
                f = QFont(opt.font)
                f.setPixelSize(max(theme.font_px() - 2, 10))
                f.setWeight(QFont.Weight.DemiBold)
                p.setFont(f)
                w = p.fontMetrics().horizontalAdvance(badge[0]) + 14
                br = QRectF(right - w, r.center().y() - 9, w, 18)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.t(badge[1])))
                p.drawRoundedRect(br, 9, 9)
                p.setPen(QColor(theme.t(badge[2])))
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, badge[0])
                right = br.left() - 8
            if (d["fields"].get("twofa") or {}).get("on") and not closed:
                p.drawPixmap(int(right - 16), int(r.center().y() - 8), icons.pixmap("shield_check", theme.t("tokiwa"), 16))
                right -= 22
            if d.get("favorite") and not rec.trashed:
                p.drawPixmap(int(right - 14), int(r.center().y() - 7), icons.pixmap("star_fill", theme.t("kincha"), 14))
                right -= 20

        title_f = QFont(opt.font)
        title_f.setWeight(QFont.Weight.DemiBold)
        title_f.setPixelSize(theme.font_px() + 1)
        sub_f = QFont(opt.font)
        sub_f.setPixelSize(max(theme.font_px() - 1, 10))
        subtitle = idx.subtitle(iid, self.model.subtitle_mode)
        width = int(right - x)
        p.setFont(title_f)
        p.setPen(QColor(theme.t("ink3") if closed else theme.t("ink")))
        title = p.fontMetrics().elidedText(d.get("title", ""), Qt.TextElideMode.ElideRight, width)
        if subtitle and not theme.compact():
            p.drawText(QRectF(x, r.top() + 9, width, r.height() / 2 - 6), Qt.AlignmentFlag.AlignBottom, title)
            p.setFont(sub_f)
            p.setPen(QColor(theme.t("ink3")))
            st = p.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideRight, width)
            p.drawText(QRectF(x, r.center().y() + 2, width, r.height() / 2 - 6), Qt.AlignmentFlag.AlignTop, st)
        else:
            p.drawText(QRectF(x, r.top(), width, r.height()), Qt.AlignmentFlag.AlignVCenter, title)
        p.restore()

    def editorEvent(self, event, model, option, index):  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            iid = index.data(ID_ROLE)
            rec = self.model.vault.items.get(iid)
            if rec and not rec.trashed:
                r = QRectF(option.rect).adjusted(8, 1, -8, -1)
                pos = event.position()
                for key, br, _ in self._buttons(r, iid):
                    if br.contains(pos):
                        self.copy_requested.emit(iid, key)
                        return True
        return super().editorEvent(event, model, option, index)


class SearchField(QLineEdit):
    """Lets copy shortcuts through to the window when nothing is selected, and steers the list with arrow keys."""

    navigate = pyqtSignal(int)
    accept_first = pyqtSignal()

    def __init__(self, passthrough: list[QKeySequence], parent=None):
        super().__init__(parent)
        self.setObjectName("SearchField")
        self.passthrough = passthrough

    def event(self, e):
        if e.type() == QEvent.Type.ShortcutOverride and not self.hasSelectedText():
            seq = QKeySequence(e.keyCombination())
            if any(seq.matches(ps) == QKeySequence.SequenceMatch.ExactMatch for ps in self.passthrough if not ps.isEmpty()):
                e.ignore()
                return False
        return super().event(e)

    def keyPressEvent(self, e):  # noqa: N802
        if e.key() == Qt.Key.Key_Down:
            self.navigate.emit(1)
            return
        if e.key() == Qt.Key.Key_Up:
            self.navigate.emit(-1)
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_first.emit()
            return
        if e.key() == Qt.Key.Key_Escape and self.text():
            self.clear()
            return
        super().keyPressEvent(e)


class ItemListView(QListView):
    """Lets the window's copy shortcuts work here instead of Qt copying the row title."""

    def __init__(self, passthrough: list[QKeySequence], parent=None):
        super().__init__(parent)
        self.passthrough = passthrough

    def _is_ours(self, e) -> bool:
        seq = QKeySequence(e.keyCombination())
        return any(seq.matches(ps) == QKeySequence.SequenceMatch.ExactMatch for ps in self.passthrough
                   if not ps.isEmpty())

    def event(self, e):
        if e.type() == QEvent.Type.ShortcutOverride and self._is_ours(e):
            e.ignore()
            return False
        return super().event(e)

    def keyPressEvent(self, e):  # noqa: N802
        if e.matches(QKeySequence.StandardKey.Copy) or self._is_ours(e):
            e.ignore()
            return
        super().keyPressEvent(e)


class ListPane(QWidget):
    current_changed = pyqtSignal(object)  # item id or None
    copy_requested = pyqtSignal(str, str)
    new_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)
    query_changed = pyqtSignal(str)

    def __init__(self, settings, shortcut_seqs: list[QKeySequence], parent=None):
        super().__init__(parent)
        self.setObjectName("ListPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings = settings
        self.vault = None
        self.index = None
        self.spec: tuple = ("all",)
        self.status = "all"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 4, 6)
        lay.setSpacing(8)

        self.search = SearchField(shortcut_seqs)
        self.search.setPlaceholderText(tr("list.search_placeholder"))
        self.search.addAction(icons.icon("search", theme.t("ink3"), 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._query_changed)
        self.search.navigate.connect(self.move_selection)
        self.search.accept_first.connect(self._accept_first)
        row0 = QHBoxLayout()
        row0.setContentsMargins(0, 0, 8, 0)
        row0.addWidget(self.search)
        lay.addLayout(row0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 8, 0)
        self.seg = Segmented([("all", tr("list.status_all")), ("active", tr("list.status_active")),
                              ("closed", tr("list.status_closed"))])
        self.seg.changed.connect(self._status_changed)
        row.addWidget(self.seg)
        row.addStretch(1)
        self.sort_btn = QToolButton()
        self.sort_btn.setProperty("variant", "text")
        self.sort_btn.setIcon(icons.icon("sort", theme.t("ink2"), 14))
        self.sort_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sort_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu = QMenu(self.sort_btn)
        for key in ("recent", "name", "updated"):
            menu.addAction(tr(f"sort.{key}"), lambda k=key: self._set_sort(k))
        self.sort_btn.setMenu(menu)
        row.addWidget(self.sort_btn)
        lay.addLayout(row)
        self.caption = label("", "smallfaint")
        self.caption.setContentsMargins(4, 0, 0, 0)
        lay.addWidget(self.caption)

        self.stack = QStackedWidget()
        self.model = ItemModel(self)
        self.view = ItemListView(shortcut_seqs)
        self.view.setModel(self.model)
        self.delegate = RowDelegate(self.model, self.view)
        self.delegate.copy_requested.connect(self.copy_requested)
        self.view.setItemDelegate(self.delegate)
        self.view.setMouseTracking(True)
        self.view.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setUniformItemSizes(True)
        self.view.setSpacing(1)
        self.view.selectionModel().currentChanged.connect(self._current)
        self.view.doubleClicked.connect(lambda ix: self.edit_requested.emit(ix.data(ID_ROLE)))
        self.stack.addWidget(self.view)

        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch(1)
        self.empty_text = label("", "muted", wrap=True)
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_text)
        self.empty_btn = button(tr("list.add_first"), "primary", "plus", slot=self.new_requested.emit)
        el.addWidget(self.empty_btn, 0, Qt.AlignmentFlag.AlignCenter)
        el.addStretch(2)
        self.stack.addWidget(self.empty)
        lay.addWidget(self.stack, 1)
        self._update_sort_label()

    # ---------------------------------------------------------------- state
    def set_vault(self, vault, index) -> None:
        self.vault, self.index = vault, index

    def set_spec(self, spec: tuple) -> None:
        self.spec = spec
        self.reload(select_first=True)

    def _status_changed(self, value: str) -> None:
        self.status = value
        self.reload(select_first=True)

    def _set_sort(self, key: str) -> None:
        self.settings.set("sort", key)
        self._update_sort_label()
        self.reload()

    def _update_sort_label(self) -> None:
        self.sort_btn.setText(tr(f"sort.{self.settings['sort']}"))

    def _query_changed(self, text: str) -> None:
        self.reload(select_first=True)
        self.query_changed.emit(text)

    def current_id(self) -> str | None:
        ix = self.view.currentIndex()
        return ix.data(ID_ROLE) if ix.isValid() else None

    def reload(self, select_first: bool = False, keep: str | None = None) -> None:
        if self.vault is None:
            return
        keep = keep or self.current_id()
        query = self.search.text()
        ids = self.index.ids_for(self.spec, self.status, query)
        sort = self.settings["sort"]
        if self.spec == ("recent",) and not query:
            sort = "recent"
        ids = self.index.sort(ids, sort)
        if self.spec == ("recent",) and not query:
            ids = ids[:30]
        self.model.set_data(ids, self.vault, self.index, self.settings["list_subtitle"])
        if query:
            self.caption.setText(tr("list.search_result", q=query, n=len(ids)))
        else:
            self.caption.setText(tr("list.count", n=len(ids)))
        if not ids:
            self.stack.setCurrentWidget(self.empty)
            empty_vault = not any(not r.trashed for r in self.vault.items.values())
            if query:
                self.empty_text.setText(tr("list.no_match", q=query))
            elif self.spec == ("trash",):
                self.empty_text.setText(tr("list.trash_empty"))
            elif empty_vault:
                self.empty_text.setText(tr("list.vault_empty"))
            else:
                self.empty_text.setText(tr("list.none_here"))
            self.empty_btn.setVisible(empty_vault and not query)
            self.current_changed.emit(None)
            return
        self.stack.setCurrentWidget(self.view)
        row = self.model.row_of(keep) if keep else -1
        if row < 0 and (select_first or keep):
            row = 0
        if row >= 0:
            ix = self.model.index(row, 0)
            self.view.setCurrentIndex(ix)
            self.view.scrollTo(ix)
            self.current_changed.emit(ix.data(ID_ROLE))
        else:
            self.current_changed.emit(None)

    def select_id(self, iid: str) -> None:
        row = self.model.row_of(iid)
        if row < 0:
            self.search.clear()
            self.reload(keep=iid)
            row = self.model.row_of(iid)
        if row >= 0:
            ix = self.model.index(row, 0)
            self.view.setCurrentIndex(ix)
            self.view.scrollTo(ix)

    def move_selection(self, delta: int) -> None:
        n = self.model.rowCount()
        if not n:
            return
        row = self.view.currentIndex().row()
        row = 0 if row < 0 else max(0, min(n - 1, row + delta))
        self.view.setCurrentIndex(self.model.index(row, 0))

    def _accept_first(self) -> None:
        if self.model.rowCount():
            if not self.view.currentIndex().isValid():
                self.view.setCurrentIndex(self.model.index(0, 0))
            self.view.setFocus()

    def _current(self, cur, _prev) -> None:
        self.current_changed.emit(cur.data(ID_ROLE) if cur.isValid() else None)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def refresh_view(self) -> None:
        self.view.viewport().update()
