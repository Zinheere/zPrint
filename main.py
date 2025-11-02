import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize
from PySide6.QtGui import QIcon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # theme state: False = light, True = dark
        self.dark_theme = False
        self.load_ui()
        self.populate_gallery()

    def load_ui(self):
        ui_file = QFile("ui/main_window.ui")
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        loaded = loader.load(ui_file)
        ui_file.close()

        # The .ui file's top-level widget is a QMainWindow. We are already a QMainWindow
        # subclass, so extract the central widget from the loaded UI and set it here.
        if isinstance(loaded, QMainWindow):
            central = loaded.findChild(QWidget, 'centralwidget')
            if central is not None:
                self.setCentralWidget(central)
            else:
                # fallback: if centralwidget not found, use loaded as widget
                self.setCentralWidget(loaded)
            # keep reference to the loaded object so we can find children inside it
            self.ui = loaded
        else:
            # loaded a widget (not a QMainWindow) - use it directly
            self.ui = loaded
            self.setCentralWidget(self.ui)

        # Access top bar buttons by object name (use findChild because loader returned
        # a separate object rather than attaching attributes to this instance)
        btn = self.findChild(QPushButton, 'btnThemeToggle') or (self.ui and self.ui.findChild(QPushButton, 'btnThemeToggle'))
        if btn:
            # make it an icon-only button that matches other buttons and is square
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'image.png')
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
            btn.setText('')
            # determine a target size using another top-bar button (btnReload) if available
            ref = self.findChild(QPushButton, 'btnReload') or (self.ui and self.ui.findChild(QPushButton, 'btnReload'))
            target_h = 28
            if ref is not None:
                # sizeHint may be 0 before show(); try sizeHint then minimumSizeHint
                hint = ref.sizeHint().height() or ref.minimumSizeHint().height()
                if hint and hint > 0:
                    target_h = hint
            btn.setFixedSize(QSize(target_h, target_h))
            # icon should be slightly smaller to provide padding
            btn.setIconSize(QSize(max(8, target_h - 8), max(8, target_h - 8)))
            # keep the same visual style as other QPushButton elements (don't make it flat)
            btn.setToolTip('Toggle theme')
            btn.clicked.connect(self.toggle_theme)

        btn = self.findChild(QPushButton, 'btnReload') or (self.ui and self.ui.findChild(QPushButton, 'btnReload'))
        if btn:
            btn.clicked.connect(self.reload_files)

        btn = self.findChild(QPushButton, 'btnImport') or (self.ui and self.ui.findChild(QPushButton, 'btnImport'))
        if btn:
            btn.clicked.connect(self.import_files)

        btn = self.findChild(QPushButton, 'btnAddModel') or (self.ui and self.ui.findChild(QPushButton, 'btnAddModel'))
        if btn:
            btn.clicked.connect(self.add_model)

    # Placeholder methods
    def toggle_theme(self):
        # Toggle theme by loading QSS files from assets/themes with an inline fallback
        self.dark_theme = not getattr(self, 'dark_theme', False)
        themes_dir = os.path.join(os.path.dirname(__file__), 'assets', 'themes')
        qss_name = 'dark.qss' if self.dark_theme else 'light.qss'
        qss_path = os.path.join(themes_dir, qss_name)

        if os.path.exists(qss_path):
            try:
                with open(qss_path, 'r', encoding='utf-8') as fh:
                    QApplication.instance().setStyleSheet(fh.read())
                return
            except Exception:
                # fall through to inline fallback on error
                pass

        # Inline fallback (kept minimal)
        if self.dark_theme:
            dark = '''
            QWidget { background-color: #2b2b2b; color: #e6e6e6; }
            QLineEdit, QComboBox, QScrollArea { background-color: #3c3c3c; }
            QPushButton { background-color: #444444; color: #e6e6e6; border: none; padding: 4px; }
            QPushButton:pressed { background-color: #555555; }
            '''
            QApplication.instance().setStyleSheet(dark)
        else:
            QApplication.instance().setStyleSheet('')

    def reload_files(self):
        print("Reload files")

    def import_files(self):
        print("Import files")

    def add_model(self):
        print("Add new model")

    def populate_gallery(self):
        # Example: Add 4 placeholder cards
        # find the scroll area contents widget and its layout that holds the gallery
        container = self.findChild(QWidget, 'scrollAreaWidgetContents')
        if container is None and self.ui is not None:
            container = self.ui.findChild(QWidget, 'scrollAreaWidgetContents')

        gallery_layout = container.layout() if container is not None else None
        if gallery_layout is None:
            # nothing to attach to
            return

        for row in range(2):
            for col in range(2):
                card = QWidget()
                layout = QVBoxLayout(card)
                layout.setContentsMargins(5, 5, 5, 5)

                thumbnail = QLabel("Thumbnail")
                # Allow the thumbnail to expand with the card and keep a minimum size
                thumbnail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                thumbnail.setMinimumSize(80, 80)
                thumbnail.setAlignment(Qt.AlignCenter)
                # If you later set a pixmap, scaledContents=True will make it scale to the label
                thumbnail.setScaledContents(True)
                thumbnail.setStyleSheet("background-color: lightgray; border: 1px solid black;")
                layout.addWidget(thumbnail)

                name_label = QLabel(f"Model {row*2 + col +1}")
                # Make the model name larger and bold
                name_label.setStyleSheet("font-size: 14pt; font-weight: 600;")
                layout.addWidget(name_label)

                time_label = QLabel("Print time: 1h30m")
                # Make print time smaller and muted
                time_label.setStyleSheet("font-size: 8pt; color: gray;")
                layout.addWidget(time_label)

                btn_layout = QHBoxLayout()
                btn_3d = QPushButton("3D View")
                btn_edit = QPushButton("Edit")
                btn_layout.addWidget(btn_3d)
                btn_layout.addWidget(btn_edit)
                layout.addLayout(btn_layout)

                gallery_layout.addWidget(card, row, col)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())