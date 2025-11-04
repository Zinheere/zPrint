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

        background = "#0d0f14" if dark_theme else "#eef2fa"
        face_hex = "#9fc6ff" if dark_theme else "#2f6bc5"
        accent_hex = "#d6e4ff" if dark_theme else "#ffffff"

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
        vertex_colors = np.clip(vertex_colors * 1.15 + 0.08, 0.0, 1.0)
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
            scene.visuals.DirectionalLight(
                parent=self._view.scene,
                color=vcolor.Color("#ffd7a1").rgba,
                direction=(0.3, -0.5, 0.9),
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


class _GcodePreview(QWidget):
    """Simple toolpath viewer that renders G-code moves as line strips."""

    def __init__(
        self,
        points: np.ndarray,
        *,
        dark_theme: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        if not VISPY_AVAILABLE:
            raise RuntimeError("VisPy backend is unavailable.")
        if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < 2:
            raise ValueError("Toolpath requires at least two 3D points.")
        super().__init__(parent)
        self.setMinimumSize(560, 420)

        self._points = points.astype(np.float32, copy=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        background = "#0f1115" if dark_theme else "#f4f5f8"
        path_hex = "#34C759" if dark_theme else "#1C7C54"

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
            fov=0.0,
            elevation=60.0,
            azimuth=45.0,
            up="+z",
        )
        self._camera = self._view.camera

        lower = np.min(self._points, axis=0)
        upper = np.max(self._points, axis=0)
        center = (lower + upper) / 2.0
        extent = upper - lower
        max_extent = float(np.max(extent)) or 1.0
        radius = max(0.5, max_extent * 0.6)

        path_color = vcolor.Color(path_hex).rgba
        path_visual = scene.visuals.Line(
            pos=self._points - center,
            color=path_color,
            width=2.2,
            connect="strip",
        )
        path_visual.parent = self._view.scene
        self._line_visual = path_visual

        floor_z = float(np.min(self._points[:, 2])) if self._points.size else 0.0
        shadow_points = self._points.copy()
        shadow_points[:, 2] = floor_z - 0.02
        shadow_visual = scene.visuals.Line(
            pos=shadow_points - center,
            color=(0.0, 0.0, 0.0, 0.22),
            width=3.5,
            connect="strip",
        )
        shadow_visual.parent = self._view.scene
        self._shadow_visual = shadow_visual

        grid_color = (0.2, 0.2, 0.2, 0.3) if dark_theme else (0.4, 0.4, 0.4, 0.3)
        ground = scene.visuals.GridLines(color=grid_color, parent=self._view.scene)
        ground.transform = STTransform(translate=(0.0, 0.0, -center[2]))
        self._ground = ground

        self._default_distance = radius * 2.5
        self._camera.distance = self._default_distance
        self._camera.center = (0.0, 0.0, 0.0)
        self._camera.up = "+z"
        span = radius * 1.3
        self._camera.set_range(x=(-span, span), y=(-span, span), z=(-span, span))
        near_clip = max(0.01, radius / 200.0)
        far_clip = radius * 15.0
        self._camera.clip_planes = (near_clip, far_clip)

    def reset_view(self) -> None:
        self._camera.elevation = 60.0
        self._camera.azimuth = 45.0
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

        self._gcode_files = self._collect_gcode_filenames()
        self._file_entries = self._build_file_entries()

        self._file_selector: QComboBox | None = None
        if len(self._file_entries) > 1:
            layout.addLayout(self._build_file_selector_row())

        self._viewer_container = QWidget(self)
        self._viewer_layout = QVBoxLayout(self._viewer_container)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._viewer_container)

        self._info_label = self._build_info_label("")
        layout.addWidget(self._info_label)

        layout.addLayout(self._build_controls_row())

        self._preview_widget = None
        self._current_filename = None
        self._current_entry_type = None

        self._update_controls_enabled(False)
        self._load_entry(self._file_entries[0])

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

    def _resolve_gcode_path(self, filename: Optional[str]) -> Optional[str]:
        folder = self._model_data.get("folder")
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

    def _build_info_label(self, initial_path: Optional[str]) -> QLabel:
        label = QLabel(
            self._format_info_text(
                initial_path,
                entry_type="model",
                truncated=False,
                size_bytes=None,
            ),
            self,
        )
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

        self._gcode_button = QPushButton("Preview G-code", self)
        self._gcode_button.clicked.connect(self._on_preview_gcode)
        controls.addWidget(self._gcode_button)

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

    def _collect_gcode_filenames(self) -> list[str]:
        entries = self._model_data.get("gcodes")
        names: list[str] = []
        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict):
                    name = item.get("file")
                    if name:
                        names.append(str(name))
        return names

    def _build_file_entries(self) -> list[dict]:
        entries: list[dict] = []
        for name in self._model_files:
            entries.append({"type": "model", "name": name})
        for name in self._gcode_files:
            entries.append({"type": "gcode", "name": name})
        return entries

    def _build_file_selector_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 12)
        label = QLabel("File:", self)
        row.addWidget(label)

        selector = QComboBox(self)
        for entry in self._file_entries:
            prefix = "G-code" if entry["type"] == "gcode" else "Model"
            selector.addItem(f"{prefix}: {entry['name']}")
        selector.currentIndexChanged.connect(self._on_entry_index_changed)
        row.addWidget(selector, 1)
        row.addStretch(1)
        self._file_selector = selector
        return row

    def _on_entry_index_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._file_entries):
            return
        entry = self._file_entries[index]
        if entry.get("name") == self._current_filename and entry.get("type") == self._current_entry_type:
            return
        self._load_entry(entry)

    def _load_entry(self, entry: dict) -> None:
        entry_type = entry.get("type") or "model"
        name = entry.get("name")
        if not name:
            return
        if entry_type == "gcode":
            self._display_gcode(str(name))
        else:
            self._load_and_display_model(str(name))

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
        self._current_entry_type = "model"
        self._set_viewer_widget(widget, entry_type="model")
        size_bytes = None
        try:
            size_bytes = os.path.getsize(path)
        except Exception:
            size_bytes = None
        self._update_info_label(path, entry_type="model", truncated=False, size_bytes=size_bytes)

    def _display_gcode(self, filename: str) -> None:
        path = self._resolve_gcode_path(filename)
        if not path:
            self._show_error(f"G-code file not found: {filename}")
            return
        size_bytes = None
        try:
            size_bytes = os.path.getsize(path)
        except Exception:
            size_bytes = None

        try:
            toolpath, downsampled = self._load_gcode_toolpath(path)
        except Exception as exc:
            self._show_error(f"Unable to parse G-code:\n{exc}")
            return

        try:
            widget = _GcodePreview(toolpath, dark_theme=self._dark_theme, parent=self)
        except Exception as exc:
            self._show_error(f"Failed to initialise G-code viewer:\n{exc}")
            return

        self._current_filename = filename
        self._current_entry_type = "gcode"
        self._set_viewer_widget(widget, entry_type="gcode")
        self._update_info_label(path, entry_type="gcode", truncated=downsampled, size_bytes=size_bytes)

    def _load_gcode_toolpath(self, path: str, *, max_points: int = 250_000) -> tuple[np.ndarray, bool]:
        positions: list[list[float]] = []
        x = y = z = 0.0
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                stripped = line.split(";", 1)[0].strip()
                if not stripped:
                    continue
                upper = stripped.upper()
                if not (upper.startswith("G0") or upper.startswith("G1")):
                    continue
                tokens = upper.split()
                if not tokens:
                    continue
                new_x, new_y, new_z = x, y, z
                for token in tokens[1:]:
                    if len(token) < 2:
                        continue
                    axis = token[0]
                    try:
                        value = float(token[1:])
                    except ValueError:
                        continue
                    if axis == "X":
                        new_x = value
                    elif axis == "Y":
                        new_y = value
                    elif axis == "Z":
                        new_z = value
                moved = (new_x != x) or (new_y != y) or (new_z != z)
                if moved:
                    if not positions:
                        positions.append([x, y, z])
                    positions.append([new_x, new_y, new_z])
                x, y, z = new_x, new_y, new_z

        if len(positions) < 2:
            raise ValueError("Toolpath is empty or contains no motion commands.")

        points = np.asarray(positions, dtype=np.float32)
        downsampled = points.shape[0] > max_points
        if downsampled:
            indices = np.linspace(0, points.shape[0] - 1, max_points, dtype=np.int32)
            points = points[indices]
        return points, downsampled

    def _set_viewer_widget(self, widget: QWidget, *, entry_type: str) -> None:
        self._clear_viewer_container()
        supports_reset = hasattr(widget, "reset_view")
        self._preview_widget = widget if supports_reset else None
        self._viewer_layout.addWidget(widget)
        self._current_entry_type = entry_type
        self._update_controls_enabled(supports_reset)

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
        if hasattr(self, "_current_entry_type"):
            self._current_entry_type = None

    def _show_error(self, message: str) -> None:
        self._clear_viewer_container()
        self._viewer_layout.addWidget(self._build_error_label(message))
        self._update_info_label(None, entry_type="error")
        self._update_controls_enabled(False)
        self._current_filename = None

    def _update_info_label(
        self,
        file_path: Optional[str],
        *,
        entry_type: str = "model",
        truncated: bool = False,
        size_bytes: Optional[int] = None,
    ) -> None:
        if hasattr(self, "_info_label") and self._info_label is not None:
            self._info_label.setText(
                self._format_info_text(
                    file_path,
                    entry_type=entry_type,
                    truncated=truncated,
                    size_bytes=size_bytes,
                )
            )

    def _format_info_text(
        self,
        file_path: Optional[str],
        *,
        entry_type: str,
        truncated: bool,
        size_bytes: Optional[int],
    ) -> str:
        parts: list[str] = []
        folder = self._model_data.get("folder") or ""

        if entry_type == "gcode":
            if file_path:
                parts.append(f"G-code: {os.path.basename(file_path)}")
            else:
                parts.append("G-code: (not available)")
        else:
            if file_path:
                parts.append(f"Source: {os.path.basename(file_path)}")
            else:
                parts.append("Source: (not available)")

        if folder:
            parts.append(f"Folder: {os.path.basename(folder)}")

        if entry_type == "model":
            print_time = self._model_data.get("print_time") or ""
            if print_time:
                parts.append(f"Print time: {print_time}")

        if size_bytes is not None:
            if size_bytes >= 1024 * 1024:
                size_text = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_text = f"{size_bytes / 1024:.1f} KB"
            parts.append(f"Size: {size_text}")

        if entry_type == "gcode" and truncated:
            parts.append("Preview truncated")

        if not parts:
            return ""
        return " | ".join(parts)

    def _update_controls_enabled(self, enabled: bool) -> None:
        if hasattr(self, "_reset_button") and self._reset_button is not None:
            self._reset_button.setEnabled(enabled)
        if hasattr(self, "_gcode_button") and self._gcode_button is not None:
            self._gcode_button.setEnabled(bool(getattr(self, "_gcode_files", [])))

    def _on_reset_view(self) -> None:
        if self._preview_widget is not None:
            self._preview_widget.reset_view()

    def _on_preview_gcode(self) -> None:
        if not getattr(self, "_gcode_files", []):
            return
        target_index = None
        if hasattr(self, "_file_entries"):
            for idx, entry in enumerate(self._file_entries):
                if entry.get("type") == "gcode":
                    target_index = idx
                    break
        if target_index is not None and self._file_selector is not None:
            if self._file_selector.currentIndex() != target_index:
                self._file_selector.blockSignals(True)
                self._file_selector.setCurrentIndex(target_index)
                self._file_selector.blockSignals(False)
            self._load_entry(self._file_entries[target_index])
            return
        self._display_gcode(self._gcode_files[0])