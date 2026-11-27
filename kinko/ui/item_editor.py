"""Right pane, edit mode: fields follow the item's type; custom fields can be added per item."""
from __future__ import annotations

import copy
import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QMessageBox,
                             QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

from ..core.model import (AUTH_APPS, TWOFA_STATES, closed_label, display_name, empty_item, find_category,
                          first_letter, item_fields, is_empty, new_id, twofa_state, twofa_value)
from ..i18n import tr
from . import theme
from .generator_popup import GeneratorPopup
from .widgets import Avatar, SecretEdit, Switch, TagEdit, button, hline, label, tool

EXTRA_TYPES = ("text", "secret", "pin", "url", "email", "date", "number", "multiline")


class QAEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, value, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.rows: list[tuple[QWidget, QLineEdit, SecretEdit]] = []
        for q in value or []:
            if isinstance(q, dict):
                self.add_row(q.get("q", ""), q.get("a", ""))
        self.add_btn = button(tr("editor.qa_add"), "ghost", "plus", slot=lambda: self.add_row("", ""))
        self.lay.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignLeft)
        if not self.rows:
            self.add_row("", "")

    def add_row(self, q: str, a: str) -> None:
        w = QWidget()
        rl = QHBoxLayout(w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        qe = QLineEdit(q)
        qe.setPlaceholderText(tr("editor.qa_question"))
        ae = SecretEdit(generator=False, placeholder=tr("editor.qa_answer"))
        ae.setText(a)
        rl.addWidget(qe, 3)
        rl.addWidget(ae, 2)
        rm = tool("x", tr("editor.remove"), None, 15)
        rl.addWidget(rm)
        qe.textChanged.connect(self.changed)
        ae.textChanged.connect(self.changed)
        row = (w, qe, ae)
        rm.clicked.connect(lambda: self._remove(row))
        self.rows.append(row)
        self.lay.insertWidget(len(self.rows) - 1, w)
        self.changed.emit()

    def _remove(self, row) -> None:
        self.rows.remove(row)
        row[0].deleteLater()
        self.changed.emit()

    def value(self) -> list[dict]:
        out = []
        for _, q, a in self.rows:
            if q.text().strip() or a.text():
                out.append({"q": q.text().strip(), "a": a.text()})
        return out


class TwoFAEditor(QWidget):
    """Whether the account uses two-step verification - or whether the service even offers it."""

    changed = pyqtSignal()

    def __init__(self, value, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.state = QComboBox()
        for st in TWOFA_STATES:
            self.state.addItem(tr(f"twofa.{st}"), st)
        self.state.setCurrentIndex(max(0, self.state.findData(twofa_state(value))))
        self.app = QComboBox()
        self.app.setEditable(True)
        self.app.addItems(AUTH_APPS)
        current = value.get("app") if isinstance(value, dict) else ""
        self.app.setCurrentText(current or AUTH_APPS[0])
        self.app.setToolTip(tr("twofa.method"))
        row.addWidget(self.state)
        row.addWidget(self.app, 1)
        lay.addLayout(row)
        self.hint = label(tr("editor.twofa_hint"), "smallfaint", wrap=True)
        lay.addWidget(self.hint)
        self._sync()
        self.state.currentIndexChanged.connect(self._state_changed)
        self.app.currentTextChanged.connect(lambda _: self.changed.emit())

    def _sync(self) -> None:
        on = self.state.currentData() == "on"
        self.app.setVisible(on)
        self.hint.setVisible(self.state.currentData() == "unknown")

    def _state_changed(self) -> None:
        self._sync()
        self.changed.emit()

    def set_state(self, state: str) -> None:
        self.state.setCurrentIndex(max(0, self.state.findData(state)))

    def value(self) -> dict | None:
        return twofa_value(self.state.currentData(), self.app.currentText())


class AddFieldDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("editor.add_field"))
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.addWidget(label(tr("editor.field_label"), "fieldkey"))
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("editor.field_label_placeholder"))
        lay.addWidget(self.name)
        lay.addWidget(label(tr("editor.field_type"), "fieldkey"))
        self.type = QComboBox()
        for t in EXTRA_TYPES:
            self.type.addItem(tr(f"ftype.{t}"), t)
        lay.addWidget(self.type)
        lay.addWidget(label(tr("editor.add_field_note"), "smallfaint", wrap=True))
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("common.cancel"), "ghost", slot=self.reject))
        row.addWidget(button(tr("editor.add"), "primary", slot=self._ok))
        lay.addLayout(row)

    def _ok(self) -> None:
        if self.name.text().strip():
            self.accept()

    def result_def(self) -> dict:
        return {"key": new_id("f_")[:14], "label": self.name.text().strip(), "type": self.type.currentData()}


class EditorView(QWidget):
    saved = pyqtSignal(object, dict)  # item id or None, data
    cancelled = pyqtSignal()
    dirty_changed = pyqtSignal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailBody")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings = settings
        self.vault = None
        self.iid = None
        self._orig = ""
        self._editors: dict[str, tuple[str, QWidget]] = {}
        self._extra: list[dict] = []
        self._values: dict = {}
        self._building = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(28, 16, 24, 12)
        hl.setSpacing(12)
        self.avatar = Avatar("?", theme.t("ink3"), 48)
        hl.addWidget(self.avatar)
        self.title = QLineEdit()
        self.title.setProperty("role", "titleedit")
        self.title.setPlaceholderText(tr("editor.title_placeholder"))
        self.title.textChanged.connect(self._changed)
        hl.addWidget(self.title, 1)
        self.fav = Switch(tr("editor.favorite"))
        self.fav.toggled.connect(self._changed)
        hl.addWidget(self.fav)
        outer.addWidget(head)

        meta = QWidget()
        ml = QGridLayout(meta)
        ml.setContentsMargins(28, 0, 24, 12)
        ml.setHorizontalSpacing(10)
        ml.setVerticalSpacing(8)
        self.cat = QComboBox()
        self.sub = QComboBox()
        self.status = QComboBox()
        self.cat.currentIndexChanged.connect(self._cat_changed)
        self.sub.currentIndexChanged.connect(self._sub_changed)
        self.status.currentIndexChanged.connect(self._changed)
        ml.addWidget(label(tr("editor.category"), "fieldkey"), 0, 0)
        ml.addWidget(self.cat, 0, 1)
        ml.addWidget(self.sub, 0, 2)
        ml.addWidget(label(tr("editor.status"), "fieldkey"), 0, 3)
        ml.addWidget(self.status, 0, 4)
        ml.setColumnStretch(1, 2)
        ml.setColumnStretch(2, 2)
        ml.setColumnStretch(4, 1)
        outer.addWidget(meta)
        outer.addWidget(hline())

        self.scroll = QScrollArea()
        self.scroll.setObjectName("DetailScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)

        foot = QWidget()
        foot.setObjectName("EditorFoot")
        foot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        foot.setStyleSheet(f"QWidget#EditorFoot {{ background: {theme.t('paper2')}; "
                           f"border-top: 1px solid {theme.t('rule')}; }}")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(28, 10, 24, 10)
        self.unsaved = label("⚠ " + tr("editor.unsaved"), "warn")
        self.unsaved.setVisible(False)
        fl.addWidget(self.unsaved)
        fl.addStretch(1)
        fl.addWidget(button(tr("common.cancel"), slot=self.cancel))
        self.save_btn = button(tr("editor.save"), "primary", slot=self.save)
        fl.addWidget(self.save_btn)
        outer.addWidget(foot)

    # ---------------------------------------------------------------- start
    def start(self, vault, index, rec=None, preset: tuple[str, str] | None = None, template_data: dict | None = None):
        self._building = True
        self.vault = vault
        self.index = index
        self.iid = rec.id if rec else None
        if rec:
            data = copy.deepcopy(rec.data)
        elif template_data:
            data = copy.deepcopy(template_data)
        else:
            cat, sub = preset or ("service", "")
            if not find_category(vault.config, cat):
                cat, sub = vault.config["categories"][0]["id"], ""
            data = empty_item(cat, sub)
        self._data = data
        self._values = copy.deepcopy(data["fields"])
        self._extra = copy.deepcopy(data.get("extra", []))
        self.title.setText(data.get("title", ""))
        self.fav.setChecked(bool(data.get("favorite")))
        self.cat.blockSignals(True)
        self.cat.clear()
        for c in vault.config["categories"]:
            self.cat.addItem(display_name(c), c["id"])
        self.cat.setCurrentIndex(max(0, self.cat.findData(data["category"])))
        self.cat.blockSignals(False)
        self._fill_subs(data.get("sub", ""))
        self._fill_status(data.get("status", "active"))
        self._build_form()
        self._building = False
        self._orig = self._snapshot()
        self._set_dirty(False)
        self._update_avatar()
        if not rec:
            self.title.setFocus()

    def _fill_subs(self, current: str) -> None:
        self.sub.blockSignals(True)
        self.sub.clear()
        cat = find_category(self.vault.config, self.cat.currentData())
        self.sub.addItem(tr("editor.no_sub"), "")
        for s in (cat or {}).get("subs", []):
            self.sub.addItem(display_name(s), s["id"])
        self.sub.setCurrentIndex(max(0, self.sub.findData(current)))
        self.sub.setEnabled(self.sub.count() > 1)
        self.sub.blockSignals(False)

    def _fill_status(self, current: str) -> None:
        self.status.blockSignals(True)
        self.status.clear()
        probe = {"category": self.cat.currentData(), "sub": self.sub.currentData() or ""}
        self.status.addItem(tr("status.active"), "active")
        self.status.addItem(closed_label(self.vault.config, probe), "closed")
        self.status.setCurrentIndex(max(0, self.status.findData(current)))
        self.status.blockSignals(False)

    def _cat_changed(self) -> None:
        if self._building:
            return
        self._values = self._collect_values()
        self._data["tags"] = self.tags.tags()
        self._fill_subs("")
        self._fill_status(self.status.currentData())
        self._build_form()
        self._update_avatar()
        self._changed()

    def _sub_changed(self) -> None:
        if self._building:
            return
        self._values = self._collect_values()
        self._data["tags"] = self.tags.tags()
        self._fill_status(self.status.currentData())
        self._build_form()
        self._changed()

    # ---------------------------------------------------------------- form
    def _probe(self) -> dict:
        return {"category": self.cat.currentData(), "sub": self.sub.currentData() or "", "fields": self._values,
                "extra": self._extra}

    def _build_form(self) -> None:
        self._editors = {}
        body = QWidget()
        body.setObjectName("DetailBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 12, 24, 18)
        lay.setSpacing(0)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, 132)
        grid.setColumnStretch(1, 1)
        fields = item_fields(self.vault.config, self._probe(), include_empty=True)
        extra_keys = {e["key"] for e in self._extra}
        row = 0
        for f in fields:
            if f["origin"] == "leftover" and f["key"] not in extra_keys:
                self._extra.append({"key": f["key"], "label": f["label"], "type": f["type"]})
                extra_keys.add(f["key"])
            editor = self._make_editor(f, self._values.get(f["key"]))
            k = label(f["label"], "fieldkey", wrap=True)
            k.setFixedWidth(140)
            k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(k, row, 0)
            k.setContentsMargins(0, 7, 0, 0)
            grid.addWidget(editor, row, 1)
            if f["key"] in extra_keys:
                rm = tool("x", tr("editor.remove_field"), None, 15)
                rm.clicked.connect(lambda _=False, key=f["key"]: self._remove_extra(key))
                grid.addWidget(rm, row, 2, Qt.AlignmentFlag.AlignTop)
            self._editors[f["key"]] = (f["type"], editor)
            row += 1
        lay.addLayout(grid)
        lay.addSpacing(10)
        add = button(tr("editor.add_field"), "ghost", "plus", slot=self._add_extra)
        lay.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(12)
        lay.addWidget(hline())
        lay.addSpacing(12)
        tags_row = QHBoxLayout()
        tl = label(tr("editor.tags"), "fieldkey")
        tl.setFixedWidth(132)
        tags_row.addWidget(tl)
        self.tags = TagEdit(sorted(self.index.tags.keys()) if self.index else [])
        self.tags.set_tags(self._data.get("tags", []))
        self.tags.textChanged.connect(self._changed)
        tags_row.addWidget(self.tags, 1)
        lay.addLayout(tags_row)
        lay.addStretch(1)
        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.scroll.setWidget(body)

    def _make_editor(self, f: dict, value) -> QWidget:
        t = f["type"]
        if t in ("secret", "pin"):
            w = SecretEdit(generator=True)
            w.setText(value or "")
            w.textChanged.connect(self._changed)
            w.generate_clicked.connect(lambda ed=w, mode=("pin" if t == "pin" else None): self._generate(ed, mode))
            return w
        if t == "multiline":
            w = QPlainTextEdit(value or "")
            w.setMinimumHeight(76)
            w.setMaximumHeight(140)
            w.textChanged.connect(self._changed)
            return w
        if t == "qa":
            w = QAEditor(value)
            w.changed.connect(self._changed)
            return w
        if t == "twofa":
            w = TwoFAEditor(value)
            w.changed.connect(self._changed)
            return w
        w = QLineEdit(str(value) if value else "")
        if t == "url":
            w.setPlaceholderText("https://")
        elif t == "date":
            w.setPlaceholderText(tr("editor.date_placeholder"))
        elif t == "email":
            w.setPlaceholderText("name@example.jp")
        w.textChanged.connect(self._changed)
        return w

    def _generate(self, editor: SecretEdit, mode: str | None) -> None:
        pop = GeneratorPopup(self.settings, mode, self)
        pop.use.connect(lambda v: (editor.setText(v), editor.edit.setFocus()))
        pop.popup_under(editor)
        self._popup = pop

    def _add_extra(self) -> None:
        dlg = AddFieldDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._values = self._collect_values()
            self._data["tags"] = self.tags.tags()
            self._extra.append(dlg.result_def())
            self._build_form()
            self._changed()

    def _remove_extra(self, key: str) -> None:
        self._values = self._collect_values()
        if not is_empty(self._values.get(key)):
            r = QMessageBox.question(self, tr("editor.remove_field"), tr("editor.remove_field_confirm"))
            if r != QMessageBox.StandardButton.Yes:
                return
        self._values.pop(key, None)
        self._extra = [e for e in self._extra if e["key"] != key]
        self._data["tags"] = self.tags.tags()
        self._build_form()
        self._changed()

    def _collect_values(self) -> dict:
        values = dict(self._values)
        for key, (t, w) in self._editors.items():
            if t in ("secret", "pin"):
                v = w.text()
            elif t == "multiline":
                v = w.toPlainText()
            elif t in ("qa", "twofa"):
                v = w.value()
            else:
                v = w.text().strip()
            if is_empty(v):
                values.pop(key, None)
            else:
                values[key] = v
        return values

    # ---------------------------------------------------------------- state
    def collect(self) -> dict:
        values = self._collect_values()
        extra = [e for e in self._extra if e["key"] in values or e["key"] in {k for k in self._editors}]
        data = copy.deepcopy(self._data)
        data.update({
            "title": self.title.text().strip(),
            "category": self.cat.currentData(),
            "sub": self.sub.currentData() or "",
            "status": self.status.currentData() or "active",
            "favorite": self.fav.isChecked(),
            "tags": self.tags.tags(),
            "fields": values,
            "extra": extra,
        })
        return data

    def _snapshot(self) -> str:
        return json.dumps(self.collect(), ensure_ascii=False, sort_keys=True)

    def _changed(self, *_) -> None:
        if self._building:
            return
        self._update_avatar()
        self._set_dirty(self._snapshot() != self._orig)

    def _set_dirty(self, dirty: bool) -> None:
        self.unsaved.setVisible(dirty)
        self.dirty_changed.emit(dirty)

    def is_dirty(self) -> bool:
        return self.vault is not None and self._snapshot() != self._orig

    def _update_avatar(self) -> None:
        cat = find_category(self.vault.config, self.cat.currentData()) if self.vault else None
        color = theme.cat_color(cat.get("color", "work")) if cat else theme.t("ink3")
        self.avatar.set(first_letter(self.title.text()), color)

    def save(self) -> None:
        data = self.collect()
        if not data["title"]:
            QMessageBox.warning(self, tr("editor.save"), tr("editor.need_title"))
            self.title.setFocus()
            return
        self.saved.emit(self.iid, data)

    def mark_saved(self) -> None:
        self._orig = self._snapshot()
        self._set_dirty(False)

    def cancel(self) -> None:
        if self.is_dirty():
            r = QMessageBox.question(self, tr("editor.cancel_title"), tr("editor.discard_confirm"))
            if r != QMessageBox.StandardButton.Yes:
                return
        self.cancelled.emit()
