from __future__ import annotations

import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor

try:
    from PySide6.QtSvg import QSvgRenderer  # type: ignore
except Exception:  # pragma: no cover - QtSvg might be missing
    QSvgRenderer = None


def tint_icon(path: str, hex_color: str, size: QSize | None = None) -> QIcon:
    """Render an icon tinted to the requested color.

    Prefers high-fidelity SVG rendering via QSvgRenderer when available and
    applies a heuristic cleanup to strip full-canvas background rectangles so
    theme tinting works reliably. Falls back to standard QIcon painting when
    QtSvg support is unavailable or the file is not an SVG.
    """
    try:
        if size is None:
            size = QSize(64, 64)
        width = max(1, size.width())
        height = max(1, size.height())

        renderer = _create_svg_renderer(path) if path.lower().endswith('.svg') else None
        if renderer is not None and renderer.isValid():
            base_pixmap = QPixmap(width, height)
            base_pixmap.fill(Qt.transparent)

            painter = QPainter(base_pixmap)
            renderer.render(painter)
            painter.end()

            tinted = QPixmap(width, height)
            tinted.fill(Qt.transparent)
            painter = QPainter(tinted)
            painter.fillRect(0, 0, width, height, QColor(hex_color))
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawPixmap(0, 0, base_pixmap)
            painter.end()
            return QIcon(tinted)

        fallback = QIcon(path)
        if fallback.isNull():
            return QIcon()
        base_pixmap = QPixmap(width, height)
        base_pixmap.fill(Qt.transparent)
        painter = QPainter(base_pixmap)
        fallback.paint(painter, 0, 0, width, height)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(0, 0, width, height, QColor(hex_color))
        painter.end()
        return QIcon(base_pixmap)
    except Exception:
        return QIcon()


def _create_svg_renderer(path: str):
    if QSvgRenderer is None:
        return None
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            svg_text = handle.read()
    except Exception:
        try:
            return QSvgRenderer(path)
        except Exception:
            return None

    try:
        root = ET.fromstring(svg_text)
    except Exception:
        try:
            return QSvgRenderer(path)
        except Exception:
            return None

    view_box = root.attrib.get('viewBox', '')
    vb_width = vb_height = None
    if view_box:
        parts = [segment for segment in view_box.replace(',', ' ').split(' ') if segment.strip()]
        if len(parts) == 4:
            try:
                vb_width = float(parts[2])
                vb_height = float(parts[3])
            except Exception:
                vb_width = vb_height = None

    removed_any = False
    for parent in list(root.iter()):
        for element in list(parent):
            if not element.tag.lower().endswith('rect'):
                continue
            width_attr = element.attrib.get('width', '')
            height_attr = element.attrib.get('height', '')
            x_attr = element.attrib.get('x', '0')
            y_attr = element.attrib.get('y', '0')
            style = element.attrib.get('style', '')
            fill = element.attrib.get('fill', '')

            def _to_float(value: str):
                try:
                    return float(value.replace('px', ''))
                except Exception:
                    return None

            is_percent_full = (
                width_attr.strip().endswith('%')
                and height_attr.strip().endswith('%')
                and width_attr.strip().startswith('100')
                and height_attr.strip().startswith('100')
            )
            width_num = _to_float(width_attr)
            height_num = _to_float(height_attr)
            x_num = _to_float(x_attr) or 0.0
            y_num = _to_float(y_attr) or 0.0
            matches_viewbox = (
                vb_width is not None
                and vb_height is not None
                and width_num == vb_width
                and height_num == vb_height
                and abs(x_num) < 1e-6
                and abs(y_num) < 1e-6
            )
            has_fill = (
                ('fill:' in style and 'fill:none' not in style.replace(' ', '').lower())
                or (fill and fill.lower() != 'none')
            )
            if has_fill and (is_percent_full or matches_viewbox):
                try:
                    parent.remove(element)
                    removed_any = True
                except Exception:
                    continue

    if removed_any:
        try:
            cleaned = ET.tostring(root, encoding='utf-8')
            return QSvgRenderer(QByteArray(cleaned))
        except Exception:
            pass
    try:
        return QSvgRenderer(path)
    except Exception:
        return None
