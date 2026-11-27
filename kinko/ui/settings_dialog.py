"""Settings: everything here is saved immediately and applied without restarting."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFontComboBox, QFrame,
                             QGridLayout, QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QLineEdit, QListWidget,
                             QScrollArea, QSpinBox, QStackedWidget, QTableWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..i18n import LANGUAGES, tr
from ..paths import config_dir, default_vault_dir, reveal_in_file_manager
from ..services import generator
from ..settings import DEFAULT_GENERATOR, DEFAULT_SHORTCUTS
from ..storage import backup
from . import theme
from .category_editor import CategoryEditor
from .formatting import fmt_date
from .generator_popup import SEPARATORS, colorize
from .widgets import Banner, Segmented, Switch, button, hline, label

PAGES = ("general", "appearance", "security", "generator", "categories", "backup", "shortcuts", "vault")
SHORTCUT_ORDER = ("search", "new_item", "edit_item", "save_item", "copy_password", "copy_username", "open_url",
                  "favorite", "trash_item", "lock", "settings")


class SettingsDialog(QDialog):
    reopen = pyqtSignal(int)

    def __init__(self, main, page: int = 0):
        super().__init__(main)
        self.main = main
        self.settings = main.settings
        self.vault = main.vault if (main.vault and main.vault.unlocked) else None
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(900, 640)
        self.resize(1000, 700)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setFixedWidth(200)
        lay.addWidget(self.nav)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        foot = QHBoxLayout()
        foot.setContentsMargins(28, 10, 24, 14)
        foot.addWidget(label(tr("settings.saved_note"), "smallfaint"))
        foot.addStretch(1)
        foot.addWidget(button(tr("common.close"), "primary", slot=self.accept))
        right.addLayout(foot)
        lay.addLayout(right, 1)
        builders = [self._general, self._appearance, self._security, self._generator, self._categories,
                    self._backup, self._shortcuts, self._vault_page]
        for key, build in zip(PAGES, builders):
            self.nav.addItem(tr(f"settings.page_{key}"))
            self.stack.addWidget(self._wrap(tr(f"settings.page_{key}"), build()))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(page)

    # ---------------------------------------------------------------- helpers
    def _wrap(self, title: str, content: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w = QWidget()
        w.setObjectName("SettingsBody")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 22, 28, 12)
        lay.setSpacing(14)
        lay.addWidget(label(title, "h1"))
        lay.addWidget(content)
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def _grid(self) -> tuple[QWidget, QGridLayout]:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(12)
        g.setColumnMinimumWidth(0, 190)
        g.setColumnStretch(1, 1)
        return w, g

    def _row(self, g: QGridLayout, text: str, widget, note: str = "") -> None:
        r = g.rowCount()
        k = label(text, "fieldkey", wrap=True)
        k.setFixedWidth(180)
        k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        g.addWidget(k, r, 0)
        k.setContentsMargins(0, 6, 0, 0)
        box = QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        if isinstance(widget, QWidget):
            box.addWidget(widget)
        else:
            box.addLayout(widget)
        box.addStretch(1)
        g.addLayout(box, r, 1)
        if note:
            g.addWidget(label(note, "smallfaint", wrap=True), r + 1, 1)

    def _check(self, key: str, text: str, after=None) -> QCheckBox:
        cb = Switch(text, bool(self.settings[key]))
        cb.toggled.connect(lambda v: (self.settings.set(key, bool(v)), after and after()))
        return cb

    def _spin(self, key: str, lo: int, hi: int, suffix: str = "", special: str = "", after=None) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setValue(int(self.settings[key]))
        if suffix:
            sp.setSuffix(suffix)
        if special:
            sp.setSpecialValueText(special)
        sp.setFixedWidth(130)
        sp.valueChanged.connect(lambda v: (self.settings.set(key, int(v)), after and after()))
        return sp

    def _locked_note(self) -> QWidget:
        return Banner("info", tr("settings.needs_unlock"), "lock")

    # ---------------------------------------------------------------- pages
    def _general(self) -> QWidget:
        w, g = self._grid()
        lang = QComboBox()
        names = {"ja": "日本語", "en": "English"}
        for code in LANGUAGES:
            lang.addItem(names[code], code)
        lang.setCurrentIndex(max(0, lang.findData(self.settings["language"])))
        lang.setFixedWidth(200)
        lang.currentIndexChanged.connect(lambda _: self._set_language(lang.currentData()))
        self._row(g, tr("settings.language"), lang, tr("settings.language_note"))
        self._row(g, tr("settings.startup"), self._check("open_last_vault", tr("settings.open_last")))
        folder = QHBoxLayout()
        self.vault_dir = QLineEdit(self.settings["vault_dir"] or str(default_vault_dir()))
        self.vault_dir.setReadOnly(True)
        folder.addWidget(self.vault_dir, 1)
        folder.addWidget(button(tr("common.change"), slot=self._choose_vault_dir))
        self._row(g, tr("settings.vault_dir"), folder, tr("settings.vault_dir_note"))
        self._row(g, tr("settings.trash_days"), self._spin("trash_days", 1, 365, tr("unit.days")),
                  tr("settings.trash_days_note"))
        cfg = QHBoxLayout()
        path = config_dir() / "settings.json"
        p = label(str(path), "smallfaint", wrap=True, selectable=True)
        cfg.addWidget(p, 1)
        cfg.addWidget(button(tr("settings.reveal"), slot=lambda: reveal_in_file_manager(path)))
        self._row(g, tr("settings.config_file"), cfg, tr("settings.config_file_note"))
        self._row(g, tr("settings.version"), label(f"KINKO {__version__}", "muted"))
        return w

    def _set_language(self, code: str) -> None:
        if code == self.settings["language"]:
            return
        self.settings.set("language", code)
        self.main.apply_language()
        self.reopen.emit(self.nav.currentRow())

    def _choose_vault_dir(self) -> None:
        start = Path(self.vault_dir.text())
        while not start.exists() and start != start.parent:
            start = start.parent
        path = QFileDialog.getExistingDirectory(self, tr("settings.vault_dir"), str(start))
        if path:
            self.settings.set("vault_dir", path)
            self.vault_dir.setText(path)

    def _appearance(self) -> QWidget:
        w, g = self._grid()
        th = Segmented([("light", tr("settings.theme_light")), ("dark", tr("settings.theme_dark")),
                        ("system", tr("settings.theme_system"))], self.settings["theme"])
        th.changed.connect(lambda v: self._appearance_set("theme", v))
        self._row(g, tr("settings.theme"), th)

        pal = QHBoxLayout()
        pal.setSpacing(6)
        for key in ("ai", "tokiwa", "kincha", "bengara"):
            sw = QLabel()
            sw.setFixedSize(16, 16)
            sw.setToolTip(tr(f"settings.palette_role.{key}"))
            sw.setStyleSheet(f"background: {theme.t(key)}; border-radius: 8px;")
            pal.addWidget(sw)
        pal.addSpacing(6)
        pal.addWidget(label(tr("settings.palette_name"), "muted"))
        pal.addStretch(1)
        pal.addWidget(button(tr("settings.palette_folder"), "ghost", "folder",
                             slot=lambda: reveal_in_file_manager(theme.override_file())))
        self._row(g, tr("settings.palette"), pal, tr("settings.palette_note"))

        dens = Segmented([("standard", tr("settings.density_standard")), ("compact", tr("settings.density_compact"))],
                         self.settings["density"])
        dens.changed.connect(lambda v: self._appearance_set("density", v))
        self._row(g, tr("settings.density"), dens)

        size = QSpinBox()
        size.setRange(11, 20)
        size.setSuffix(" px")
        size.setValue(int(self.settings["font_px"]))
        size.setFixedWidth(130)
        size.valueChanged.connect(lambda v: self._appearance_set("font_px", int(v)))
        self._row(g, tr("settings.font_size"), size)

        fam = QHBoxLayout()
        self.font_box = QFontComboBox()
        self.font_box.setFixedWidth(260)
        if self.settings["font_family"]:
            self.font_box.setCurrentFont(QFont(self.settings["font_family"]))
        self.font_box.currentFontChanged.connect(lambda f: self._appearance_set("font_family", f.family()))
        fam.addWidget(self.font_box)
        fam.addWidget(button(tr("settings.font_default"), "ghost",
                             slot=lambda: self._appearance_set("font_family", "")))
        fam.addStretch(1)
        self._row(g, tr("settings.font"), fam)

        sub = QComboBox()
        for key in ("username", "email", "url", "none"):
            sub.addItem(tr(f"settings.subtitle_{key}"), key)
        sub.setCurrentIndex(max(0, sub.findData(self.settings["list_subtitle"])))
        sub.setFixedWidth(240)
        sub.currentIndexChanged.connect(lambda _: (self.settings.set("list_subtitle", sub.currentData()),
                                                   self.main.refresh_views()))
        self._row(g, tr("settings.list_subtitle"), sub)

        sort = QComboBox()
        for key in ("recent", "name", "updated"):
            sort.addItem(tr(f"sort.{key}"), key)
        sort.setCurrentIndex(max(0, sort.findData(self.settings["sort"])))
        sort.setFixedWidth(240)
        sort.currentIndexChanged.connect(lambda _: (self.settings.set("sort", sort.currentData()),
                                                    self.main.refresh_views(rebuild=True)))
        self._row(g, tr("settings.sort"), sort)

        side = QVBoxLayout()
        side.setSpacing(6)
        for key in ("show_favorites", "show_recent", "show_tags", "show_health"):
            side.addWidget(self._check(key, tr(f"settings.{key}"), self.main.refresh_views))
        self._row(g, tr("settings.sidebar"), side)
        return w

    def _appearance_set(self, key: str, value) -> None:
        self.settings.set(key, value)
        self.main.apply_appearance()

    def _security(self) -> QWidget:
        w, g = self._grid()
        self._row(g, tr("settings.auto_lock"), self._spin("auto_lock_minutes", 0, 240, tr("unit.minutes"),
                                                          tr("settings.never")), tr("settings.auto_lock_note"))
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(self._check("lock_on_minimize", tr("settings.lock_minimize")))
        col.addWidget(self._check("lock_on_app_switch", tr("settings.lock_app_switch")))
        col.addWidget(self._check("lock_on_os_lock", tr("settings.lock_os")))
        self._row(g, tr("settings.lock_when"), col)
        self._row(g, tr("settings.clipboard"), self._spin("clipboard_seconds", 0, 600, tr("unit.seconds"),
                                                          tr("settings.never_clear")), tr("settings.clipboard_note"))
        if self.vault:
            g.addWidget(hline(), g.rowCount(), 0, 1, 2)
            self._row(g, tr("settings.master_password"),
                      button(tr("settings.change_password"), None, "key", slot=self.main.change_password),
                      tr("settings.change_password_note"))
            self._row(g, tr("settings.recovery_key"),
                      button(tr("settings.regenerate_recovery"), None, "refresh", slot=self.main.regenerate_recovery),
                      tr("settings.regenerate_note"))
            kdf = self.vault.kdf
            info = tr("settings.crypto_info", t=kdf.get("t"), m=int(kdf.get("m", 0)) // 1024, p=kdf.get("p"))
            self._row(g, tr("settings.crypto"), label(info, "muted", wrap=True))
        return w

    def _generator(self) -> QWidget:
        w, g = self._grid()
        gen = dict(DEFAULT_GENERATOR)
        gen.update(self.settings["generator"])

        def setg(key, value):
            cur = dict(self.settings["generator"])
            cur[key] = value
            self.settings.set("generator", cur)
            refresh()

        mode = QComboBox()
        for key in ("random", "words", "pin"):
            mode.addItem(tr(f"gen.{key}"), key)
        mode.setCurrentIndex(max(0, mode.findData(gen["mode"])))
        mode.setFixedWidth(240)
        mode.currentIndexChanged.connect(lambda _: setg("mode", mode.currentData()))
        self._row(g, tr("settings.gen_mode"), mode)
        length = QSpinBox()
        length.setRange(8, 64)
        length.setValue(int(gen["length"]))
        length.setFixedWidth(130)
        length.valueChanged.connect(lambda v: setg("length", int(v)))
        self._row(g, tr("gen.length"), length)
        chars = QGridLayout()
        chars.setHorizontalSpacing(24)
        chars.setVerticalSpacing(6)
        for i, key in enumerate(("upper", "lower", "digits", "symbols")):
            cb = QCheckBox(tr(f"gen.{key}"))
            cb.setChecked(bool(gen[key]))
            cb.toggled.connect(lambda v, k=key: setg(k, bool(v)))
            chars.addWidget(cb, i // 2, i % 2)
        amb = QCheckBox(tr("gen.avoid_ambiguous"))
        amb.setChecked(bool(gen["avoid_ambiguous"]))
        amb.toggled.connect(lambda v: setg("avoid_ambiguous", bool(v)))
        chars.addWidget(amb, 2, 0, 1, 2)
        self._row(g, tr("settings.gen_chars"), chars)
        sym = QLineEdit(gen["symbol_set"])
        sym.setFixedWidth(240)
        sym.editingFinished.connect(lambda: setg("symbol_set", sym.text() or DEFAULT_GENERATOR["symbol_set"]))
        self._row(g, tr("settings.gen_symbols"), sym, tr("settings.gen_symbols_note"))
        words = QSpinBox()
        words.setRange(3, 8)
        words.setValue(int(gen["words"]))
        words.setFixedWidth(130)
        words.valueChanged.connect(lambda v: setg("words", int(v)))
        self._row(g, tr("gen.word_count"), words)
        sep = QComboBox()
        for value, text in SEPARATORS:
            sep.addItem(tr(f"gen.sep_{text}") if text in ("space", "none") else text, value)
        sep.setCurrentIndex(max(0, sep.findData(gen["separator"])))
        sep.setFixedWidth(130)
        sep.currentIndexChanged.connect(lambda _: setg("separator", sep.currentData()))
        self._row(g, tr("gen.separator"), sep)
        opts = QHBoxLayout()
        opts.setSpacing(24)
        for key in ("capitalize", "word_digit"):
            cb = QCheckBox(tr(f"gen.{key}"))
            cb.setChecked(bool(gen[key]))
            cb.toggled.connect(lambda v, k=key: setg(k, bool(v)))
            opts.addWidget(cb)
        opts.addStretch(1)
        self._row(g, tr("settings.gen_words_opts"), opts)
        pin = QSpinBox()
        pin.setRange(4, 12)
        pin.setValue(int(gen["pin_length"]))
        pin.setFixedWidth(130)
        pin.valueChanged.connect(lambda v: setg("pin_length", int(v)))
        self._row(g, tr("gen.pin_length"), pin)
        preview = QLabel()
        preview.setTextFormat(Qt.TextFormat.RichText)
        preview.setFont(theme.mono_font(theme.font_px() + 3))
        preview.setProperty("role", "note")
        preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        def refresh():
            opts_ = dict(DEFAULT_GENERATOR)
            opts_.update(self.settings["generator"])
            preview.setText(colorize(generator.generate(opts_)))

        self._row(g, tr("settings.gen_preview"), preview)
        refresh()
        return w

    def _categories(self) -> QWidget:
        if not self.vault:
            return self._locked_note()
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(label(tr("cats.lead"), "muted", wrap=True))
        ed = CategoryEditor(self.vault)
        ed.setMinimumHeight(470)
        lay.addWidget(ed)
        return w

    def _backup(self) -> QWidget:
        w, g = self._grid()
        self._row(g, tr("settings.backup"), self._check("backup_enabled", tr("settings.backup_enabled")))
        folder = QHBoxLayout()
        current = self.settings["backup_dir"]
        if not current and self.vault:
            current = str(backup.backup_dir_for(self.vault.path))
        self.backup_dir = QLineEdit(current or tr("settings.backup_default"))
        self.backup_dir.setReadOnly(True)
        folder.addWidget(self.backup_dir, 1)
        folder.addWidget(button(tr("common.change"), slot=self._choose_backup_dir))
        folder.addWidget(button(tr("settings.default"), "ghost", slot=self._reset_backup_dir))
        self._row(g, tr("settings.backup_dir"), folder, tr("settings.backup_dir_note"))
        self._row(g, tr("settings.keep_latest"), self._spin("backup_keep_latest", 1, 200, tr("unit.copies")))
        self._row(g, tr("settings.keep_days"), self._spin("backup_keep_days", 0, 365, tr("unit.days"),
                                                          tr("settings.off")), tr("settings.keep_days_note"))
        if self.vault:
            last = self.main.backups.last
            self.last_backup = label(tr("settings.last_backup", t=last.strftime("%Y-%m-%d %H:%M")) if last
                                     else tr("settings.no_backup_yet"), "muted")
            self._row(g, tr("settings.status"), self.last_backup)
            row = QHBoxLayout()
            row.addWidget(button(tr("settings.backup_now"), "primary", "download", slot=self._backup_now))
            row.addWidget(button(tr("settings.restore"), None, "history", slot=self.main.restore_backup))
            row.addWidget(button(tr("settings.open_folder"), "ghost", "folder",
                                 slot=lambda: reveal_in_file_manager(self.main.backups.backup_dir() / "_")))
            row.addStretch(1)
            self._row(g, "", row)
        return w

    def _choose_backup_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("settings.backup_dir"), self.backup_dir.text())
        if path:
            self.settings.set("backup_dir", path)
            self.backup_dir.setText(path)

    def _reset_backup_dir(self) -> None:
        self.settings.set("backup_dir", "")
        self.backup_dir.setText(str(backup.backup_dir_for(self.vault.path)) if self.vault
                                else tr("settings.backup_default"))

    def _backup_now(self) -> None:
        dest = self.main.backups.run_now()
        if dest is not None and self.main.backups.last:
            self.last_backup.setText(tr("settings.last_backup", t=self.main.backups.last.strftime("%Y-%m-%d %H:%M")))

    def _shortcuts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(label(tr("settings.shortcuts_lead"), "muted", wrap=True))
        table = QTableWidget(len(SHORTCUT_ORDER), 2)
        table.setHorizontalHeaderLabels([tr("settings.sc_action"), tr("settings.sc_key")])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 220)
        table.setShowGrid(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        current = dict(DEFAULT_SHORTCUTS)
        current.update(self.settings["shortcuts"])
        self._seq_edits = {}
        from PyQt6.QtWidgets import QTableWidgetItem

        for row, key in enumerate(SHORTCUT_ORDER):
            table.setItem(row, 0, QTableWidgetItem(tr(f"sc.{key}")))
            ed = QKeySequenceEdit(QKeySequence(current.get(key, "")))
            if hasattr(ed, "setClearButtonEnabled"):
                ed.setClearButtonEnabled(True)
            ed.editingFinished.connect(lambda k=key, e=ed: self._set_shortcut(k, e))
            table.setCellWidget(row, 1, ed)
            table.setRowHeight(row, 40)
            self._seq_edits[key] = ed
        table.setMinimumHeight(40 * len(SHORTCUT_ORDER) + 40)
        lay.addWidget(table)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("settings.default_all"), "ghost", slot=self._reset_shortcuts))
        lay.addLayout(row)
        return w

    def _set_shortcut(self, key: str, ed: QKeySequenceEdit) -> None:
        seq = ed.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        cur = dict(self.settings["shortcuts"])
        cur[key] = seq
        self.settings.set("shortcuts", cur)
        self.main.apply_shortcuts()

    def _reset_shortcuts(self) -> None:
        self.settings.set("shortcuts", dict(DEFAULT_SHORTCUTS))
        for key, ed in self._seq_edits.items():
            ed.setKeySequence(QKeySequence(DEFAULT_SHORTCUTS[key]))
        self.main.apply_shortcuts()

    def _vault_page(self) -> QWidget:
        if not self.vault:
            return self._locked_note()
        v = self.vault
        w, g = self._grid()
        name = QLineEdit(v.name)
        name.editingFinished.connect(lambda: name.text().strip() and name.text().strip() != v.name and
                                     (v.set_meta_text("name", name.text().strip()), self.main.refresh_views()))
        self._row(g, tr("settings.vault_name"), name)
        hint = QLineEdit(v.hint)
        hint.editingFinished.connect(lambda: hint.text().strip() != v.hint and v.set_meta_text("hint", hint.text().strip()))
        self._row(g, tr("pwform.hint"), hint, tr("pwform.hint_note"))
        loc = QHBoxLayout()
        loc.addWidget(label(str(v.path), "small", wrap=True, selectable=True), 1)
        loc.addWidget(button(tr("settings.reveal"), slot=lambda: reveal_in_file_manager(v.path)))
        self._row(g, tr("settings.vault_file"), loc)
        self._row(g, tr("settings.vault_id"), label(v.vault_id, "small", selectable=True))
        self._row(g, tr("settings.vault_created"), label(fmt_date(v.created_at), "small"))
        n_items = sum(1 for r in v.items.values() if not r.trashed)
        self._row(g, tr("settings.vault_items"), label(tr("sidebar.count", n=n_items), "small"))
        return w
