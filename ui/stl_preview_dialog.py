"""Interactive STL/3MF viewer dialog used by the gallery."""

from __future__ import annotations

import os
from typing import Optional, Callable

import numpy as np
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

        base_rgb = np.asarray(vcolor.Color(face_hex).rgb, dtype=np.float32)
        light_dir = np.array([0.35, 0.6, 0.7], dtype=np.float32)
        norm = np.linalg.norm(light_dir)
        if norm == 0:
            light_dir = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            light_dir /= norm

        vertex_normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
        if vertex_normals.shape != vertices.shape:
            vertex_normals = np.zeros_like(vertices, dtype=np.float32)
            face_normals = np.asarray(mesh.face_normals, dtype=np.float32)
            for face, normal in zip(faces, face_normals):
                vertex_normals[face] += normal
            lengths = np.linalg.norm(vertex_normals, axis=1, keepdims=True)
            lengths[lengths == 0.0] = 1.0
            vertex_normals /= lengths

        intensities = np.clip(vertex_normals @ light_dir, -1.0, 1.0)
        intensities = 0.2 + 0.8 * np.clip(intensities, 0.0, 1.0)
        vertex_colors = np.clip(intensities[:, None] * base_rgb, 0.0, 1.0)
        alpha = np.ones((vertex_colors.shape[0], 1), dtype=np.float32)
        vertex_colors = np.hstack([vertex_colors, alpha])

        supports_directional = hasattr(scene.visuals, "DirectionalLight")
        shading_mode = "smooth" if supports_directional else None
        self._mesh_visual = scene.visuals.Mesh(
            vertices=vertices,
            faces=faces,
            vertex_colors=vertex_colors,
            shading=shading_mode,
        )
        self._mesh_visual.transform = STTransform(translate=-center)
        self._mesh_visual.parent = self._view.scene

        if hasattr(scene.visuals, "AmbientLight"):
            scene.visuals.AmbientLight(
                parent=self._view.scene,
                color=vcolor.Color(accent_hex).rgba,
            )
        if supports_directional:
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
    """Interactive window for orbiting around an STL or 3MF model."""

    def __init__(
        self,
        model_data: dict,
        *,
        dark_theme: bool = False,
        parent: Optional[QWidget] = None,
        ready_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._model_data = model_data or {}
        self._dark_theme = bool(dark_theme)
        self._ready_callback = ready_callback

        model_name = self._model_data.get("name") or "Model Preview"
        self.setWindowTitle(str(model_name))
        self.resize(960, 720)

        layout = QVBoxLayout(self)

        if not VISPY_AVAILABLE:
            layout.addWidget(self._build_error_label("VisPy is not installed; 3D preview is unavailable."))
            layout.addLayout(self._build_close_row())
            return

        self._model_files = self._collect_model_filenames()
        if not self._model_files:
            layout.addWidget(self._build_error_label("This model does not reference a 3D model file."))
            layout.addLayout(self._build_close_row())
            return

        self._file_selector: QComboBox | None = None
        if len(self._model_files) > 1:
            layout.addLayout(self._build_file_selector_row())

        self._viewer_container = QWidget(self)
        self._viewer_layout = QVBoxLayout(self._viewer_container)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._viewer_container)

        self._info_label = self._build_info_label("")
        layout.addWidget(self._info_label)

        layout.addLayout(self._build_controls_row())

        self._preview_widget: Optional[_InteractivePreview] = None
        self._current_filename: Optional[str] = None

        self._update_controls_enabled(False)
        self._load_and_display_model(self._model_files[0])

    def showEvent(self, event):
        super().showEvent(event)
        if self._ready_callback is not None:
            try:
                self._ready_callback()
            finally:
                self._ready_callback = None

    def _resolve_model_path(self, filename: Optional[str] = None) -> Optional[str]:
        folder = self._model_data.get("folder")
        if filename is None:
            if hasattr(self, "_model_files") and self._model_files:
                filename = self._model_files[0]
            else:
                filename = self._model_data.get("model_file") or self._model_data.get("stl_file")
        if not folder or not filename:
            return None
        candidate = os.path.join(folder, filename)
        if os.path.isfile(candidate):
            return candidate
        return None

    def _load_mesh(self, mesh_path: str) -> trimesh.Trimesh:
        mesh = trimesh.load_mesh(mesh_path, force="mesh", process=True)
        if isinstance(mesh, (list, tuple)):
            parts = [part for part in mesh if isinstance(part, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(parts) if parts else None
        if isinstance(mesh, trimesh.Scene):
            geoms = [geom for geom in mesh.geometry.values() if isinstance(geom, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(geoms) if geoms else None
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError("Unsupported mesh format.")
        if mesh.is_empty:
            raise ValueError("Mesh contains no geometry.")
        return mesh

    def _build_error_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        return label

    def _build_info_label(self, stl_path: Optional[str]) -> QLabel:
        label = QLabel(self._format_info_text(stl_path), self)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setObjectName("previewDetails")
        return label

    def _build_controls_row(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        controls.addStretch(1)

        self._reset_button = QPushButton("Reset View", self)
        self._reset_button.clicked.connect(self._on_reset_view)
        controls.addWidget(self._reset_button)

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

    def _collect_model_filenames(self) -> list[str]:
        files = self._model_data.get("model_files")
        if isinstance(files, (list, tuple)):
            collected = [str(name) for name in files if name]
            if collected:
                return collected
        fallback = self._model_data.get("model_file") or self._model_data.get("stl_file")
        return [str(fallback)] if fallback else []

    def _build_file_selector_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 12)
        label = QLabel("Model File:", self)
        row.addWidget(label)

        selector = QComboBox(self)
        for name in self._model_files:
            selector.addItem(name)
        selector.currentIndexChanged.connect(self._on_model_file_changed)
        row.addWidget(selector, 1)
        row.addStretch(1)
        self._file_selector = selector
        return row

    def _on_model_file_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._model_files):
            return
        filename = self._model_files[index]
        if filename == self._current_filename:
            return
        self._load_and_display_model(filename)

    def _load_and_display_model(self, filename: str) -> None:
        path = self._resolve_model_path(filename)
        if not path:
            self._show_error(f"Model file not found: {filename}")
            return
        try:
            mesh = self._load_mesh(path)
        except Exception as exc:
            self._show_error(f"Unable to load mesh:\n{exc}")
            return
        try:
            widget = _InteractivePreview(mesh, dark_theme=self._dark_theme, parent=self)
        except Exception as exc:
            self._show_error(f"Failed to initialise viewer:\n{exc}")
            return
        self._current_filename = filename
        self._set_viewer_widget(widget)
        self._update_info_label(path)

    def _set_viewer_widget(self, widget: _InteractivePreview) -> None:
        self._clear_viewer_container()
        self._preview_widget = widget
        self._viewer_layout.addWidget(widget)
        self._update_controls_enabled(True)

    def _clear_viewer_container(self) -> None:
        if not hasattr(self, "_viewer_layout"):
            return
        while self._viewer_layout.count():
            item = self._viewer_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()
        self._preview_widget = None

    def _show_error(self, message: str) -> None:
        self._clear_viewer_container()
        self._viewer_layout.addWidget(self._build_error_label(message))
        self._update_info_label(None)
        self._update_controls_enabled(False)
        self._current_filename = None

    def _update_info_label(self, stl_path: Optional[str]) -> None:
        if hasattr(self, "_info_label") and self._info_label is not None:
            self._info_label.setText(self._format_info_text(stl_path))

    def _format_info_text(self, stl_path: Optional[str]) -> str:
        parts: list[str] = []
        if stl_path:
            parts.append(f"Source: {os.path.basename(stl_path)}")
        else:
            parts.append("Source: (not available)")
        folder = self._model_data.get("folder") or ""
        if folder:
            parts.append(f"Folder: {os.path.basename(folder)}")
        print_time = self._model_data.get("print_time") or ""
        if print_time:
            parts.append(f"Print time: {print_time}")
        return " | ".join(parts)

    def _update_controls_enabled(self, enabled: bool) -> None:
        if hasattr(self, "_reset_button") and self._reset_button is not None:
            self._reset_button.setEnabled(enabled)

    def _on_reset_view(self) -> None:
        if self._preview_widget is not None:
            self._preview_widget.reset_view()