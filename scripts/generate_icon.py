"""Generate PNG and multi-size ICO files from the original project SVG."""

from pathlib import Path
from struct import pack

from PySide6 import QtCore, QtGui, QtSvg

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "src" / "poker_trainer" / "resources"
SVG_PATH = RESOURCE_DIR / "peaceful_poker.svg"
PNG_PATH = RESOURCE_DIR / "peaceful_poker.png"
ICO_PATH = RESOURCE_DIR / "peaceful_poker.ico"
ICON_SIZES = (16, 32, 48, 256)


def render_png(size: int) -> bytes:
    """Render one square PNG payload from the source SVG."""
    renderer = QtSvg.QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load icon source: {SVG_PATH}")
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not render {size}px icon.")
    return bytes(buffer.data())


def write_ico(payloads: list[tuple[int, bytes]]) -> None:
    """Write a standards-compliant ICO containing PNG-compressed images."""
    header_size = 6 + 16 * len(payloads)
    offset = header_size
    entries: list[bytes] = []
    images: list[bytes] = []
    for size, payload in payloads:
        dimension = 0 if size >= 256 else size
        entries.append(pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(payload), offset))
        images.append(payload)
        offset += len(payload)
    ICO_PATH.write_bytes(pack("<HHH", 0, 1, len(payloads)) + b"".join(entries + images))


def main() -> None:
    """Create reproducible application icon assets."""
    payloads = [(size, render_png(size)) for size in ICON_SIZES]
    PNG_PATH.write_bytes(next(payload for size, payload in payloads if size == 256))
    write_ico(payloads)
    print(f"Generated {PNG_PATH}")
    print(f"Generated {ICO_PATH}")


if __name__ == "__main__":
    main()
