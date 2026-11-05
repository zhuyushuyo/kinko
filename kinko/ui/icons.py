"""Line icons (24px grid, 1.75 stroke) rendered from inline SVG in any colour."""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_DOT = 'fill="currentColor"'

ICONS: dict[str, str] = {
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "grid": '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/>'
            '<rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    "star": '<path d="M12 3.8l2.5 5.2 5.7.7-4.2 3.9 1.1 5.6L12 16.4l-5.1 2.8 1.1-5.6-4.2-3.9 5.7-.7z"/>',
    "star_fill": '<path d="M12 3.8l2.5 5.2 5.7.7-4.2 3.9 1.1 5.6L12 16.4l-5.1 2.8 1.1-5.6-4.2-3.9 5.7-.7z" fill="currentColor"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "bag": '<path d="M5.5 8.5h13l-1 11.5h-11z"/><path d="M9 8.5V7a3 3 0 0 1 6 0v1.5"/>',
    "cart": '<path d="M3.5 4.5h2l2.2 10.5h10.3l2-7.5H6.6"/><circle cx="9" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><ellipse cx="12" cy="12" rx="3.6" ry="8.5"/><path d="M3.5 12h17"/>',
    "yen": '<path d="M7 4.5l5 7 5-7"/><path d="M12 11.5V20"/><path d="M8 13h8M8 16.3h8"/>',
    "card": '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3 10h18"/><path d="M6.5 15h4"/>',
    "game": '<rect x="2.8" y="7.5" width="18.4" height="10" rx="5"/><path d="M7.8 10.5v4M5.8 12.5h4"/>'
            '<circle cx="15.3" cy="11.3" r=".6" ' + _DOT + '/><circle cx="17.3" cy="13.7" r=".6" ' + _DOT + '/>',
    "building": '<path d="M3.5 9L12 4.2 20.5 9z"/><path d="M5.8 11v6.5M9.9 11v6.5M14.1 11v6.5M18.2 11v6.5"/><path d="M3.8 20h16.4"/>',
    "briefcase": '<rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M9 7.5V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v1.5"/><path d="M3.5 12.5h17"/>',
    "home": '<path d="M4 11l8-6.5 8 6.5"/><path d="M6.2 9.4V19.5h11.6V9.4"/><path d="M10 19.5v-5h4v5"/>',
    "heart": '<path d="M12 19.5s-7.5-4.4-7.5-10A4 4 0 0 1 12 7.2a4 4 0 0 1 7.5 2.3c0 5.6-7.5 10-7.5 10z"/>',
    "book": '<path d="M4.5 5.5A1.5 1.5 0 0 1 6 4h12.5v14H6a1.5 1.5 0 0 0-1.5 1.5z"/><path d="M4.5 19.5A1.5 1.5 0 0 0 6 21h12.5v-3"/>',
    "school": '<path d="M2.5 9.5L12 5l9.5 4.5L12 14z"/><path d="M6.5 11.5v4c1.5 1.4 3.4 2 5.5 2s4-.6 5.5-2v-4"/><path d="M21.5 9.5v5"/>',
    "mail": '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7l8 6 8-6"/>',
    "phone": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 17.5h2"/>',
    "plane": '<path d="M20.5 4L3.5 11l6.5 2.5L12.5 20z"/><path d="M10 13.5l4.5-4.5"/>',
    "car": '<path d="M4.5 13l1.8-5a1.5 1.5 0 0 1 1.4-1h8.6a1.5 1.5 0 0 1 1.4 1l1.8 5"/><rect x="3.5" y="13" width="17" height="5" rx="1.5"/>'
           '<path d="M6.5 18v2M17.5 18v2"/><circle cx="7.5" cy="15.5" r=".6" ' + _DOT + '/><circle cx="16.5" cy="15.5" r=".6" ' + _DOT + '/>',
    "music": '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
    "film": '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M7.5 5v14M16.5 5v14M3.5 9.5h4M3.5 14.5h4M16.5 9.5h4M16.5 14.5h4"/>',
    "gift": '<rect x="4" y="9" width="16" height="4" rx="1"/><path d="M5.5 13v7h13v-7"/><path d="M12 9v11"/>'
            '<path d="M12 9c-1.5-3-5-3.5-5-1.5S10 9 12 9zM12 9c1.5-3 5-3.5 5-1.5S14 9 12 9z"/>',
    "cloud": '<path d="M7.5 18.5a4 4 0 0 1-.6-8 5.5 5.5 0 0 1 10.6 1.3A3.4 3.4 0 0 1 17 18.5z"/>',
    "wifi": '<path d="M3.5 9.5a12 12 0 0 1 17 0"/><path d="M6.5 12.8a7.7 7.7 0 0 1 11 0"/><path d="M9.5 16a3.4 3.4 0 0 1 5 0"/>'
            '<circle cx="12" cy="18.8" r=".7" ' + _DOT + '/>',
    "user": '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c.8-3.8 3.8-6 7.5-6s6.7 2.2 7.5 6"/>',
    "shield": '<path d="M12 3.5l7 3v5c0 4.4-3.1 7.7-7 9-3.9-1.3-7-4.6-7-9v-5z"/>',
    "shield_check": '<path d="M12 3.5l7 3v5c0 4.4-3.1 7.7-7 9-3.9-1.3-7-4.6-7-9v-5z"/><path d="M9 12l2.2 2.2L15.3 10"/>',
    "trash": '<path d="M4.8 7h14.4"/><path d="M9.5 7V5h5v2"/><path d="M6.8 7l.9 12.5h8.6L17.2 7"/>',
    "sliders": '<path d="M4.5 7h2.6M10.9 7h8.6M4.5 12h8.6M16.9 12h2.6M4.5 17h4.1M12.4 17h7.1"/><circle cx="9" cy="7" r="1.9"/>'
               '<circle cx="15" cy="12" r="1.9"/><circle cx="10.5" cy="17" r="1.9"/>',
    "lock": '<rect x="5.5" y="10.5" width="13" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
    "unlock": '<rect x="5.5" y="10.5" width="13" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 6.8-1.2"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6A1.5 1.5 0 0 0 14 4.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
    "eye": '<path d="M2.5 12C5 7.6 8.2 5.5 12 5.5s7 2.1 9.5 6.5c-2.5 4.4-5.7 6.5-9.5 6.5S5 16.4 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M3.5 3.5l17 17"/><path d="M10.6 6.1A9 9 0 0 1 12 6c3.8 0 7 2.1 9.5 6-1 1.7-2.1 3-3.4 4"/>'
               '<path d="M6.4 7.9C4.9 8.9 3.6 10.3 2.5 12c2.5 4.4 5.7 6.5 9.5 6.5 1.4 0 2.7-.3 3.9-.8"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "external": '<path d="M14 4.5h5.5V10"/><path d="M19.5 4.5L11 13"/><path d="M17 14v5.5H4.5V7H10"/>',
    "chev_down": '<path d="M6.5 9.5L12 15l5.5-5.5"/>',
    "chev_right": '<path d="M9.5 6.5L15 12l-5.5 5.5"/>',
    "chev_left": '<path d="M14.5 6.5L9 12l5.5 5.5"/>',
    "chev_up": '<path d="M6.5 14.5L12 9l5.5 5.5"/>',
    "alert": '<path d="M12 4.2l8.8 15.3H3.2z"/><path d="M12 10v4"/><circle cx="12" cy="16.9" r=".5" ' + _DOT + '/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".6" ' + _DOT + '/>',
    "history": '<path d="M4.6 12a7.4 7.4 0 1 0 2.2-5.3"/><path d="M4.6 4.8v3.6h3.6"/><path d="M12 8v4l2.6 1.6"/>',
    "more": '<circle cx="6" cy="12" r="1.4" ' + _DOT + '/><circle cx="12" cy="12" r="1.4" ' + _DOT + '/><circle cx="18" cy="12" r="1.4" ' + _DOT + '/>',
    "check": '<path d="M5.5 12.5L10 17l8.5-9.5"/>',
    "key": '<circle cx="8" cy="15.5" r="3.6"/><path d="M10.6 13L19 4.6"/><path d="M15.8 7.8l2.4 2.4M13.6 10l1.8 1.8"/>',
    "refresh": '<path d="M19.4 12a7.4 7.4 0 1 1-2.2-5.3"/><path d="M19.4 4.8v3.6h-3.6"/>',
    "sort": '<path d="M8 5v14M5 8l3-3 3 3"/><path d="M16 19V5M13 16l3 3 3-3"/>',
    "pen": '<path d="M4.5 19.5l1-4L15.6 5.4a2.1 2.1 0 0 1 3 3L8.5 18.5z"/>',
    "folder": '<path d="M3.5 7A1.5 1.5 0 0 1 5 5.5h4.5l2 2H19A1.5 1.5 0 0 1 20.5 9v8.5A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/>',
    "download": '<path d="M12 4.5v9"/><path d="M8.5 10l3.5 3.5 3.5-3.5"/><path d="M4.5 15.5V18a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-2.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "tag": '<path d="M3.8 12.6V5.3A1.5 1.5 0 0 1 5.3 3.8h7.3l7.6 7.6a1.5 1.5 0 0 1 0 2.1l-6.7 6.7a1.5 1.5 0 0 1-2.1 0z"/>'
           '<circle cx="8.3" cy="8.3" r="1.3"/>',
    "undo": '<path d="M9 7.5L5 11.5l4 4"/><path d="M5 11.5h9.5a4.5 4.5 0 0 1 0 9H11"/>',
    "arrow_up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "arrow_down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "keyboard": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M9.5 10h.01M13 10h.01M16.5 10h.01M6 14h.01M18 14h.01M9 14h6"/>',
    "palette": '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.1 0 1.7-.8 1.7-1.6 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.8-1.6 1.7-1.6H16a4.5 4.5 0 0 0 4.5-4.5C20.5 6.6 16.7 3.5 12 3.5z"/>'
               '<circle cx="7.5" cy="11.5" r=".8" ' + _DOT + '/><circle cx="10" cy="7.8" r=".8" ' + _DOT + '/><circle cx="14.5" cy="7.8" r=".8" ' + _DOT + '/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="2.8"/><path d="M5 6v12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V6"/><path d="M5 12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8"/>',
    "layers": '<path d="M12 4l8.5 4.5L12 13 3.5 8.5z"/><path d="M3.5 12.5L12 17l8.5-4.5"/><path d="M3.5 16.5L12 21l8.5-4.5"/>',
    "dice": '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r=".9" ' + _DOT + '/><circle cx="15" cy="15" r=".9" ' + _DOT + '/>'
            '<circle cx="15" cy="9" r=".9" ' + _DOT + '/><circle cx="9" cy="15" r=".9" ' + _DOT + '/>',
}

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
        'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

_cache: dict = {}


def svg_markup(name: str, color: str, width: float = 1.75) -> str:
    body = ICONS.get(name, ICONS["info"]).replace("currentColor", color)
    return _SVG.format(c=color, w=width, body=body)


def _dpr() -> float:
    app = QGuiApplication.instance()
    return app.devicePixelRatio() if app else 1.0


def render_svg(markup: str, size: int, dpr: float | None = None) -> QPixmap:
    dpr = dpr or max(_dpr(), 2.0)
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    r = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p, QRectF(0, 0, pm.width(), pm.height()))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def pixmap(name: str, color: str, size: int = 18, width: float = 1.75) -> QPixmap:
    key = (name, color, size, width)
    pm = _cache.get(key)
    if pm is None:
        pm = render_svg(svg_markup(name, color, width), size)
        _cache[key] = pm
    return pm


def icon(name: str, color: str, size: int = 18, active_color: str | None = None) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    if active_color:
        ic.addPixmap(pixmap(name, active_color, size), QIcon.Mode.Normal, QIcon.State.On)
        ic.addPixmap(pixmap(name, active_color, size), QIcon.Mode.Active, QIcon.State.Off)
    return ic


def mark_markup(bg: str = "#28457A", fg: str = "#F0F1EE") -> str:
    """The KINKO mark: a safe door with a dial."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            f'<rect width="32" height="32" rx="7" fill="{bg}"/>'
            f'<rect x="5.5" y="5.5" width="21" height="21" rx="3.5" fill="{fg}"/>'
            f'<rect x="3.7" y="9.4" width="2.6" height="3.4" rx="1" fill="{fg}"/>'
            f'<rect x="3.7" y="19.2" width="2.6" height="3.4" rx="1" fill="{fg}"/>'
            f'<circle cx="16" cy="16" r="6.1" fill="{bg}"/>'
            f'<circle cx="16" cy="16" r="2.3" fill="{fg}"/>'
            f'<rect x="15.1" y="10.2" width="1.8" height="2.6" rx=".6" fill="{fg}"/>'
            f'</svg>')


def mark_pixmap(size: int, bg: str = "#28457A", fg: str = "#F0F1EE") -> QPixmap:
    key = ("__mark__", size, bg, fg)
    pm = _cache.get(key)
    if pm is None:
        pm = render_svg(mark_markup(bg, fg), size)
        _cache[key] = pm
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256, 512):
        ic.addPixmap(render_svg(mark_markup(), s, 1.0))
    return ic


def clear_cache() -> None:
    _cache.clear()
