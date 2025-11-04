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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.stl_preview import render_stl_preview


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
        self.generated_preview_pixmap: QPixmap | None = None
        self.pending_model_copies: list[dict] = []
        self.model_files_to_delete: list[str] = []

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

        model_layout = QVBoxLayout()
        self.model_list = QListWidget(self)
        self.model_list.setSelectionMode(QAbstractItemView.SingleSelection)
        model_layout.addWidget(self.model_list)

        model_buttons = QHBoxLayout()
        self.add_model_button = QPushButton("Add Model File...", self)
        self.remove_model_button = QPushButton("Remove Selected", self)
        self.remove_model_button.setEnabled(False)
        model_buttons.addWidget(self.add_model_button)
        model_buttons.addWidget(self.remove_model_button)
        model_buttons.addStretch(1)
        model_layout.addLayout(model_buttons)

        form.addRow("Model Files", model_layout)

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

        buttons_row = QHBoxLayout()
        self.choose_preview_button = QPushButton("Change Preview…", self)
        self.regenerate_preview_button = QPushButton("Regenerate Preview", self)
        buttons_row.addWidget(self.choose_preview_button)
        buttons_row.addWidget(self.regenerate_preview_button)
        buttons_row.addStretch(1)
        preview_box.addLayout(buttons_row)

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
        self.delete_button.setStyleSheet(
            "QPushButton { background-color: #FF3B30; color: #ffffff; font-weight: 600; padding: 6px 12px; border-radius: 6px; } "
            "QPushButton:pressed { background-color: #FF3B30; }"
        )
        controls.addWidget(self.delete_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.model_list.currentItemChanged.connect(self._on_model_selection_changed)
        self.add_model_button.clicked.connect(self._on_add_model_file)
        self.remove_model_button.clicked.connect(self._on_remove_model_file)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.choose_preview_button.clicked.connect(self._on_choose_preview)
        self.regenerate_preview_button.clicked.connect(self._on_regenerate_preview)
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
        self.generated_preview_pixmap = None

        pixmap = self._load_preview_pixmap()
        if pixmap:
            self._update_preview_label(pixmap)
        else:
            self._update_preview_label(None)
            if preview_name:
                self.preview_label.setText("Preview image not found")

        self._populate_model_files()

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

    def _populate_model_files(self) -> None:
        if not hasattr(self, "model_list") or self.model_list is None:
            return
        self.model_list.clear()
        model_files = self._resolve_model_files()
        for filename in model_files:
            item = QListWidgetItem(filename)
            payload = {
                "file": filename,
                "source_path": os.path.join(self.folder_path, filename) if self.folder_path else "",
                "is_new": False,
            }
            item.setData(Qt.UserRole, payload)
            self.model_list.addItem(item)
        if self.model_list.count():
            self.model_list.setCurrentRow(0)
        self._update_model_buttons()

    def _resolve_model_files(self) -> list[str]:
        raw = self.metadata.get("model_files")
        if isinstance(raw, list) and raw:
            return [str(item) for item in raw if item]
        data_files = self.model_data.get("model_files")
        if isinstance(data_files, list) and data_files:
            return [str(item) for item in data_files if item]
        fallback = (
            self.metadata.get("model_file")
            or self.metadata.get("stl_file")
            or self.model_data.get("model_file")
            or self.model_data.get("stl_file")
        )
        return [str(fallback)] if fallback else []

    def _on_model_selection_changed(self, current, _previous) -> None:
        self._update_model_buttons()

    def _update_model_buttons(self) -> None:
        if not hasattr(self, "remove_model_button") or self.remove_model_button is None:
            return
        if not hasattr(self, "model_list") or self.model_list is None:
            self.remove_model_button.setEnabled(False)
            return
        count = self.model_list.count()
        has_selection = self.model_list.currentRow() >= 0
        self.remove_model_button.setEnabled(bool(has_selection and count > 1))

    def _on_add_model_file(self) -> None:
        start_dir = self.folder_path if self.folder_path else os.path.expanduser("~")
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Model Files",
            start_dir,
            "3D Models (*.stl *.STL *.3mf *.3MF);;All Files (*)",
        )
        if not paths:
            return
        existing_names = {
            self.model_list.item(index).text().lower()
            for index in range(self.model_list.count())
            if self.model_list.item(index)
        }
        added = False
        for path in paths:
            if not os.path.isfile(path):
                continue
            base_name = os.path.basename(path)
            if base_name.lower() in existing_names:
                QMessageBox.warning(
                    self,
                    "Duplicate File",
                    f"A model file named '{base_name}' is already associated with this model.",
                )
                continue
            item = QListWidgetItem(base_name)
            payload = {
                "file": base_name,
                "source_path": path,
                "is_new": True,
            }
            item.setData(Qt.UserRole, payload)
            self.model_list.addItem(item)
            existing_names.add(base_name.lower())
            added = True
        if added:
            self.model_list.setCurrentRow(self.model_list.count() - 1)
            self._update_model_buttons()

    def _on_remove_model_file(self) -> None:
        if not self.model_list:
            return
        row = self.model_list.currentRow()
        if row < 0:
            return
        if self.model_list.count() <= 1:
            QMessageBox.warning(self, "Model Files", "At least one model file must remain in the package.")
            return
        item = self.model_list.item(row)
        payload = item.data(Qt.UserRole) if item else {}
        if isinstance(payload, dict) and not payload.get("is_new"):
            file_name = payload.get("file") or item.text()
            prompt = QMessageBox(self)
            prompt.setWindowTitle("Remove Model File")
            prompt.setIcon(QMessageBox.Question)
            prompt.setText("Remove this model file? Optionally delete the file from disk as well.")
            delete_btn = prompt.addButton("Remove && Delete", QMessageBox.AcceptRole)
            prompt.addButton("Remove Only", QMessageBox.DestructiveRole)
            cancel_btn = prompt.addButton(QMessageBox.Cancel)
            prompt.setDefaultButton(delete_btn)
            prompt.exec()
            clicked = prompt.clickedButton()
            if clicked is cancel_btn:
                return
            if clicked is delete_btn and file_name and file_name not in self.model_files_to_delete:
                self.model_files_to_delete.append(file_name)
        self.model_list.takeItem(row)
        if self.model_list.count():
            self.model_list.setCurrentRow(min(row, self.model_list.count() - 1))
        self._update_model_buttons()

    def _collect_model_rows(self) -> list[dict]:
        rows: list[dict] = []
        if not self.model_list:
            return rows
        for index in range(self.model_list.count()):
            item = self.model_list.item(index)
            if not item:
                continue
            payload = item.data(Qt.UserRole) or {}
            if isinstance(payload, str):
                payload = {"file": payload, "source_path": "", "is_new": False}
            file_name = payload.get("file") or item.text()
            rows.append(
                {
                    "file": file_name,
                    "source_path": payload.get("source_path", ""),
                    "is_new": bool(payload.get("is_new")),
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
        self.generated_preview_pixmap = None
        self._update_preview_label(pixmap)

    def _on_regenerate_preview(self) -> None:
        model_path = self._current_model_path_for_preview() or self._resolve_model_path()
        if not model_path:
            QMessageBox.warning(self, "Regenerate Preview", "Unable to locate the model file for this entry.")
            return
        try:
            pixmap = render_stl_preview(model_path, QSize(640, 480), dark_theme=self._is_dark_theme())
        except Exception as exc:
            QMessageBox.warning(self, "Regenerate Preview", f"Failed to render preview:\n{exc}")
            return
        if not pixmap or pixmap.isNull():
            QMessageBox.warning(self, "Regenerate Preview", "Preview rendering failed for this model.")
            return
        target_name = self.original_preview_name or "preview.png"
        self.preview_changed = True
        self.new_preview_source_path = None
        self.new_preview_filename = target_name
        self.current_preview_name = target_name
        self.generated_preview_pixmap = pixmap
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
        model_rows = self._collect_model_rows()
        if not model_rows:
            QMessageBox.warning(self, "Missing Data", "Select at least one model file.")
            return

        model_used_names: set[str] = set()
        model_entries: list[dict] = []
        model_copies: list[dict] = []
        for index, entry in enumerate(model_rows):
            base_name = entry.get("file") or os.path.basename(entry.get("source_path") or "")
            if not base_name:
                QMessageBox.warning(self, "Invalid Entry", "A model entry has no filename.")
                return
            unique_name = self._ensure_unique_filename(base_name, model_used_names)
            if unique_name != entry.get("file"):
                item = self.model_list.item(index)
                if item:
                    item.setText(unique_name)
                    payload = item.data(Qt.UserRole) or {}
                    if isinstance(payload, dict):
                        payload["file"] = unique_name
                        item.setData(Qt.UserRole, payload)
            model_entries.append({"file": unique_name})
            if entry.get("is_new") and entry.get("source_path"):
                model_copies.append({"source": entry["source_path"], "dest": unique_name})

        metadata["model_files"] = [entry["file"] for entry in model_entries]
        if metadata["model_files"]:
            metadata["model_file"] = metadata["model_files"][0]
            metadata["stl_file"] = metadata["model_files"][0]

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
        self.pending_model_copies = model_copies
        current_model_set = {name.lower() for name in metadata.get("model_files", [])}
        self.model_files_to_delete = [name for name in self.model_files_to_delete if name.lower() not in current_model_set]
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

    def _resolve_model_path(self) -> str | None:
        model_files = self._resolve_model_files()
        filename = model_files[0] if model_files else None
        if not filename or not self.folder_path:
            return None
        candidate = os.path.join(self.folder_path, filename)
        if os.path.exists(candidate):
            return candidate
        return None

    def _current_model_path_for_preview(self) -> str | None:
        if not self.model_list or not self.model_list.currentItem():
            return None
        payload = self.model_list.currentItem().data(Qt.UserRole) or {}
        if isinstance(payload, dict) and payload.get("is_new") and payload.get("source_path"):
            return payload["source_path"]
        filename = payload.get("file") or self.model_list.currentItem().text()
        if not filename or not self.folder_path:
            return None
        candidate = os.path.join(self.folder_path, filename)
        if os.path.exists(candidate):
            return candidate
        return None

    def _is_dark_theme(self) -> bool:
        parent = self.parent()
        if parent is not None and hasattr(parent, "dark_theme"):
            return bool(getattr(parent, "dark_theme"))
        return False