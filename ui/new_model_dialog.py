import json
import os
import re
import shutil
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from core.stl_preview import render_stl_preview
from ui.generated.new_model_dialog_ui import Ui_NewModelDialog


class NewModelDialog(QDialog):
    def __init__(self, app_dir: str, config: dict, dark_theme: bool = False, parent=None):
        super().__init__(parent)
        self.app_dir = app_dir
        self.config = config or {}
        self.dark_theme = dark_theme
        self.result_data: Optional[dict] = None
        self._preview_pixmap: Optional[QPixmap] = None
        self._preview_source_path: Optional[str] = None
        self._preview_generated = False

        self._setup_ui()
        self._wire_controls()
        self._apply_defaults()

    def _setup_ui(self) -> None:
        self.ui = Ui_NewModelDialog()
        self.ui.setupUi(self)
        self.setModal(True)

        self.name_edit: QLineEdit = self.ui.lineEditName
        self.stl_list: QListWidget = self.ui.listWidgetStlFiles
        self.preview_label: QLabel = self.ui.previewLabel
        self.choose_preview_btn: QPushButton = self.ui.btnChoosePreview
        self.add_stl_btn: QPushButton = self.ui.btnAddStl
        self.remove_stl_btn: QPushButton = self.ui.btnRemoveStl
        self.add_gcode_btn: QPushButton = self.ui.btnAddGcode
        self.remove_gcode_btn: QPushButton = self.ui.btnRemoveGcode
        self.location_combo: QComboBox = self.ui.comboLocation
        self.destination_edit: QLineEdit = self.ui.lineEditDestination
        self.browse_destination_btn: QPushButton = self.ui.btnBrowseDestination
        self.gcode_table: QTableWidget = self.ui.tableGcodes
        self.button_box: QDialogButtonBox = self.ui.buttonBox

        if self.location_combo is not None:
            self.location_combo.hide()
            self.location_combo = None
        location_label = getattr(self.ui, "labelLocation", None)
        if location_label is not None:
            location_label.hide()

        if self.minimumWidth() <= 0 or self.minimumHeight() <= 0:
            self.setMinimumSize(560, 520)
        if self.width() <= 0 or self.height() <= 0:
            self.resize(640, 600)

    def _wire_controls(self) -> None:
        if self.stl_list is not None:
            self.stl_list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.stl_list.currentItemChanged.connect(self._on_model_selection_changed)

        if self.remove_stl_btn is not None:
            self.remove_stl_btn.setEnabled(False)

        if self.gcode_table is not None:
            self.gcode_table.setColumnCount(4)
            self.gcode_table.setHorizontalHeaderLabels(["File", "Material", "Colour", "Print Time"])
            self.gcode_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.gcode_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.gcode_table.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )
            header = self.gcode_table.horizontalHeader()
            if header is not None:
                header.setStretchLastSection(True)

        if self.add_stl_btn is not None:
            self.add_stl_btn.clicked.connect(self._on_add_model_files)
        if self.remove_stl_btn is not None:
            self.remove_stl_btn.clicked.connect(self._on_remove_model_file)
        if self.choose_preview_btn is not None:
            self.choose_preview_btn.clicked.connect(self._on_choose_preview)
        if self.add_gcode_btn is not None:
            self.add_gcode_btn.clicked.connect(self._on_add_gcode)
        if self.remove_gcode_btn is not None:
            self.remove_gcode_btn.clicked.connect(self._on_remove_gcode)
        if self.browse_destination_btn is not None:
            self.browse_destination_btn.clicked.connect(self._on_browse_destination)

        if self.button_box is not None:
            self.button_box.accepted.connect(self._on_accept)
            self.button_box.rejected.connect(self.reject)

    def _apply_defaults(self) -> None:
        if self.destination_edit is not None:
            self.destination_edit.setText(self._resolve_default_destination())

        if self.preview_label is not None:
            self.preview_label.setText("No Preview")
            self.preview_label.setAlignment(Qt.AlignCenter)

    def _resolve_default_destination(self) -> str:
        path = self.config.get("storage_path")
        if not path:
            path = os.path.join(self.app_dir, "testfiles")
        return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))

    def _on_browse_destination(self) -> None:
        base = self.destination_edit.text() if self.destination_edit else self._resolve_default_destination()
        directory = QFileDialog.getExistingDirectory(self, "Select Destination Folder", base)
        if directory and self.destination_edit is not None:
            self.destination_edit.setText(directory)

    def _on_add_model_files(self) -> None:
        start_dir = self._resolve_default_destination()
        existing = self._collect_model_files()
        if existing:
            start_dir = os.path.dirname(existing[-1]) or start_dir
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Model Files",
            start_dir,
            "3D Models (*.stl *.STL *.3mf *.3MF);;All Files (*)",
        )
        if not paths:
            return
        self._add_model_paths(paths)

    def _add_model_paths(self, paths: List[str]) -> None:
        if not self.stl_list:
            return
        existing_names = {
            os.path.basename(self.stl_list.item(index).data(Qt.UserRole)).lower()
            for index in range(self.stl_list.count())
            if self.stl_list.item(index) and self.stl_list.item(index).data(Qt.UserRole)
        }
        added_any = False
        for path in paths:
            if not os.path.isfile(path):
                continue
            base_name = os.path.basename(path)
            key_name = base_name.lower()
            if key_name in existing_names:
                QMessageBox.warning(
                    self,
                    "Duplicate File",
                    f"A model file named '{base_name}' is already in this model package. Remove it first if you need to replace it.",
                )
                continue
            item = QListWidgetItem(base_name)
            item.setData(Qt.UserRole, path)
            self.stl_list.addItem(item)
            added_any = True
            existing_names.add(key_name)
        if not added_any:
            return

        if self.name_edit and not self.name_edit.text().strip():
            self._suggest_name_from_model()

        if self.stl_list.count() == 1 and self.stl_list.item(0):
            first_path = self.stl_list.item(0).data(Qt.UserRole)
            if first_path:
                self._generate_preview_from_stl(first_path)

        if self.stl_list.currentRow() < 0 and self.stl_list.count() > 0:
            self.stl_list.setCurrentRow(0)

        self._update_model_controls()

    def _suggest_name_from_model(self) -> None:
        if not self.stl_list or self.stl_list.count() == 0:
            return
        item = self.stl_list.item(0)
        if not item:
            return
        source = item.data(Qt.UserRole)
        if not source:
            return
        suggested = os.path.splitext(os.path.basename(source))[0]
        self.name_edit.setText(suggested)

    def _on_remove_model_file(self) -> None:
        if not self.stl_list:
            return
        row = self.stl_list.currentRow()
        if row < 0:
            return
        self.stl_list.takeItem(row)
        if self.stl_list.count():
            new_row = min(row, self.stl_list.count() - 1)
            self.stl_list.setCurrentRow(new_row)
        self._update_model_controls()

    def _on_model_selection_changed(self, current: Optional[QListWidgetItem], _: Optional[QListWidgetItem]) -> None:
        self._update_model_controls()
        if not current:
            return
        path = current.data(Qt.UserRole)
        if not path:
            return
        if self._preview_source_path:
            return
        self._generate_preview_from_stl(path)

    def _update_model_controls(self) -> None:
        if self.remove_stl_btn is not None:
            has_selection = bool(self.stl_list and self.stl_list.currentRow() >= 0)
            self.remove_stl_btn.setEnabled(has_selection)

    def _generate_preview_from_stl(self, file_path: str) -> None:
        try:
            pixmap = render_stl_preview(file_path, QSize(640, 640), dark_theme=self.dark_theme)
        except Exception:
            pixmap = None
        if pixmap and not pixmap.isNull():
            self._preview_pixmap = pixmap
            self._preview_source_path = None
            self._preview_generated = True
            self._update_preview_label(pixmap)
        else:
            self._preview_generated = False

    def _on_choose_preview(self) -> None:
        start_dir = os.path.dirname(self._preview_source_path) if self._preview_source_path else self._resolve_default_destination()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Preview Image",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Invalid Image", "Could not load the selected image file.")
            return
        self._preview_pixmap = pixmap
        self._preview_source_path = file_path
        self._preview_generated = False
        self._update_preview_label(pixmap)

    def _update_preview_label(self, pixmap: QPixmap) -> None:
        if not self.preview_label or pixmap.isNull():
            return
        target_size = self.preview_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = QSize(180, 140)
        scaled = pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def _on_add_gcode(self) -> None:
        start_dir = self._resolve_default_destination()
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select G-code Files",
            start_dir,
            "G-code Files (*.gcode *.gco *.g);;All Files (*)",
        )
        if not paths:
            return
        for path in paths:
            self._append_gcode_row(path)

    def _append_gcode_row(self, path: str, material: str = "", colour: str = "", print_time: str = "") -> None:
        if not self.gcode_table:
            return
        parsed = self._parse_gcode_filename(path)
        if parsed.get("name") and self.name_edit and not self.name_edit.text().strip():
            self.name_edit.setText(parsed["name"])
        if not material and parsed.get("material"):
            material = parsed["material"]
        if not colour and parsed.get("colour"):
            colour = parsed["colour"]
        if not print_time and parsed.get("print_time"):
            print_time = parsed["print_time"]
        row = self.gcode_table.rowCount()
        self.gcode_table.insertRow(row)
        file_item = QTableWidgetItem(os.path.basename(path))
        file_item.setData(Qt.UserRole, path)
        file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
        material_item = QTableWidgetItem(material)
        colour_item = QTableWidgetItem(colour)
        print_item = QTableWidgetItem(print_time)
        self.gcode_table.setItem(row, 0, file_item)
        self.gcode_table.setItem(row, 1, material_item)
        self.gcode_table.setItem(row, 2, colour_item)
        self.gcode_table.setItem(row, 3, print_item)

    def _on_remove_gcode(self) -> None:
        if not self.gcode_table:
            return
        selected = self.gcode_table.currentRow()
        if selected >= 0:
            self.gcode_table.removeRow(selected)

    def _collect_gcode_entries(self) -> List[dict]:
        entries: List[dict] = []
        if not self.gcode_table:
            return entries
        for row in range(self.gcode_table.rowCount()):
            file_item = self.gcode_table.item(row, 0)
            if file_item is None:
                continue
            source_path = file_item.data(Qt.UserRole) or file_item.text()
            material_item = self.gcode_table.item(row, 1)
            colour_item = self.gcode_table.item(row, 2)
            time_item = self.gcode_table.item(row, 3)
            entries.append(
                {
                    "source": source_path,
                    "file": file_item.text(),
                    "material": material_item.text() if material_item else "",
                    "colour": colour_item.text() if colour_item else "",
                    "print_time": time_item.text() if time_item else "",
                }
            )
        return entries

    def _on_accept(self) -> None:
        try:
            data = self._gather_inputs()
        except ValueError as exc:
            QMessageBox.warning(self, "Missing Data", str(exc))
            return

        try:
            package = self._create_model_package(data)
        except Exception as exc:
            QMessageBox.critical(self, "Unable to Save", str(exc))
            return

        self.result_data = package
        self.accept()

    def _collect_model_files(self) -> List[str]:
        if not self.stl_list:
            return []
        paths: List[str] = []
        for index in range(self.stl_list.count()):
            item = self.stl_list.item(index)
            if not item:
                continue
            path = item.data(Qt.UserRole)
            if path:
                paths.append(path)
        return paths

    def _gather_inputs(self) -> dict:
        name = self.name_edit.text().strip() if self.name_edit else ""
        if not name:
            raise ValueError("Model name is required.")
        model_paths = self._collect_model_files()
        if not model_paths:
            raise ValueError("Select at least one STL or 3MF file.")
        missing = [path for path in model_paths if not os.path.isfile(path)]
        if missing:
            raise ValueError("Some selected model files no longer exist. Remove them and try again.")
        destination_root = self.destination_edit.text().strip() if self.destination_edit else ""
        if not destination_root:
            destination_root = self._resolve_default_destination()
        gcode_entries = self._collect_gcode_entries()

        return {
            "name": name,
            "model_paths": model_paths,
            "gcodes": gcode_entries,
            "destination_root": destination_root,
        }

    def _sanitize_folder_name(self, name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
        return cleaned or "model"

    def _create_model_package(self, data: dict) -> dict:
        dest_root = os.path.abspath(os.path.expanduser(os.path.expandvars(data["destination_root"])))
        if not os.path.isdir(dest_root):
            raise FileNotFoundError("Destination folder does not exist.")

        folder_name = self._sanitize_folder_name(data["name"])
        model_dir = os.path.join(dest_root, folder_name)
        if os.path.exists(model_dir):
            raise FileExistsError("A model folder with this name already exists.")

        os.makedirs(model_dir, exist_ok=False)
        created_paths = []
        try:
            model_files = []
            for index, source_path in enumerate(data["model_paths"]):
                base_name = os.path.basename(source_path)
                dest_name = base_name
                dest_path = os.path.join(model_dir, dest_name)
                if os.path.exists(dest_path):
                    raise FileExistsError(
                        f"A file named '{base_name}' already exists in the new model folder."
                    )
                shutil.copy2(source_path, dest_path)
                created_paths.append(dest_path)
                model_files.append(dest_name)

            gcodes_meta = []
            for entry in data["gcodes"]:
                source = entry.get("source")
                if not source or not os.path.isfile(source):
                    continue
                dest_file = os.path.join(model_dir, os.path.basename(source))
                shutil.copy2(source, dest_file)
                created_paths.append(dest_file)
                gcodes_meta.append(
                    {
                        "file": os.path.basename(dest_file),
                        "material": entry.get("material") or "",
                        "colour": entry.get("colour") or "",
                        "print_time": entry.get("print_time") or "",
                    }
                )

            preview_name = ""
            if self._preview_pixmap and not self._preview_pixmap.isNull():
                if self._preview_generated or not self._preview_source_path:
                    preview_name = "preview.png"
                    preview_dest = os.path.join(model_dir, preview_name)
                    if not self._preview_pixmap.save(preview_dest, "PNG"):
                        raise IOError("Failed to write generated preview image.")
                    created_paths.append(preview_dest)
                else:
                    source = self._preview_source_path
                    preview_name = os.path.basename(source)
                    preview_dest = os.path.join(model_dir, preview_name)
                    shutil.copy2(source, preview_dest)
                    created_paths.append(preview_dest)

            timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            primary_model = model_files[0] if model_files else ""
            meta = {
                "name": data["name"],
                "stl_file": primary_model,
                "model_file": primary_model,
                "model_files": model_files,
                "gcodes": gcodes_meta,
                "preview_image": preview_name,
                "last_modified": timestamp,
                "time_created": timestamp,
            }

            meta_path = os.path.join(model_dir, "model.json")
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2)
            created_paths.append(meta_path)
        except Exception:
            shutil.rmtree(model_dir, ignore_errors=True)
            raise

        return {
            "folder_path": model_dir,
            "storage_path": dest_root,
        }

    def _parse_gcode_filename(self, path: str) -> dict:
        base = os.path.splitext(os.path.basename(path))[0]
        tokens = [tok for tok in base.split("_") if tok]
        if not tokens:
            return {"name": "", "material": "", "colour": "", "print_time": ""}

        time_index = None
        for idx, token in enumerate(tokens):
            token_l = token.lower()
            if re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", token_l) and any(ch.isdigit() for ch in token_l):
                time_index = idx
                break
        if time_index is None:
            return {"name": "", "material": "", "colour": "", "print_time": ""}

        name_tokens = tokens[:time_index]
        time_token = tokens[time_index]
        trailing = tokens[time_index + 1 :] if time_index + 1 < len(tokens) else []

        def _clean(parts: list[str]) -> str:
            text = " ".join(part.replace("-", " ") for part in parts)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        name = _clean(name_tokens)
        hours = minutes = ""
        match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", time_token.lower())
        if match:
            hours = match.group(1) or ""
            minutes = match.group(2) or ""
        print_time = ""
        if hours:
            print_time += f"{hours}h"
        if minutes:
            print_time += f"{minutes}m"
        if not print_time:
            print_time = time_token

        material_tokens: list[str] = []
        colour = ""
        if trailing:
            if len(trailing) > 1:
                colour = _clean([trailing[-1]])
                material_tokens = trailing[:-1]
            else:
                material_tokens = trailing
        material = _clean(material_tokens)

        return {
            "name": name,
            "material": material,
            "colour": colour,
            "print_time": print_time,
        }
