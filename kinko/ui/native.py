"""Small OS hooks via ctypes (no extra packages). Every call is best effort."""
from __future__ import annotations

import ctypes
import ctypes.util
import sys

_MAC = sys.platform == "darwin"
_WIN = sys.platform == "win32"


# ---------------------------------------------------------------- Caps Lock

def caps_lock_on() -> bool:
    try:
        if _WIN:
            return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)  # type: ignore[attr-defined]
        if _MAC:
            lib = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
            lib.CGEventSourceFlagsState.restype = ctypes.c_uint64
            lib.CGEventSourceFlagsState.argtypes = [ctypes.c_int32]
            return bool(lib.CGEventSourceFlagsState(1) & 0x00010000)
    except Exception:  # noqa: BLE001
        return False
    return False


# ---------------------------------------------------------------- macOS screen lock

class MacScreenLock:
    """Polls CGSessionCopyCurrentDictionary()["CGSSessionScreenIsLocked"]."""

    def __init__(self):
        self.ok = False
        if not _MAC:
            return
        try:
            cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
            cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            cg.CGSessionCopyCurrentDictionary.restype = ctypes.c_void_p
            cf.CFDictionaryGetValue.restype = ctypes.c_void_p
            cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            cf.CFBooleanGetValue.restype = ctypes.c_bool
            cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            self._cg, self._cf = cg, cf
            self._key = cf.CFStringCreateWithCString(None, b"CGSSessionScreenIsLocked", 0x08000100)
            self.ok = bool(self._key)
        except Exception:  # noqa: BLE001
            self.ok = False

    def locked(self) -> bool:
        if not self.ok:
            return False
        try:
            d = self._cg.CGSessionCopyCurrentDictionary()
            if not d:
                return False
            try:
                v = self._cf.CFDictionaryGetValue(d, self._key)
                return bool(v) and bool(self._cf.CFBooleanGetValue(v))
            finally:
                self._cf.CFRelease(d)
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------- title bar colour

def set_dark_title_bar(window, dark: bool | None) -> None:
    """dark=None follows the OS."""
    try:
        if _MAC:
            _mac_appearance(dark)
        elif _WIN:
            hwnd = int(window.winId())
            value = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(  # type: ignore[attr-defined]
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
    except Exception:  # noqa: BLE001
        pass


def _mac_appearance(dark: bool | None) -> None:
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send0 = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
    send_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
    send_str = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(
        ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
    app = send0(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
    appearance = None
    if dark is not None:
        name = b"NSAppearanceNameDarkAqua" if dark else b"NSAppearanceNameAqua"
        ns_name = send_str(objc.objc_getClass(b"NSString"), objc.sel_registerName(b"stringWithUTF8String:"), name)
        appearance = send_ptr(objc.objc_getClass(b"NSAppearance"), objc.sel_registerName(b"appearanceNamed:"),
                              ns_name)
    send_ptr(app, objc.sel_registerName(b"setAppearance:"), appearance)


# ---------------------------------------------------------------- Windows session lock

def make_windows_lock_filter(on_lock):
    """Returns a QAbstractNativeEventFilter that calls on_lock() on WTS_SESSION_LOCK, or None."""
    if not _WIN:
        return None
    from ctypes import wintypes

    from PyQt6.QtCore import QAbstractNativeEventFilter

    class _Filter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, event_type, message):  # noqa: N802
            try:
                if bytes(event_type) == b"windows_generic_MSG":
                    msg = wintypes.MSG.from_address(int(message))
                    if msg.message == 0x02B1 and msg.wParam == 0x7:  # WM_WTSSESSION_CHANGE / LOCK
                        on_lock()
            except Exception:  # noqa: BLE001
                pass
            return False, 0

    return _Filter()


def register_windows_session_events(window) -> None:
    if not _WIN:
        return
    try:
        ctypes.windll.wtsapi32.WTSRegisterSessionNotification(int(window.winId()), 0)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
