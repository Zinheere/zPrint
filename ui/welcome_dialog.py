from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QWidget,
)
class WelcomeDialog(QDialog):
    """First-run onboarding dialog for selecting storage location and theme."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        initial_path: str,
        default_path: str,
        theme: str = "light",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to zPrint")
        self.setModal(True)
        self.result_data: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        intro = QLabel(
            "Before we start, choose where zPrint should store your models and which theme you prefer."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Storage location controls
        storage_label = QLabel("Models folder")
        storage_label.setProperty("sectionHeader", True)
        layout.addWidget(storage_label)

        storage_row = QHBoxLayout()
        storage_row.setSpacing(8)
        self.path_edit = QLineEdit(self)
        self.path_edit.setReadOnly(True)
        self.path_edit.setText(os.path.abspath(initial_path))
        storage_row.addWidget(self.path_edit)

        browse_btn = QPushButton("Browse…", self)
        browse_btn.clicked.connect(self._browse_for_path)
        storage_row.addWidget(browse_btn)
        layout.addLayout(storage_row)

        use_default_btn = QPushButton(f"Use Default ({default_path})", self)
        use_default_btn.clicked.connect(lambda: self._set_path(default_path))
        layout.addWidget(use_default_btn)

        # Theme selection controls
        theme_label = QLabel("Theme")
        theme_label.setProperty("sectionHeader", True)
        layout.addWidget(theme_label)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)
        self.theme_group = QButtonGroup(self)

        self.light_radio = QRadioButton("Light", self)
        self.dark_radio = QRadioButton("Dark", self)
        self.theme_group.addButton(self.light_radio)
        self.theme_group.addButton(self.dark_radio)

        theme_row.addWidget(self.light_radio)
        theme_row.addWidget(self.dark_radio)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)

        theme = (theme or "light").lower()
        if theme == "dark":
            self.dark_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)

        # Action buttons
        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        continue_btn = QPushButton("Continue", self)
        continue_btn.setDefault(True)
        continue_btn.clicked.connect(self._accept)
        buttons_row.addWidget(cancel_btn)
        buttons_row.addWidget(continue_btn)
        layout.addLayout(buttons_row)

        self._default_path = os.path.abspath(default_path)

    def _set_path(self, new_path: str) -> None:
        if not new_path:
            return
        self.path_edit.setText(os.path.abspath(new_path))

    def _browse_for_path(self) -> None:
        start_dir = self.path_edit.text().strip() or self._default_path
        directory = QFileDialog.getExistingDirectory(self, "Choose Models Folder", start_dir)
        if directory:
            self._set_path(directory)

    def _accept(self) -> None:
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Welcome", "Please choose a folder for your models before continuing.")
            return
        path = os.path.abspath(path)
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:  # pragma: no cover - user filesystem errors
            QMessageBox.critical(
                self,
                "Welcome",
                f"Unable to create or access the selected folder:\n{exc}",
            )
            return

        theme_value = "dark" if self.dark_radio.isChecked() else "light"
        self.result_data = {
            "models_path": path,
            "theme": theme_value,
        }
        self.accept()