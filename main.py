import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

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
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'toggletheme.svg')
            # prepare SVG icons (white/black) for swapping later
            self._theme_icon_path = icon_path if os.path.exists(icon_path) else None
            self._theme_icon_white = None
            self._theme_icon_black = None
            if self._theme_icon_path:
                # create small default icons; real sizing will be applied later
                try:
                    self._theme_icon_white = self._icon_from_svg(self._theme_icon_path, '#FFFFFF', 20)
                    self._theme_icon_black = self._icon_from_svg(self._theme_icon_path, '#000000', 20)
                    # set a default icon now (will be updated by apply_theme)
                    btn.setIcon(self._theme_icon_black if not self.dark_theme else self._theme_icon_white)
                except Exception:
                    pass
            btn.setText('')
            btn.setToolTip('Toggle theme')
            btn.clicked.connect(self.toggle_theme)
            # make it resize-friendly; square sizing enforced in resizeEvent
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # keep reference so we can swap the icon color when theme changes
            self.theme_button = btn
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

    def _tint_icon(self, path: str, hex_color: str) -> QIcon:
        """Return a QIcon with the source pixmap tinted to hex_color. Uses SourceIn composition to preserve alpha."""
        try:
            pix = QPixmap(path)
            if pix.isNull():
                return QIcon()
            out = QPixmap(pix.size())
            out.fill(QColor(0, 0, 0, 0))
            painter = QPainter(out)
            painter.drawPixmap(0, 0, pix)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(out.rect(), QColor(hex_color))
            painter.end()
            return QIcon(out)
        except Exception:
            return QIcon()

    def _icon_from_svg(self, path: str, hex_color: str, size: int) -> QIcon:
        """Render an SVG at the requested square size and tint it to hex_color, returning a QIcon."""
        try:
            renderer = QSvgRenderer(path)
            pix = QPixmap(size, size)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pix.rect(), QColor(hex_color))
            painter.end()
            return QIcon(pix)
        except Exception:
            # fallback: try tinting a rasterized version
            return self._tint_icon(path, hex_color)

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
                # continue to update themed icons after applying stylesheet
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

        # Update the theme toggle icon to be the opposite color of the button background
        try:
            if hasattr(self, 'theme_button') and self._theme_icon_path:
                # lazily compute tinted icons using SVG renderer when possible
                if self._theme_icon_white is None or self._theme_icon_black is None:
                    try:
                        self._theme_icon_white = self._icon_from_svg(self._theme_icon_path, '#FFFFFF', 20)
                        self._theme_icon_black = self._icon_from_svg(self._theme_icon_path, '#000000', 20)
                    except Exception:
                        # fallback to raster tint
                        if self._theme_icon_white is None:
                            self._theme_icon_white = self._tint_icon(self._theme_icon_path, '#FFFFFF')
                        if self._theme_icon_black is None:
                            self._theme_icon_black = self._tint_icon(self._theme_icon_path, '#000000')

                if dark:
                    # dark mode: button background is white (per dark.qss) -> icon should be black
                    if self._theme_icon_black:
                        self.theme_button.setIcon(self._theme_icon_black)
                else:
                    # light mode: button background is black (per light.qss) -> icon should be white
                    if self._theme_icon_white:
                        self.theme_button.setIcon(self._theme_icon_white)
                # keep icon size consistent with button
                try:
                    btn_h = self.theme_button.height() or self.theme_button.sizeHint().height() or 28
                    self.theme_button.setIconSize(QSize(max(8, btn_h - 8), max(8, btn_h - 8)))
                except Exception:
                    pass

            # Also update shared icons used in gallery buttons (cache them)
            icon_color = '#FFFFFF' if dark else '#000000'
            svg_3d = os.path.join(os.path.dirname(__file__), 'assets', 'icons', '3dview.svg')
            svg_edit = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'editmodel.svg')
            try:
                if os.path.exists(svg_3d):
                    self._icon_3d = self._icon_from_svg(svg_3d, icon_color, 16)
                else:
                    self._icon_3d = None
                if os.path.exists(svg_edit):
                    self._icon_edit = self._icon_from_svg(svg_edit, icon_color, 16)
                else:
                    self._icon_edit = None
            except Exception:
                self._icon_3d = None
                self._icon_edit = None
        except Exception:
            pass

    def reload_files(self):
        print("Reload files")

    def import_files(self):
        print("Import files")

    def add_model(self):
        print("Add new model")

    def populate_gallery(self):
        # Example: Add 4 placeholder cards using a Designer-editable template `ui/model_card.ui`
        # find the scroll area contents widget and its layout that holds the gallery
        container = self.findChild(QWidget, 'scrollAreaWidgetContents')
        if container is None and self.ui is not None:
            container = self.ui.findChild(QWidget, 'scrollAreaWidgetContents')

        gallery_layout = container.layout() if container is not None else None
        if gallery_layout is None:
            # nothing to attach to
            return

        # Load the model card template UI and instantiate copies using QUiLoader
        loader = QUiLoader()
        for row in range(2):
            for col in range(2):
                ui_file = QFile('ui/model_card.ui')
                ui_file.open(QFile.ReadOnly)
                card = loader.load(ui_file, self)
                ui_file.close()
                if card is None:
                    continue

                # Populate fields
                thumb = card.findChild(QLabel, 'thumbnailLabel')
                if thumb is not None:
                    thumb.setText('Thumbnail')
                    thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    thumb.setMinimumSize(80, 80)
                    thumb.setAlignment(Qt.AlignCenter)
                    thumb.setScaledContents(True)

                name_label = card.findChild(QLabel, 'nameLabel')
                if name_label is not None:
                    name_label.setText(f'Model {row*2 + col + 1}')
                    self.card_headers.append(name_label)

                time_label = card.findChild(QLabel, 'timeLabel')
                if time_label is not None:
                    time_label.setText('Print time: 1h30m')

                btn_3d = card.findChild(QPushButton, 'btn3d')
                btn_edit = card.findChild(QPushButton, 'btnEditModel')
                # set icons for these buttons using cached icons if available
                try:
                    if hasattr(self, '_icon_3d') and self._icon_3d:
                        if btn_3d is not None:
                            btn_3d.setIcon(self._icon_3d)
                    else:
                        svg_3d = os.path.join(os.path.dirname(__file__), 'assets', 'icons', '3dview.svg')
                        if os.path.exists(svg_3d) and btn_3d is not None:
                            btn_3d.setIcon(self._icon_from_svg(svg_3d, '#FFFFFF' if self.dark_theme else '#000000', 16))
                    if hasattr(self, '_icon_edit') and self._icon_edit:
                        if btn_edit is not None:
                            btn_edit.setIcon(self._icon_edit)
                    else:
                        svg_edit = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'editmodel.svg')
                        if os.path.exists(svg_edit) and btn_edit is not None:
                            btn_edit.setIcon(self._icon_from_svg(svg_edit, '#FFFFFF' if self.dark_theme else '#000000', 16))
                except Exception:
                    pass

                gallery_layout.addWidget(card, row, col)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # set global fonts (will fallback to system fonts if Inter / JetBrains Mono are not installed)
    try:
        app.setFont(QFont('Inter', 13))
    except Exception:
        pass
    # set application icon (logo.svg)
    try:
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'logo.svg')
        if os.path.exists(logo_path):
            app.setWindowIcon(QIcon(logo_path))
    except Exception:
        pass
    window = MainWindow()
    window.setWindowTitle("zPrint")
    window.show()
    # Run an initial sizing pass after show to pick up platform metrics
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window._resize_top_buttons)
    sys.exit(app.exec())