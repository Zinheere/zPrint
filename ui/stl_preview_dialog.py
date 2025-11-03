"""Interactive STL viewer dialog used by the gallery."""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import trimesh
from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.stl_preview import render_stl_preview


class _InteractivePreview(QWidget):
    """Widget that re-renders a mesh preview while tracking orbit and zoom."""

    def __init__(
        self,
        mesh: trimesh.Trimesh,
        stl_path: str,
        *,
        dark_theme: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(560, 420)

        self._mesh = mesh
        self._stl_path = stl_path
        self._dark_theme = dark_theme
        self._angles = [26.0, 35.0]
        self._distance_scale = 1.0
        self._dragging = False
        self._last_pos = QPoint()
        self._current_pixmap = None
        self._quick_mode = False

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_now)

        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._exit_quick_mode)

        self._schedule_render()

    def _schedule_render(self) -> None:
        self._render_timer.start(0)

    def _render_now(self) -> None:
        size = self.size()
        width = max(200, size.width())
        height = max(200, size.height())
        max_dimension = max(width, height)
        scale_cap = 1.0
        if max_dimension > 720:
            scale_cap = 720.0 / float(max_dimension)
        if self._quick_mode:
            quality_scale = max(0.3, scale_cap * 0.5)
        else:
            quality_scale = max(0.45, scale_cap * 0.85)
        self._current_pixmap = render_stl_preview(
            self._stl_path,
            QSize(width, height),
            dark_theme=self._dark_theme,
            mesh=self._mesh,
            view_angles=(self._angles[0], self._angles[1]),
            distance_scale=self._distance_scale,
            quality_scale=quality_scale,
        )
        self.update()

    def _enter_quick_mode(self) -> None:
        if not self._quick_mode:
            self._quick_mode = True
        self._settle_timer.start(90)

    def _exit_quick_mode(self) -> None:
        if not self._quick_mode:
            return
        self._settle_timer.stop()
        self._quick_mode = False
        self._schedule_render()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if self._current_pixmap is None or self._current_pixmap.isNull():
            painter.drawText(self.rect(), Qt.AlignCenter, "Rendering preview…")
            return
        target = self.rect()
        pix = self._current_pixmap.scaled(
            target.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = target.x() + (target.width() - pix.width()) // 2
        y = target.y() + (target.height() - pix.height()) // 2
        painter.drawPixmap(x, y, pix)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._schedule_render()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_pos = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            pos = event.position().toPoint()
            delta = pos - self._last_pos
            self._last_pos = pos
            self._angles[0] = float(np.clip(self._angles[0] - delta.y() * 0.5, -89.0, 89.0))
            self._angles[1] = (self._angles[1] + delta.x() * 0.5) % 360.0
            self._enter_quick_mode()
            self._schedule_render()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._exit_quick_mode()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        super().leaveEvent(event)
        self._dragging = False
        self._exit_quick_mode()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        factor = 0.9 if delta > 0 else 1.1
        self._distance_scale = float(np.clip(self._distance_scale * factor, 0.4, 3.0))
        self._enter_quick_mode()
        self._schedule_render()
        event.accept()

    def reset_view(self) -> None:
        self._angles = [26.0, 35.0]
        self._distance_scale = 1.0
        self._quick_mode = False
        self._schedule_render()


class StlPreviewDialog(QDialog):
    """Interactive window that orbits an STL model using repeated renders."""

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

        self._preview_widget = _InteractivePreview(mesh, stl_path, dark_theme=self._dark_theme, parent=self)
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