import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_ui()
        self.populate_gallery()

    def load_ui(self):
        ui_file = QFile("ui/main_window.ui")
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        ui_file.close()
        self.setCentralWidget(self.ui)

        # Access top bar buttons
        self.ui.btnThemeToggle.clicked.connect(self.toggle_theme)
        self.ui.btnReload.clicked.connect(self.reload_files)
        self.ui.btnImport.clicked.connect(self.import_files)
        self.ui.btnAddModel.clicked.connect(self.add_model)

    # Placeholder methods
    def toggle_theme(self):
        print("Toggle theme")

    def reload_files(self):
        print("Reload files")

    def import_files(self):
        print("Import files")

    def add_model(self):
        print("Add new model")

    def populate_gallery(self):
        # Example: Add 4 placeholder cards
        for row in range(2):
            for col in range(2):
                card = QWidget()
                layout = QVBoxLayout(card)
                layout.setContentsMargins(5, 5, 5, 5)

                thumbnail = QLabel("Thumbnail")
                thumbnail.setFixedSize(150, 150)
                thumbnail.setStyleSheet("background-color: lightgray; border: 1px solid black;")
                layout.addWidget(thumbnail)

                name_label = QLabel(f"Model {row*2 + col +1}")
                layout.addWidget(name_label)

                time_label = QLabel("Print time: 1h30m")
                layout.addWidget(time_label)

                btn_layout = QHBoxLayout()
                btn_3d = QPushButton("3D View")
                btn_edit = QPushButton("Edit")
                btn_layout.addWidget(btn_3d)
                btn_layout.addWidget(btn_edit)
                layout.addLayout(btn_layout)

                self.ui.galleryLayout.addWidget(card, row, col)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())