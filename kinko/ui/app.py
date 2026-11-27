"""Application start-up: settings, language, theme, crash log, main window."""
from __future__ import annotations

import logging
import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from .. import __version__
from ..i18n import set_language, tr
from ..paths import config_dir
from ..settings import Settings
from . import icons, native, theme


def _setup_logging() -> logging.Logger:
    log = logging.getLogger("kinko")
    try:
        d = config_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        h = logging.FileHandler(d / "kinko.log", encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    except OSError:
        pass
    return log


def run(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    native.set_app_user_model_id()  # Windows: our own taskbar button and icon, not Python's
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("KINKO")
    app.setApplicationDisplayName("KINKO")
    app.setOrganizationName("KINKO")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setWindowIcon(icons.app_icon())

    log = _setup_logging()
    log.info("start KINKO %s", __version__)

    settings = Settings()
    set_language(settings["language"])
    theme.apply(app, settings)

    from .main_window import MainWindow

    win = MainWindow(settings)

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error(text)
        QMessageBox.critical(win, "KINKO", tr("error.unexpected", error=exc))

    sys.excepthook = excepthook

    def on_scheme_changed(*_):
        if settings["theme"] == "system":
            win.apply_appearance()

    try:
        app.styleHints().colorSchemeChanged.connect(on_scheme_changed)
    except AttributeError:
        pass
    win.show()
    return app.exec()
