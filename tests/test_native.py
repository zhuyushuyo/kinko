"""The Windows taskbar identity and the window icon sizes."""
import sys

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from kinko.ui import icons, native  # noqa: E402


@pytest.mark.skipif(sys.platform == "win32", reason="Windows sets the id")
def test_taskbar_id_is_windows_only():
    assert native.set_app_user_model_id() is False
    assert native.app_user_model_id() == ""


@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
def test_taskbar_id_on_windows():
    assert native.set_app_user_model_id() is True
    assert native.app_user_model_id() == native.APP_USER_MODEL_ID


def test_app_icon_has_the_taskbar_sizes():
    app = QApplication.instance() or QApplication([])  # kept alive while the icon is drawn
    sizes = {s.width() for s in icons.app_icon().availableSizes()}
    assert app is not None
    assert {16, 20, 24, 32, 40, 48, 64, 256} <= sizes
