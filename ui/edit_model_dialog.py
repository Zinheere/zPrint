import json
import os
from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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

    def _populate_fields(self) -> None:
        name = self.metadata.get("name") or self.model_data.get("name") or ""
        self.name_edit.setText(str(name))

        display_time = self.metadata.get("print_time") or self.model_data.get("print_time") or ""
        self.print_time_edit.setText(str(display_time))

        gcodes = self.metadata.get("gcodes") or []
        self.gcode_table.setRowCount(len(gcodes))
        for row, entry in enumerate(gcodes):
            file_name = entry.get("file", "")
            material = entry.get("material", "")
            colour = entry.get("colour") or entry.get("color") or ""
            print_time = entry.get("print_time", "")

            file_item = QTableWidgetItem(file_name)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            file_item.setData(Qt.UserRole, file_name)
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
            file_name = file_item.data(Qt.UserRole) or file_item.text()
            material_item = self.gcode_table.item(row, 1)
            colour_item = self.gcode_table.item(row, 2)
            time_item = self.gcode_table.item(row, 3)
            rows.append(
                {
                    "file": file_name,
                    "material": material_item.text().strip() if material_item else "",
                    "colour": colour_item.text().strip() if colour_item else "",
                    "print_time": time_item.text().strip() if time_item else "",
                }
            )
        return rows

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Data", "Model name cannot be empty.")
            return

        metadata = deepcopy(self.metadata)
        metadata["name"] = name
        metadata["print_time"] = self.print_time_edit.text().strip()
        metadata["gcodes"] = self._collect_gcode_rows()
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