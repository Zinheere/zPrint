import json
import os
import re
from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class EditModelDialog(QDialog):
    """Dialog for editing model metadata and optionally deleting the model."""

    def __init__(self, model_data: dict, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.model_data = model_data or {}
        self.folder_path: str = self.model_data.get("folder", "")
        self.meta_path = os.path.join(self.folder_path, "model.json") if self.folder_path else None
        self.metadata = {}
        self.updated_metadata: dict | None = None
        self.delete_requested = False
        self.original_preview_name: str = ""
        self.current_preview_name: str = ""
        self.preview_changed = False
        self.new_preview_source_path: str | None = None
        self.new_preview_filename: str = ""
        self._preview_pixmap: QPixmap | None = None
        self.pending_gcode_copies: list[dict] = []
        self.gcode_files_to_delete: list[str] = []

        self._load_metadata()
        self._build_ui()
        self._populate_fields()

    def _load_metadata(self) -> None:
        if self.meta_path and os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as fh:
                    self.metadata = json.load(fh) or {}
            except Exception:
                self.metadata = deepcopy(self.model_data.get("metadata", {}))
        else:
            self.metadata = deepcopy(self.model_data.get("metadata", {}))

    def _build_ui(self) -> None:
        self.setWindowTitle("Edit Model")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        form.addRow("Name", self.name_edit)

        self.print_time_edit = QLineEdit(self)
        form.addRow("Print Time", self.print_time_edit)

        folder_label = QLabel(self.folder_path or "Unknown", self)
        folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Folder", folder_label)

        layout.addLayout(form)

        preview_box = QVBoxLayout()
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(220, 160)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet("border: 1px solid rgba(160, 160, 160, 60);")
        self.preview_label.setWordWrap(True)
        preview_box.addWidget(self.preview_label)

        self.choose_preview_button = QPushButton("Change Preview…", self)
        preview_box.addWidget(self.choose_preview_button, alignment=Qt.AlignLeft)

        layout.addLayout(preview_box)

        self.gcode_table = QTableWidget(self)
        self.gcode_table.setColumnCount(4)
        self.gcode_table.setHorizontalHeaderLabels(["File", "Material", "Colour", "Print Time"])
        header = self.gcode_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.gcode_table.verticalHeader().setVisible(False)
        self.gcode_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        layout.addWidget(self.gcode_table)

        gcode_controls = QHBoxLayout()
        self.add_gcode_button = QPushButton("Add G-code…", self)
        self.remove_gcode_button = QPushButton("Remove Selected", self)
        gcode_controls.addWidget(self.add_gcode_button)
        gcode_controls.addWidget(self.remove_gcode_button)
        gcode_controls.addStretch(1)
        layout.addLayout(gcode_controls)

        hint = QLabel(
            "Update metadata for each G-code entry. File names remain unchanged.",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        controls = QHBoxLayout()
        self.delete_button = QPushButton("Delete Model…", self)
        controls.addWidget(self.delete_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.choose_preview_button.clicked.connect(self._on_choose_preview)
        self.add_gcode_button.clicked.connect(self._on_add_gcode)
        self.remove_gcode_button.clicked.connect(self._on_remove_gcode)

    def _populate_fields(self) -> None:
        name = self.metadata.get("name") or self.model_data.get("name") or ""
        self.name_edit.setText(str(name))

        display_time = self.metadata.get("print_time") or self.model_data.get("print_time") or ""
        self.print_time_edit.setText(str(display_time))

        preview_name = self.metadata.get("preview_image") or ""
        self.original_preview_name = preview_name
        self.current_preview_name = preview_name
        self.preview_changed = False
        self.new_preview_source_path = None
        self.new_preview_filename = preview_name

        pixmap = self._load_preview_pixmap()
        if pixmap:
            self._update_preview_label(pixmap)
        else:
            self._update_preview_label(None)
            if preview_name:
                self.preview_label.setText("Preview image not found")

        gcodes = self.metadata.get("gcodes") or []
        self.gcode_table.setRowCount(len(gcodes))
        for row, entry in enumerate(gcodes):
            file_name = entry.get("file", "")
            material = entry.get("material", "")
            colour = entry.get("colour") or entry.get("color") or ""
            print_time = entry.get("print_time", "")

            file_item = QTableWidgetItem(file_name)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            file_item.setToolTip(file_name)
            file_item.setData(
                Qt.UserRole,
                {
                    "file": file_name,
                    "source_path": os.path.join(self.folder_path, file_name) if self.folder_path else "",
                    "is_new": False,
                },
            )
            material_item = QTableWidgetItem(material)
            colour_item = QTableWidgetItem(colour)
            time_item = QTableWidgetItem(print_time)

            self.gcode_table.setItem(row, 0, file_item)
            self.gcode_table.setItem(row, 1, material_item)
            self.gcode_table.setItem(row, 2, colour_item)
            self.gcode_table.setItem(row, 3, time_item)

    def _collect_gcode_rows(self) -> list[dict]:
        rows: list[dict] = []
        if self.gcode_table.rowCount() == 0:
            return rows
        for row in range(self.gcode_table.rowCount()):
            file_item = self.gcode_table.item(row, 0)
            if file_item is None:
                continue
            payload = file_item.data(Qt.UserRole) or {}
            if isinstance(payload, str):
                payload = {"file": payload, "source_path": "", "is_new": False}
            file_name = payload.get("file") or file_item.text()
            material_item = self.gcode_table.item(row, 1)
            colour_item = self.gcode_table.item(row, 2)
            time_item = self.gcode_table.item(row, 3)
            rows.append(
                {
                    "file": file_name,
                    "material": material_item.text().strip() if material_item else "",
                    "colour": colour_item.text().strip() if colour_item else "",
                    "print_time": time_item.text().strip() if time_item else "",
                    "source_path": payload.get("source_path", "") if isinstance(payload, dict) else "",
                    "is_new": bool(payload.get("is_new") if isinstance(payload, dict) else False),
                }
            )
        return rows

    def _load_preview_pixmap(self) -> QPixmap | None:
        if not self.current_preview_name or not self.folder_path:
            return None
        candidate = os.path.join(self.folder_path, self.current_preview_name)
        if not os.path.exists(candidate):
            return None
        pixmap = QPixmap(candidate)
        if pixmap.isNull():
            return None
        return pixmap

    def _update_preview_label(self, pixmap: QPixmap | None) -> None:
        if not hasattr(self, "preview_label") or self.preview_label is None:
            return
        if not pixmap or pixmap.isNull():
            self._preview_pixmap = None
            self.preview_label.clear()
            self.preview_label.setText("No Preview")
            return
        self._preview_pixmap = pixmap
        self._apply_preview_scaling()

    def _apply_preview_scaling(self) -> None:
        if not self._preview_pixmap or self._preview_pixmap.isNull():
            return
        if not hasattr(self, "preview_label") or self.preview_label is None:
            return
        target = self.preview_label.size()
        if target.width() <= 0 or target.height() <= 0:
            target = QSize(220, 160)
        scaled = self._preview_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def _on_choose_preview(self) -> None:
        start_dir = self.folder_path if self.folder_path else os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Preview Image",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)",
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Invalid Image", "Could not load the selected image file.")
            return
        self.preview_changed = True
        self.new_preview_source_path = file_path
        self.new_preview_filename = os.path.basename(file_path)
        self.current_preview_name = self.new_preview_filename
        self._update_preview_label(pixmap)

    def _on_add_gcode(self) -> None:
        start_dir = self.folder_path if self.folder_path else os.path.expanduser("~")
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select G-code Files",
            start_dir,
            "G-code Files (*.gcode *.gco *.g);;All Files (*)",
        )
        if not paths:
            return
        for path in paths:
            if not os.path.isfile(path):
                continue
            basename = os.path.basename(path)
            material, colour, print_time = self._parse_gcode_filename(basename)
            row = self.gcode_table.rowCount()
            self.gcode_table.insertRow(row)

            file_item = QTableWidgetItem(basename)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            file_item.setToolTip(path)
            file_item.setData(
                Qt.UserRole,
                {
                    "file": basename,
                    "source_path": path,
                    "is_new": True,
                },
            )

            material_item = QTableWidgetItem(material)
            colour_item = QTableWidgetItem(colour)
            time_item = QTableWidgetItem(print_time)

            self.gcode_table.setItem(row, 0, file_item)
            self.gcode_table.setItem(row, 1, material_item)
            self.gcode_table.setItem(row, 2, colour_item)
            self.gcode_table.setItem(row, 3, time_item)

    def _on_remove_gcode(self) -> None:
        row = self.gcode_table.currentRow()
        if row < 0:
            return
        file_item = self.gcode_table.item(row, 0)
        payload = file_item.data(Qt.UserRole) if file_item else {}
        if isinstance(payload, dict) and not payload.get("is_new"):
            file_name = payload.get("file") or file_item.text()
            if file_name:
                prompt = QMessageBox(self)
                prompt.setWindowTitle("Remove G-code")
                prompt.setIcon(QMessageBox.Question)
                prompt.setText("Remove this G-code entry? Optionally delete the file from disk as well.")
                delete_btn = prompt.addButton("Remove && Delete", QMessageBox.AcceptRole)
                prompt.addButton("Remove Only", QMessageBox.DestructiveRole)
                cancel_btn = prompt.addButton(QMessageBox.Cancel)
                prompt.setDefaultButton(delete_btn)
                prompt.exec()
                clicked = prompt.clickedButton()
                if clicked is cancel_btn:
                    return
                if clicked is delete_btn and file_name not in self.gcode_files_to_delete:
                    self.gcode_files_to_delete.append(file_name)
        self.gcode_table.removeRow(row)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_preview_scaling()

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Data", "Model name cannot be empty.")
            return

        metadata = deepcopy(self.metadata)
        metadata["name"] = name
        metadata["print_time"] = self.print_time_edit.text().strip()
        collected = self._collect_gcode_rows()
        if any(not row.get("file") and not row.get("source_path") for row in collected):
            QMessageBox.warning(self, "Invalid Entry", "Each G-code row must reference a file.")
            return

        used_names: set[str] = set()
        gcodes: list[dict] = []
        pending_copies: list[dict] = []
        for entry in collected:
            base_name = entry.get("file") or os.path.basename(entry.get("source_path") or "")
            if not base_name:
                QMessageBox.warning(self, "Invalid Entry", "A G-code row has no filename.")
                return
            unique_name = self._ensure_unique_filename(base_name, used_names)
            gcodes.append(
                {
                    "file": unique_name,
                    "material": entry.get("material", ""),
                    "colour": entry.get("colour", ""),
                    "print_time": entry.get("print_time", ""),
                }
            )
            if entry.get("is_new") and entry.get("source_path"):
                pending_copies.append({
                    "source": entry["source_path"],
                    "dest": unique_name,
                })
        current_files = {entry["file"].lower() for entry in gcodes}
        self.gcode_files_to_delete = [name for name in self.gcode_files_to_delete if name.lower() not in current_files]
        metadata["gcodes"] = gcodes
        self.pending_gcode_copies = pending_copies
        if self.preview_changed and self.new_preview_source_path:
            preview_name = self.new_preview_filename or os.path.basename(self.new_preview_source_path)
            metadata["preview_image"] = preview_name
        else:
            metadata["preview_image"] = self.current_preview_name or ""
        self.current_preview_name = metadata.get("preview_image", "")
        metadata["last_modified"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        self.updated_metadata = metadata
        self.delete_requested = False
        super().accept()

    def _on_delete_clicked(self) -> None:
        if not self.folder_path:
            QMessageBox.critical(self, "Delete Model", "Unable to determine model folder.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Model",
            "This will remove the entire model folder from disk. This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.delete_requested = True
        self.updated_metadata = None
        super().accept()

    def _ensure_unique_filename(self, candidate: str, used_lower: set[str]) -> str:
        root, ext = os.path.splitext(candidate)
        attempt = candidate
        suffix = 1
        key = attempt.lower()
        while key in used_lower:
            attempt = f"{root}_{suffix}{ext}"
            suffix += 1
            key = attempt.lower()
        used_lower.add(key)
        return attempt

    def _parse_gcode_filename(self, filename: str) -> tuple[str, str, str]:
        base = os.path.splitext(filename)[0]
        tokens = [tok for tok in re.split(r"[_\-]+", base) if tok]
        material = ""
        colour = ""
        print_time = ""
        for token in tokens:
            upper = token.upper()
            if not material and upper in {"PLA", "ABS", "PETG", "TPU", "ASA", "PC"}:
                material = upper
                continue
            if not colour and upper in {"RED", "BLUE", "BLACK", "WHITE", "GREEN", "GREY", "GRAY", "YELLOW", "PURPLE", "ORANGE"}:
                colour = token.capitalize()
                continue
            if not print_time and re.fullmatch(r"\d+h\d*m|\d+h|\d+m", token.lower()):
                print_time = token.lower()
        return material, colour, print_time