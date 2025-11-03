"""Interactive STL viewer dialog used by the gallery."""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from vispy import app, scene, color as vcolor
    from vispy.visuals.transforms import STTransform

    app.use_app("pyside6")
    VISPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    VISPY_AVAILABLE = False


DEFAULT_ELEVATION = 26.0
DEFAULT_AZIMUTH = 35.0


class _InteractivePreview(QWidget):
    """GPU-backed mesh viewer powered by VisPy."""

    def __init__(
        self,
        mesh: trimesh.Trimesh,
        *,
        dark_theme: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        if not VISPY_AVAILABLE:
            raise RuntimeError("VisPy backend is unavailable.")
        super().__init__(parent)
        self.setMinimumSize(560, 420)

        self._mesh = mesh
        self._dark_theme = dark_theme

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        background = "#0f1115" if dark_theme else "#f4f5f8"
        face_hex = "#8db4ff" if dark_theme else "#3a6db3"
        accent_hex = "#c5d7ff" if dark_theme else "#ffffff"

        self._canvas = scene.SceneCanvas(
            keys=None,
            size=(640, 480),
            bgcolor=background,
            show=False,
        )
        self._canvas.create_native()
        self._canvas.native.setParent(self)
        layout.addWidget(self._canvas.native)

        self._view = self._canvas.central_widget.add_view()
        self._view.camera = scene.cameras.TurntableCamera(
            fov=45.0,
            azimuth=DEFAULT_AZIMUTH,
            elevation=DEFAULT_ELEVATION,
            distance=2.0,
            up="+z",
        )

        self._camera = self._view.camera

        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.faces, dtype=np.uint32)
        if vertices.size == 0 or faces.size == 0:
            raise ValueError("Mesh contains no triangles.")

        lower, upper = mesh.bounds
        center = (lower + upper) / 2.0
        extent = upper - lower
        max_extent = float(np.max(extent))
        radius = max(0.5, max_extent * 0.6)
        self._radius = radius

        mesh_color = vcolor.Color(face_hex).rgba
        self._mesh_visual = scene.visuals.Mesh(
            vertices=vertices,
            faces=faces,
            color=mesh_color,
            shading="smooth",
        )
        self._mesh_visual.transform = STTransform(translate=-center)
        self._mesh_visual.parent = self._view.scene

        scene.visuals.AmbientLight(
            parent=self._view.scene,
            color=vcolor.Color(accent_hex).rgba,
        )
        scene.visuals.DirectionalLight(
            parent=self._view.scene,
            color=vcolor.Color("#ffffff").rgba,
            direction=(0.7, 1.0, 1.3),
        )
        scene.visuals.DirectionalLight(
            parent=self._view.scene,
            color=vcolor.Color("#7690d0").rgba,
            direction=(-0.6, -0.8, -0.4),
        )

        self._default_distance = self._radius * 2.8
        self._camera.distance = self._default_distance
        self._camera.center = (0.0, 0.0, 0.0)
        near_clip = max(0.01, self._radius / 100.0)
        far_clip = self._radius * 12.0
        self._camera.clip_planes = (near_clip, far_clip)
        span = self._radius * 1.2
        self._camera.set_range(x=(-span, span), y=(-span, span), z=(-span, span))

    def reset_view(self) -> None:
        self._camera.azimuth = DEFAULT_AZIMUTH
        self._camera.elevation = DEFAULT_ELEVATION
        self._camera.distance = self._default_distance
        self._camera.center = (0.0, 0.0, 0.0)

    def close(self) -> None:  # pragma: no cover - cleanup helper
        try:
            self._canvas.close()
        finally:
            super().close()


class StlPreviewDialog(QDialog):
    """Interactive window for orbiting around an STL model."""

    def __init__(
        self,
        model_data: dict,
        *,
        dark_theme: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._model_data = model_data or {}
        self._dark_theme = bool(dark_theme)

        model_name = self._model_data.get("name") or "Model Preview"
        self.setWindowTitle(str(model_name))
        self.resize(960, 720)

        layout = QVBoxLayout(self)

        if not VISPY_AVAILABLE:
            layout.addWidget(self._build_error_label("VisPy is not installed; 3D preview is unavailable."))
            layout.addLayout(self._build_close_row())
            return

        stl_path = self._resolve_stl_path()
        if not stl_path:
            layout.addWidget(self._build_error_label("This model does not reference an STL file."))
            layout.addLayout(self._build_close_row())
            return

        try:
            mesh = self._load_mesh(stl_path)
        except Exception as exc:
            layout.addWidget(self._build_error_label(f"Unable to load mesh:\n{exc}"))
            layout.addLayout(self._build_close_row())
            return

        try:
            self._preview_widget = _InteractivePreview(mesh, dark_theme=self._dark_theme, parent=self)
        except Exception as exc:  # pragma: no cover - defensive guard
            layout.addWidget(self._build_error_label(f"Failed to initialise viewer:\n{exc}"))
            layout.addLayout(self._build_close_row())
            return

        layout.addWidget(self._preview_widget)
        layout.addWidget(self._build_info_label(stl_path))
        layout.addLayout(self._build_controls_row())

    def _resolve_stl_path(self) -> Optional[str]:
        folder = self._model_data.get("folder")
        stl_name = self._model_data.get("stl_file")
        if not folder or not stl_name:
            return None
        candidate = os.path.join(folder, stl_name)
        if os.path.isfile(candidate):
            return candidate
        return None

    def _load_mesh(self, stl_path: str) -> trimesh.Trimesh:
        mesh = trimesh.load_mesh(stl_path, force="mesh", process=True)
        if mesh.is_empty:
            raise ValueError("Mesh contains no geometry.")
        return mesh

    def _build_error_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        return label

    def _build_info_label(self, stl_path: str) -> QLabel:
        folder = self._model_data.get("folder") or ""
        print_time = self._model_data.get("print_time") or ""
        parts = [f"Source: {os.path.basename(stl_path)}"]
        if folder:
            parts.append(f"Folder: {os.path.basename(folder)}")
        if print_time:
            parts.append(f"Print time: {print_time}")
        label = QLabel(" | ".join(parts), self)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setObjectName("previewDetails")
        return label

    def _build_controls_row(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        controls.addStretch(1)

        reset_btn = QPushButton("Reset View", self)
        reset_btn.clicked.connect(self._preview_widget.reset_view)
        controls.addWidget(reset_btn)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)

        return controls

    def _build_close_row(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        controls.addStretch(1)
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)
        controls.addStretch(1)
        return controls