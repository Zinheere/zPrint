import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize
from PySide6.QtGui import QIcon, QFont

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # theme state: False = light, True = dark
        self.dark_theme = False
        self.load_ui()
        # apply the chosen theme immediately on startup
        self.apply_theme(self.dark_theme)
        # tracked card header labels for dynamic font resizing
        self.card_headers = []
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
        # We'll collect the top-bar buttons so we can resize them together later.
        self.top_bar_buttons = []

        btn = self.findChild(QPushButton, 'btnThemeToggle') or (self.ui and self.ui.findChild(QPushButton, 'btnThemeToggle'))
        if btn:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'image.png')
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
            btn.setText('')
            btn.setToolTip('Toggle theme')
            btn.clicked.connect(self.toggle_theme)
            # make it resize-friendly; square sizing enforced in resizeEvent
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnReload') or (self.ui and self.ui.findChild(QPushButton, 'btnReload'))
        if btn:
            btn.clicked.connect(self.reload_files)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnImport') or (self.ui and self.ui.findChild(QPushButton, 'btnImport'))
        if btn:
            btn.clicked.connect(self.import_files)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnAddModel') or (self.ui and self.ui.findChild(QPushButton, 'btnAddModel'))
        if btn:
            btn.clicked.connect(self.add_model)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.top_bar_buttons.append(btn)

        # apply an initial sizing pass for the top bar buttons
        self._resize_top_buttons(initial=True)

    def resizeEvent(self, event):
        # Update button sizes whenever the main window resizes so they scale with the window
        try:
            self._resize_top_buttons()
        except Exception:
            pass
        super().resizeEvent(event)

    def _resize_top_buttons(self, initial=False):
        # Compute a target height for top-bar buttons based on window height
        if not hasattr(self, 'top_bar_buttons') or not self.top_bar_buttons:
            return
        win_h = max(1, self.height())
        # choose a height between 28 and 56 px based on window height (roughly 4-8% of height)
        target_h = max(28, min(56, int(win_h * 0.06)))

        for btn in self.top_bar_buttons:
            # theme button should be square; detect by objectName
            if btn.objectName() == 'btnThemeToggle':
                btn.setFixedSize(QSize(target_h, target_h))
                btn.setIconSize(QSize(max(8, target_h - 8), max(8, target_h - 8)))
            else:
                # allow width to expand while fixing height
                btn.setMinimumHeight(target_h)
                btn.setMaximumHeight(target_h)
                # scale the button's font size so the text rescales with the button
                try:
                    # make top-bar button text larger; only Add Model is bold
                    font_pt = max(10, int(target_h * 0.42))
                    f = btn.font() or QFont()
                    f.setFamily('Inter')
                    f.setPointSize(font_pt)
                    if btn.objectName() == 'btnAddModel':
                        f.setBold(True)
                    else:
                        f.setBold(False)
                    btn.setFont(f)
                except Exception:
                    # don't fail on font errors
                    pass

        # Update card header fonts so they scale with window size as well
        try:
            # pick a card header font size based on window height, clamped to 12-20
            card_pt = max(12, min(20, int(win_h * 0.028)))
            for lbl in getattr(self, 'card_headers', []):
                try:
                    lf = lbl.font() or QFont()
                    lf.setFamily('Inter')
                    lf.setPointSize(card_pt)
                    lf.setBold(True)
                    lbl.setFont(lf)
                    # ensure not colored blue by QSS
                    lbl.setStyleSheet('')
                except Exception:
                    pass
        except Exception:
            pass

    # Placeholder methods
    def toggle_theme(self):
        # Toggle theme state and apply the corresponding QSS
        self.dark_theme = not getattr(self, 'dark_theme', False)
        self.apply_theme(self.dark_theme)

    def apply_theme(self, dark: bool):
        """Load the QSS for the chosen theme (dark=True) or light (dark=False).
        Falls back to a minimal inline stylesheet if the file read fails."""
        themes_dir = os.path.join(os.path.dirname(__file__), 'assets', 'themes')
        qss_name = 'dark.qss' if dark else 'light.qss'
        qss_path = os.path.join(themes_dir, qss_name)

        if os.path.exists(qss_path):
            try:
                with open(qss_path, 'r', encoding='utf-8') as fh:
                    QApplication.instance().setStyleSheet(fh.read())
                return
            except Exception:
                pass

        # Inline fallback
        if dark:
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
                # mark as a card header and track for dynamic font resizing (bold, not blue)
                name_label.setProperty('cardHeader', True)
                # clear any inline color so QSS handles base color; we'll set font dynamically
                name_label.setStyleSheet("")
                layout.addWidget(name_label)
                # store reference for dynamic resizing
                self.card_headers.append(name_label)

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
    # set global fonts (will fallback to system fonts if Inter / JetBrains Mono are not installed)
    try:
        app.setFont(QFont('Inter', 13))
    except Exception:
        pass
    window = MainWindow()
    window.show()
    # Run an initial sizing pass after show to pick up platform metrics
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window._resize_top_buttons)
    sys.exit(app.exec())