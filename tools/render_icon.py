#!/usr/bin/env python3
"""Write the KINKO icon as files: SVG, PNG sizes and a Windows .ico.

    python tools/render_icon.py

The app draws its icon itself at start-up (kinko/ui/icons.py), so it needs none of these files.
They are for a desktop shortcut, the Dock or a later .app / .exe. Needs PyQt6.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PyQt6.QtSvg import QSvgRenderer  # noqa: E402

from kinko.ui.icons import mark_markup  # noqa: E402

FOLDER = ROOT / "assets" / "icon"
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def write_ico(path: Path, images: dict[int, bytes]) -> None:
    """A Windows icon file holding one PNG per size."""
    sizes = sorted(images)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    entries, blobs = b"", b""
    offset = len(header) + 16 * len(sizes)
    for size in sizes:
        blob = images[size]
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)
    path.write_bytes(header + entries + blobs)


def main() -> int:
    app = QGuiApplication(sys.argv)  # Qt needs one to draw
    svg = mark_markup().replace('viewBox="0 0 32 32"', 'viewBox="0 0 32 32" width="256" height="256"')
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / "kinko.svg").write_text(svg + "\n", encoding="utf-8")
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    sizes = sorted(set(PNG_SIZES) | set(ICO_SIZES))
    images = {size: render(renderer, size) for size in sizes}
    png = FOLDER / "png"
    png.mkdir(exist_ok=True)
    for size in PNG_SIZES:
        (png / f"kinko-{size}.png").write_bytes(images[size])
    write_ico(FOLDER / "kinko.ico", {size: images[size] for size in ICO_SIZES})
    print(f"Wrote kinko.svg, {len(PNG_SIZES)} PNG files and kinko.ico to {FOLDER.relative_to(ROOT)}")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
