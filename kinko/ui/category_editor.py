"""Customize categories, sub-categories and item types (which fields an item shows).

Changes are saved into the vault right away, so they travel with the data.
"""
from __future__ import annotations

import copy

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QGridLayout, QHBoxLayout, QInputDialog, QLineEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QToolButton,
                             QVBoxLayout, QWidget)

from ..core.model import (BUILTIN_FIELDS, CATEGORY_COLORS, CATEGORY_ICONS, DEFAULT_TEMPLATES, FIELD_TYPES,
                          display_name, field_label, field_type, new_id)
from ..i18n import tr
from . import icons, theme
from .widgets import Segmented, button, label

ROLE = Qt.ItemDataRole.UserRole


class FieldDialog(QDialog):
    """Add a field to a type: a built-in field or a new one."""

    def __init__(self, parent, existing: set[str]):
        super().__init__(parent)
        self.setWindowTitle(tr("cats.add_field"))
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.addWidget(label(tr("cats.field_source"), "fieldkey"))
        self.source = QComboBox()
        self.source.addItem(tr("cats.field_new"), "")
        for key, (_, lk) in BUILTIN_FIELDS.items():
            if key not in existing:
                self.source.addItem(tr(lk), key)
        lay.addWidget(self.source)
        lay.addWidget(label(tr("editor.field_label"), "fieldkey"))
        self.name = QLineEdit()
        lay.addWidget(self.name)
        lay.addWidget(label(tr("editor.field_type"), "fieldkey"))
        self.type = QComboBox()
        for t in FIELD_TYPES:
            if t not in ("qa", "twofa"):
                self.type.addItem(tr(f"ftype.{t}"), t)
        lay.addWidget(self.type)
        self.source.currentIndexChanged.connect(self._sync)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("common.cancel"), "ghost", slot=self.reject))
        row.addWidget(button(tr("editor.add"), "primary", slot=self._ok))
        lay.addLayout(row)
        self._sync()

    def _sync(self) -> None:
        builtin = bool(self.source.currentData())
        self.name.setEnabled(not builtin)
        self.type.setEnabled(not builtin)
        if builtin:
            self.name.setText(self.source.currentText())

    def _ok(self) -> None:
        if self.source.currentData() or self.name.text().strip():
            self.accept()

    def result_def(self) -> dict:
        key = self.source.currentData()
        if key:
            return {"key": key}
        return {"key": new_id("f_")[:14], "label": self.name.text().strip(), "type": self.type.currentData()}


class CategoryEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.cfg = copy.deepcopy(vault.config)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.seg = Segmented([("cats", tr("cats.tab_categories")), ("types", tr("cats.tab_types"))])
        self.seg.changed.connect(lambda v: self.stack.setCurrentIndex(0 if v == "cats" else 1))
        lay.addWidget(self.seg)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_categories())
        self.stack.addWidget(self._build_types())
        lay.addWidget(self.stack, 1)
        self._reload_cats()
        self._reload_types()

    # ---------------------------------------------------------------- persistence
    def _apply(self) -> None:
        self.vault.config = copy.deepcopy(self.cfg)
        self.vault.save_config()
        self.cfg = copy.deepcopy(self.vault.config)
        self.changed.emit()

    def _items_in(self, cat_id: str, sub_id: str | None = None) -> list[str]:
        out = []
        for iid, rec in self.vault.items.items():
            d = rec.data
            if d["category"] == cat_id and (sub_id is None or d.get("sub") == sub_id):
                out.append(iid)
        return out

    # ---------------------------------------------------------------- categories page
    def _build_categories(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        self.cat_list = QListWidget()
        self.cat_list.setProperty("role", "plain")
        self.cat_list.setIconSize(QSize(18, 18))
        self.cat_list.setFixedWidth(190)
        self.cat_list.currentRowChanged.connect(self._cat_selected)
        left.addWidget(self.cat_list, 1)
        btns = QHBoxLayout()
        btns.setSpacing(6)
        btns.addWidget(button(tr("cats.add"), None, "plus", slot=self._cat_add))
        up = QToolButton()
        up.setIcon(icons.icon("arrow_up", theme.t("ink2"), 15))
        up.clicked.connect(lambda: self._cat_move(-1))
        dn = QToolButton()
        dn.setIcon(icons.icon("arrow_down", theme.t("ink2"), 15))
        dn.clicked.connect(lambda: self._cat_move(1))
        up.setToolTip(tr("cats.up"))
        dn.setToolTip(tr("cats.down"))
        btns.addWidget(up)
        btns.addWidget(dn)
        btns.addStretch(1)
        left.addLayout(btns)
        lay.addLayout(left)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        r = 0
        form.addWidget(label(tr("cats.name"), "fieldkey"), r, 0)
        self.cat_name = QLineEdit()
        self.cat_name.editingFinished.connect(self._cat_rename)
        form.addWidget(self.cat_name, r, 1)
        r += 1
        form.addWidget(label(tr("cats.icon"), "fieldkey"), r, 0, Qt.AlignmentFlag.AlignTop)
        icon_grid = QGridLayout()
        icon_grid.setSpacing(4)
        self.icon_group = QButtonGroup(self)
        self.icon_group.setExclusive(True)
        for i, name in enumerate(CATEGORY_ICONS):
            b = QToolButton()
            b.setProperty("variant", "iconpick")
            b.setCheckable(True)
            b.setIcon(icons.icon(name, theme.t("ink2"), 18, active_color=theme.t("ai")))
            b.setIconSize(QSize(18, 18))
            b.setProperty("icon_name", name)
            b.clicked.connect(lambda _=False, n=name: self._cat_set("icon", n))
            self.icon_group.addButton(b)
            icon_grid.addWidget(b, i // 8, i % 8)
        icon_grid.setColumnStretch(8, 1)
        form.addLayout(icon_grid, r, 1)
        r += 1
        form.addWidget(label(tr("cats.color"), "fieldkey"), r, 0)
        sw = QHBoxLayout()
        sw.setSpacing(4)
        self.color_group = QButtonGroup(self)
        for key in CATEGORY_COLORS:
            b = QPushButton()
            b.setProperty("variant", "swatch")
            b.setCheckable(True)
            b.setProperty("color_key", key)
            b.setStyleSheet(f"background: {theme.cat_color(key)};")
            b.clicked.connect(lambda _=False, k=key: self._cat_set("color", k))
            self.color_group.addButton(b)
            sw.addWidget(b)
        sw.addStretch(1)
        form.addLayout(sw, r, 1)
        r += 1
        form.addWidget(label(tr("cats.type"), "fieldkey"), r, 0)
        self.cat_tpl = QComboBox()
        self.cat_tpl.activated.connect(lambda _: self._cat_set("template", self.cat_tpl.currentData()))
        form.addWidget(self.cat_tpl, r, 1)
        r += 1
        form.addWidget(label(tr("cats.closed_label"), "fieldkey"), r, 0)
        self.cat_closed = QLineEdit()
        self.cat_closed.setPlaceholderText(tr("status.closed_default"))
        self.cat_closed.editingFinished.connect(lambda: self._cat_set("closed_label", self.cat_closed.text().strip()))
        form.addWidget(self.cat_closed, r, 1)
        r += 1
        form.addWidget(label(tr("cats.subs"), "fieldkey"), r, 0, Qt.AlignmentFlag.AlignTop)
        subcol = QVBoxLayout()
        self.sub_list = QListWidget()
        self.sub_list.setProperty("role", "plain")
        self.sub_list.setMaximumHeight(150)
        self.sub_list.currentRowChanged.connect(self._sub_selected)
        subcol.addWidget(self.sub_list)
        sb = QHBoxLayout()
        sb.setSpacing(6)
        sb.addWidget(button(tr("cats.add"), None, "plus", slot=self._sub_add))
        sb.addWidget(button(tr("cats.rename"), slot=self._sub_rename))
        sb.addWidget(button(tr("cats.delete"), "danger", slot=self._sub_delete))
        sb.addStretch(1)
        subcol.addLayout(sb)
        tplrow = QHBoxLayout()
        tplrow.addWidget(label(tr("cats.sub_type"), "small"))
        self.sub_tpl = QComboBox()
        self.sub_tpl.activated.connect(lambda _: self._sub_set_template(self.sub_tpl.currentData()))
        tplrow.addWidget(self.sub_tpl, 1)
        subcol.addLayout(tplrow)
        form.addLayout(subcol, r, 1)
        r += 1
        del_row = QHBoxLayout()
        del_row.addStretch(1)
        del_row.addWidget(button(tr("cats.delete_category"), "danger", "trash", slot=self._cat_delete))
        form.addLayout(del_row, r, 0, 1, 2)
        form.setRowStretch(r + 1, 1)
        lay.addLayout(form, 1)
        return w

    def _template_names(self) -> list[tuple[str, str]]:
        return [(tid, display_name(t)) for tid, t in self.cfg["templates"].items()]

    def _reload_cats(self, select: int | None = None) -> None:
        row = self.cat_list.currentRow() if select is None else select
        self.cat_list.blockSignals(True)
        self.cat_list.clear()
        for c in self.cfg["categories"]:
            it = QListWidgetItem(icons.icon(c.get("icon", "star"), theme.cat_color(c.get("color", "work")), 18),
                                 display_name(c))
            it.setData(ROLE, c["id"])
            self.cat_list.addItem(it)
        self.cat_list.blockSignals(False)
        self.cat_list.setCurrentRow(max(0, min(row, self.cat_list.count() - 1)))
        self._cat_selected(self.cat_list.currentRow())

    def _cur_cat(self) -> dict | None:
        row = self.cat_list.currentRow()
        if 0 <= row < len(self.cfg["categories"]):
            return self.cfg["categories"][row]
        return None

    def _cat_selected(self, _row: int) -> None:
        cat = self._cur_cat()
        if not cat:
            return
        self.cat_name.setText(display_name(cat))
        for b in self.icon_group.buttons():
            b.setChecked(b.property("icon_name") == cat.get("icon"))
        for b in self.color_group.buttons():
            b.setChecked(b.property("color_key") == cat.get("color"))
        self.cat_tpl.clear()
        for tid, name in self._template_names():
            self.cat_tpl.addItem(name, tid)
        self.cat_tpl.setCurrentIndex(max(0, self.cat_tpl.findData(cat.get("template", "login"))))
        self.cat_closed.setText(cat.get("closed_label", ""))
        self.sub_list.clear()
        for s in cat["subs"]:
            it = QListWidgetItem(display_name(s))
            it.setData(ROLE, s["id"])
            self.sub_list.addItem(it)
        self.sub_tpl.clear()
        for tid, name in self._template_names():
            self.sub_tpl.addItem(name, tid)
        self._sub_selected(self.sub_list.currentRow())

    def _cat_set(self, key: str, value) -> None:
        cat = self._cur_cat()
        if not cat:
            return
        if key == "closed_label" and not value:
            cat.pop("closed_label", None)
        else:
            cat[key] = value
        self._apply()
        self._reload_cats()

    def _cat_rename(self) -> None:
        cat = self._cur_cat()
        name = self.cat_name.text().strip()
        if not cat or not name or name == display_name(cat):
            return
        cat["name"] = name
        self._apply()
        self._reload_cats()

    def _cat_add(self) -> None:
        name, ok = QInputDialog.getText(self, tr("cats.add"), tr("cats.name"))
        if not ok or not name.strip():
            return
        self.cfg["categories"].append({"id": new_id("c_")[:12], "name": name.strip(), "icon": "star",
                                       "color": "teal", "template": "login", "subs": []})
        self._apply()
        self._reload_cats(len(self.cfg["categories"]) - 1)

    def _cat_move(self, delta: int) -> None:
        row = self.cat_list.currentRow()
        cats = self.cfg["categories"]
        new = row + delta
        if 0 <= row < len(cats) and 0 <= new < len(cats):
            cats[row], cats[new] = cats[new], cats[row]
            self._apply()
            self._reload_cats(new)

    def _cat_delete(self) -> None:
        cat = self._cur_cat()
        if not cat:
            return
        if len(self.cfg["categories"]) <= 1:
            QMessageBox.information(self, tr("cats.delete_category"), tr("cats.keep_one"))
            return
        ids = self._items_in(cat["id"])
        if ids:
            others = [c for c in self.cfg["categories"] if c["id"] != cat["id"]]
            names = [display_name(c) for c in others]
            target, ok = QInputDialog.getItem(self, tr("cats.delete_category"),
                                              tr("cats.move_items", n=len(ids), name=display_name(cat)), names, 0, False)
            if not ok:
                return
            dest = others[names.index(target)]["id"]
            for iid in ids:
                data = copy.deepcopy(self.vault.items[iid].data)
                data["category"], data["sub"] = dest, ""
                self.vault.update_item(iid, data)
        else:
            r = QMessageBox.question(self, tr("cats.delete_category"), tr("cats.delete_confirm", name=display_name(cat)))
            if r != QMessageBox.StandardButton.Yes:
                return
        self.cfg["categories"] = [c for c in self.cfg["categories"] if c["id"] != cat["id"]]
        self._apply()
        self._reload_cats(0)

    # sub-categories
    def _cur_sub(self) -> dict | None:
        cat = self._cur_cat()
        row = self.sub_list.currentRow()
        if cat and 0 <= row < len(cat["subs"]):
            return cat["subs"][row]
        return None

    def _sub_selected(self, _row: int) -> None:
        sub = self._cur_sub()
        self.sub_tpl.setEnabled(sub is not None)
        if sub:
            self.sub_tpl.setCurrentIndex(max(0, self.sub_tpl.findData(sub.get("template", "login"))))

    def _sub_add(self) -> None:
        cat = self._cur_cat()
        if not cat:
            return
        name, ok = QInputDialog.getText(self, tr("cats.add_sub"), tr("cats.name"))
        if ok and name.strip():
            cat["subs"].append({"id": new_id("s_")[:12], "name": name.strip(), "template": cat.get("template", "login")})
            row = self.cat_list.currentRow()
            self._apply()
            self._reload_cats(row)
            self.sub_list.setCurrentRow(self.sub_list.count() - 1)

    def _sub_rename(self) -> None:
        sub = self._cur_sub()
        if not sub:
            return
        name, ok = QInputDialog.getText(self, tr("cats.rename"), tr("cats.name"), text=display_name(sub))
        if ok and name.strip():
            sub["name"] = name.strip()
            row, srow = self.cat_list.currentRow(), self.sub_list.currentRow()
            self._apply()
            self._reload_cats(row)
            self.sub_list.setCurrentRow(srow)

    def _sub_delete(self) -> None:
        cat, sub = self._cur_cat(), self._cur_sub()
        if not cat or not sub:
            return
        ids = self._items_in(cat["id"], sub["id"])
        msg = tr("cats.delete_sub_confirm", name=display_name(sub), n=len(ids))
        if QMessageBox.question(self, tr("cats.delete"), msg) != QMessageBox.StandardButton.Yes:
            return
        for iid in ids:
            data = copy.deepcopy(self.vault.items[iid].data)
            data["sub"] = ""
            self.vault.update_item(iid, data)
        cat["subs"] = [s for s in cat["subs"] if s["id"] != sub["id"]]
        row = self.cat_list.currentRow()
        self._apply()
        self._reload_cats(row)

    def _sub_set_template(self, tid: str) -> None:
        sub = self._cur_sub()
        if sub and tid:
            sub["template"] = tid
            row, srow = self.cat_list.currentRow(), self.sub_list.currentRow()
            self._apply()
            self._reload_cats(row)
            self.sub_list.setCurrentRow(srow)

    # ---------------------------------------------------------------- types page
    def _build_types(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        self.tpl_list = QListWidget()
        self.tpl_list.setProperty("role", "plain")
        self.tpl_list.setFixedWidth(190)
        self.tpl_list.currentRowChanged.connect(self._tpl_selected)
        left.addWidget(self.tpl_list, 1)
        tb = QHBoxLayout()
        tb.setSpacing(6)
        tb.addWidget(button(tr("cats.type_add"), None, "plus", slot=self._tpl_add))
        tb.addWidget(button(tr("cats.rename"), slot=self._tpl_rename))
        tb.addStretch(1)
        left.addLayout(tb)
        left.addWidget(button(tr("cats.type_delete"), "danger", "trash", slot=self._tpl_delete))
        lay.addLayout(left)
        right = QVBoxLayout()
        right.addWidget(label(tr("cats.fields"), "fieldkey"))
        self.field_list = QListWidget()
        self.field_list.setProperty("role", "plain")
        right.addWidget(self.field_list, 1)
        fb = QHBoxLayout()
        fb.setSpacing(6)
        fb.addWidget(button(tr("cats.add_field"), None, "plus", slot=self._field_add))
        fb.addWidget(button(tr("cats.rename"), slot=self._field_rename))
        up = QToolButton()
        up.setIcon(icons.icon("arrow_up", theme.t("ink2"), 15))
        up.setToolTip(tr("cats.up"))
        up.clicked.connect(lambda: self._field_move(-1))
        dn = QToolButton()
        dn.setIcon(icons.icon("arrow_down", theme.t("ink2"), 15))
        dn.setToolTip(tr("cats.down"))
        dn.clicked.connect(lambda: self._field_move(1))
        fb.addWidget(up)
        fb.addWidget(dn)
        fb.addWidget(button(tr("cats.delete"), "danger", slot=self._field_delete))
        fb.addStretch(1)
        self.reset_btn = button(tr("cats.type_reset"), "ghost", slot=self._tpl_reset)
        fb.addWidget(self.reset_btn)
        right.addLayout(fb)
        right.addWidget(label(tr("cats.types_note"), "smallfaint", wrap=True))
        lay.addLayout(right, 1)
        return w

    def _tpl_ids(self) -> list[str]:
        return list(self.cfg["templates"].keys())

    def _cur_tpl(self) -> tuple[str, dict] | tuple[None, None]:
        row = self.tpl_list.currentRow()
        ids = self._tpl_ids()
        if 0 <= row < len(ids):
            return ids[row], self.cfg["templates"][ids[row]]
        return None, None

    def _reload_types(self, select: int | None = None) -> None:
        row = self.tpl_list.currentRow() if select is None else select
        self.tpl_list.blockSignals(True)
        self.tpl_list.clear()
        for tid, t in self.cfg["templates"].items():
            it = QListWidgetItem(display_name(t))
            it.setData(ROLE, tid)
            self.tpl_list.addItem(it)
        self.tpl_list.blockSignals(False)
        self.tpl_list.setCurrentRow(max(0, min(row, self.tpl_list.count() - 1)))
        self._tpl_selected(self.tpl_list.currentRow())

    def _tpl_selected(self, _row: int, field_row: int = 0) -> None:
        tid, tpl = self._cur_tpl()
        self.field_list.clear()
        if not tpl:
            return
        for f in tpl["fields"]:
            it = QListWidgetItem(f"{field_label(f)}　（{tr('ftype.' + field_type(f))}）")
            self.field_list.addItem(it)
        self.field_list.setCurrentRow(max(0, min(field_row, self.field_list.count() - 1)))
        self.reset_btn.setVisible(tid in DEFAULT_TEMPLATES)

    def _tpl_add(self) -> None:
        tid, tpl = self._cur_tpl()
        name, ok = QInputDialog.getText(self, tr("cats.type_add"), tr("cats.type_add_prompt"))
        if not ok or not name.strip():
            return
        new = {"name": name.strip(), "fields": copy.deepcopy((tpl or self.cfg["templates"]["login"])["fields"])}
        self.cfg["templates"][new_id("t_")[:12]] = new
        self._apply()
        self._reload_types(len(self.cfg["templates"]) - 1)

    def _tpl_rename(self) -> None:
        tid, tpl = self._cur_tpl()
        if not tpl:
            return
        name, ok = QInputDialog.getText(self, tr("cats.rename"), tr("cats.name"), text=display_name(tpl))
        if ok and name.strip():
            tpl["name"] = name.strip()
            row = self.tpl_list.currentRow()
            self._apply()
            self._reload_types(row)
            self._reload_cats()

    def _tpl_delete(self) -> None:
        tid, tpl = self._cur_tpl()
        if not tpl:
            return
        if tid == "login":
            QMessageBox.information(self, tr("cats.type_delete"), tr("cats.type_keep_login"))
            return
        used = [display_name(c) for c in self.cfg["categories"] if c.get("template") == tid]
        used += [display_name(s) for c in self.cfg["categories"] for s in c["subs"] if s.get("template") == tid]
        if used:
            QMessageBox.information(self, tr("cats.type_delete"), tr("cats.type_in_use", names="、".join(used)))
            return
        if QMessageBox.question(self, tr("cats.type_delete"), tr("cats.type_delete_confirm",
                                                                 name=display_name(tpl))) != QMessageBox.StandardButton.Yes:
            return
        del self.cfg["templates"][tid]
        self._apply()
        self._reload_types(0)

    def _tpl_reset(self) -> None:
        tid, tpl = self._cur_tpl()
        if tid in DEFAULT_TEMPLATES and QMessageBox.question(
                self, tr("cats.type_reset"), tr("cats.type_reset_confirm")) == QMessageBox.StandardButton.Yes:
            self.cfg["templates"][tid] = copy.deepcopy(DEFAULT_TEMPLATES[tid])
            row = self.tpl_list.currentRow()
            self._apply()
            self._reload_types(row)

    def _field_add(self) -> None:
        tid, tpl = self._cur_tpl()
        if not tpl:
            return
        dlg = FieldDialog(self, {f["key"] for f in tpl["fields"]})
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tpl["fields"].append(dlg.result_def())
            row = self.tpl_list.currentRow()
            self._apply()
            self._reload_types(row)
            self._tpl_selected(row, len(tpl["fields"]) - 1)

    def _field_rename(self) -> None:
        tid, tpl = self._cur_tpl()
        frow = self.field_list.currentRow()
        if not tpl or not (0 <= frow < len(tpl["fields"])):
            return
        f = tpl["fields"][frow]
        name, ok = QInputDialog.getText(self, tr("cats.rename"), tr("editor.field_label"), text=field_label(f))
        if ok and name.strip():
            f["label"] = name.strip()
            row = self.tpl_list.currentRow()
            self._apply()
            self._reload_types(row)
            self._tpl_selected(row, frow)

    def _field_move(self, delta: int) -> None:
        tid, tpl = self._cur_tpl()
        frow = self.field_list.currentRow()
        if not tpl:
            return
        fields = tpl["fields"]
        new = frow + delta
        if 0 <= frow < len(fields) and 0 <= new < len(fields):
            fields[frow], fields[new] = fields[new], fields[frow]
            row = self.tpl_list.currentRow()
            self._apply()
            self._reload_types(row)
            self._tpl_selected(row, new)

    def _field_delete(self) -> None:
        tid, tpl = self._cur_tpl()
        frow = self.field_list.currentRow()
        if not tpl or not (0 <= frow < len(tpl["fields"])):
            return
        f = tpl["fields"][frow]
        if QMessageBox.question(self, tr("cats.delete"), tr("cats.field_delete_confirm",
                                                            name=field_label(f))) != QMessageBox.StandardButton.Yes:
            return
        del tpl["fields"][frow]
        row = self.tpl_list.currentRow()
        self._apply()
        self._reload_types(row)
