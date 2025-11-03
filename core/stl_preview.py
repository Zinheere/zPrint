from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import trimesh
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor

__all__ = ["render_stl_preview"]


def render_stl_preview(
	stl_path: str | Path,
	size: QSize | tuple[int, int] = QSize(320, 240),
	*,
	dark_theme: bool = False,
) -> QPixmap | None:
	"""Render an STL file into a tinted `QPixmap` for gallery previews.

	The mesh is loaded with `trimesh`, plotted with Matplotlib's 3D toolkit,
	and rasterised off-screen so PySide can display it without an OpenGL
	widget. Returns `None` if the STL cannot be parsed or rendered.
	"""

	mesh = _load_mesh(stl_path)
	if mesh is None or mesh.is_empty:
		return None

	target_size = _coerce_qsize(size)
	width = max(64, target_size.width())
	height = max(64, target_size.height())
	dpi = 100

	figure = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
	background, face_color, edge_color = _palette(dark_theme)
	figure.patch.set_facecolor(background)
	canvas = FigureCanvas(figure)

	axis = figure.add_subplot(111, projection="3d")
	axis.set_facecolor(background)
	axis.set_axis_off()

	triangles = mesh.triangles
	if isinstance(triangles, np.ndarray) and triangles.size:
		collection = Poly3DCollection(
			triangles,
			linewidths=0.1,
			facecolor=face_color,
			edgecolor=edge_color,
			antialiased=True,
		)
		axis.add_collection3d(collection)

	_configure_view(axis, mesh)

	canvas.draw()
	image = np.asarray(canvas.buffer_rgba()).copy()
	if image.size == 0:
		return None

	height_px, width_px, _ = image.shape
	qimage = QImage(image.data, width_px, height_px, width_px * 4, QImage.Format_RGBA8888)
	# copy to detach from numpy buffer before returning
	pixmap = QPixmap.fromImage(qimage.copy())
	if pixmap.isNull():
		return None
	if pixmap.size() != target_size:
		scaled = pixmap.scaled(
			target_size,
			aspectMode=Qt.KeepAspectRatio,
			mode=Qt.SmoothTransformation,
		)
		framed = QPixmap(target_size)
		framed.fill(QColor(background))
		painter = QPainter(framed)
		offset_x = (target_size.width() - scaled.width()) // 2
		offset_y = (target_size.height() - scaled.height()) // 2
		painter.drawPixmap(offset_x, offset_y, scaled)
		painter.end()
		pixmap = framed
	else:
		# ensure background is opaque even if renderer left margins transparent
		with_background = QPixmap(target_size)
		with_background.fill(QColor(background))
		painter = QPainter(with_background)
		painter.drawPixmap(0, 0, pixmap)
		painter.end()
		pixmap = with_background
	return pixmap


def _load_mesh(stl_path: str | Path) -> trimesh.Trimesh | None:
	try:
		return trimesh.load_mesh(stl_path, force="mesh", process=True)
	except Exception:
		return None


def _coerce_qsize(value: QSize | tuple[int, int]) -> QSize:
	if isinstance(value, QSize):
		return value
	width, height = value
	return QSize(int(width), int(height))


def _palette(dark: bool) -> tuple[str, tuple[float, float, float, float], tuple[float, float, float, float]]:
	if dark:
		return (
			"#0f1115",
			(0.55, 0.8, 1.0, 0.9),
			(0.1, 0.2, 0.3, 0.2),
		)
	return (
		"#f4f5f8",
		(0.15, 0.45, 0.85, 0.9),
		(0.0, 0.2, 0.4, 0.15),
	)


def _configure_view(axis, mesh: trimesh.Trimesh) -> None:
	axis.view_init(elev=26, azim=35)
	axis.dist = 7  # type: ignore[attr-defined]

	bounds = mesh.bounds
	if bounds.size == 0:
		return
	lower, upper = bounds
	extents = upper - lower
	max_extent = float(np.max(extents)) or 1.0
	center = mesh.centroid
	padding = max_extent * 0.35

	for center_value, axis_setter in zip(center, (axis.set_xlim, axis.set_ylim, axis.set_zlim)):
		axis_setter(center_value - padding, center_value + padding)

	axis.set_box_aspect((1.0, 1.0, 1.0))

