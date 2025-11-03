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
	mesh_path: str | Path | None,
	size: QSize | tuple[int, int] = QSize(320, 240),
	*,
	dark_theme: bool = False,
	mesh: trimesh.Trimesh | None = None,
	view_angles: tuple[float, float] | None = None,
	distance_scale: float = 1.0,
	quality_scale: float = 1.0,
) -> QPixmap | None:
	"""Render an STL or 3MF file into a tinted `QPixmap` for gallery previews.

	The mesh is loaded with `trimesh`, plotted with Matplotlib's 3D toolkit,
	and rasterised off-screen so PySide can display it without an OpenGL
	widget. Returns `None` if the model cannot be parsed or rendered. The
	`quality_scale` argument allows callers to trade detail for speed during
	interactive updates (valid range 0.3-1.0).
	"""

	if mesh is None:
		if not mesh_path:
			return None
		mesh = _load_mesh(mesh_path)
	if mesh is None or mesh.is_empty:
		return None

	target_size = _coerce_qsize(size)
	quality_scale = float(np.clip(quality_scale, 0.3, 1.0))
	width = max(64, int(target_size.width() * quality_scale))
	height = max(64, int(target_size.height() * quality_scale))
	dpi = int(70 + 30 * quality_scale)

	figure = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
	background, face_color, edge_color = _palette(dark_theme)
	figure.patch.set_facecolor(background)
	canvas = FigureCanvas(figure)

	axis = figure.add_subplot(111, projection="3d")
	axis.set_facecolor(background)
	axis.set_axis_off()
	axis.set_position([0.0, 0.0, 1.0, 1.0])

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

	_configure_view(axis, mesh, view_angles=view_angles, distance_scale=distance_scale)

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


def _load_mesh(mesh_path: str | Path) -> trimesh.Trimesh | None:
	try:
		loaded = trimesh.load_mesh(mesh_path, force="mesh", process=True)
		if isinstance(loaded, (list, tuple)):
			loaded = trimesh.util.concatenate([mesh for mesh in loaded if isinstance(mesh, trimesh.Trimesh)])
		if isinstance(loaded, trimesh.Scene):
			geoms = [geom for geom in loaded.geometry.values() if isinstance(geom, trimesh.Trimesh)]
			if geoms:
				loaded = trimesh.util.concatenate(geoms)
			else:
				loaded = None
		if isinstance(loaded, trimesh.Trimesh):
			return loaded
	except Exception:
		return None
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


def _configure_view(
	axis,
	mesh: trimesh.Trimesh,
	*,
	view_angles: tuple[float, float] | None = None,
	distance_scale: float = 1.0,
) -> None:
	if view_angles is None:
		elev, azim = 26, 35
	else:
		elev, azim = view_angles
	axis.view_init(elev=elev, azim=azim)
	try:
		distance = max(0.2, 7.0 * float(distance_scale))
		axis.dist = distance  # type: ignore[attr-defined]
	except Exception:
		pass

	bounds = mesh.bounds
	if bounds.size == 0:
		return
	lower, upper = bounds
	extents = upper - lower
	half_extents = extents / 2.0
	max_half_extent = float(np.max(half_extents)) or 1.0
	radius = max_half_extent * 1.2
	center = (lower + upper) / 2.0

	for center_value, axis_setter in zip(center, (axis.set_xlim, axis.set_ylim, axis.set_zlim)):
		axis_setter(center_value - radius, center_value + radius)

	axis.set_box_aspect((1.0, 1.0, 1.0))

