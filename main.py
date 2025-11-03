import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor

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
        self.card_subtexts = []
        self.cards = []
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

        # We'll move the top-row buttons into a new container so the bar can be styled
        central = self.centralWidget()
        vlayout = central.layout() if central is not None else None

        btn = self.findChild(QPushButton, 'btnThemeToggle') or (self.ui and self.ui.findChild(QPushButton, 'btnThemeToggle'))
        if btn:
            icons_dir = os.path.join(os.path.dirname(__file__), 'assets', 'icons')
            svg_path = os.path.join(icons_dir, 'toggletheme.svg')
            # store path for tinting; apply_theme will set the appropriate tinted icon
            self._theme_icon_path = svg_path if os.path.exists(svg_path) else None
            btn.setText('')
            btn.setToolTip('Toggle theme')
            btn.clicked.connect(self.toggle_theme)
            # make it resize-friendly; square sizing enforced in resizeEvent
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # keep reference so we can swap the icon color when theme changes
            self.theme_button = btn
            # placeholders for tinted icons (computed lazily)
            self._theme_icon_white = None
            self._theme_icon_black = None
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

        # Move the top-row widgets into a new container widget so we can style the bar
        try:
            if vlayout is not None:
                # remove the first item (assumed to be the original top bar layout)
                item = vlayout.takeAt(0)
                # create a new frame/container for the top bar
                from PySide6.QtWidgets import QFrame, QHBoxLayout
                top_bar = QFrame(central)
                top_bar.setObjectName('topBarFrame')
                top_bar_layout = QHBoxLayout(top_bar)
                top_bar_layout.setContentsMargins(6, 6, 6, 6)
                top_bar_layout.setSpacing(6)
                # add known buttons into the new layout in order
                for name in ('btnThemeToggle', 'btnReload', 'btnImport', 'btnAddModel'):
                    w = self.findChild(QPushButton, name) or (self.ui and self.ui.findChild(QPushButton, name))
                    if w is not None:
                        # reparent and add to new layout
                        w.setParent(top_bar)
                        top_bar_layout.addWidget(w)
                # insert the new top_bar back into the vertical layout at position 0
                vlayout.insertWidget(0, top_bar)
        except Exception:
            pass

        # apply an initial sizing pass for the top bar buttons
        self._resize_top_buttons(initial=True)

        # Prepare references to inputs on the second top bar for resizing
        self.top_bar_inputs = []
        search = self.findChild(QLabel, 'searchBox') or (self.ui and self.ui.findChild(QLabel, 'searchBox'))
        # searchBox is a QLineEdit; use a broad lookup in case the above didn't match QLabel
        if search is None:
            from PySide6.QtWidgets import QLineEdit
            search = self.findChild(QLineEdit, 'searchBox') or (self.ui and self.ui.findChild(QLineEdit, 'searchBox'))
        if search:
            try:
                # Make it expand horizontally and be fixed vertically (we'll set its height on resize)
                search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            except Exception:
                pass
            self.top_bar_inputs.append(search)

        from PySide6.QtWidgets import QComboBox
        for name in ('sortDropdown', 'filterDropdown'):
            dd = self.findChild(QComboBox, name) or (self.ui and self.ui.findChild(QComboBox, name))
            if dd:
                try:
                    dd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                except Exception:
                    pass
                self.top_bar_inputs.append(dd)

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
                # Cap icon size so it doesn't get oversized on big windows
                icon_dim = min(24, max(12, target_h - 12))
                btn.setIconSize(QSize(icon_dim, icon_dim))
            else:
                # allow width to expand while fixing height
                btn.setMinimumHeight(target_h)
                btn.setMaximumHeight(target_h)
                # scale the button's font size so the text rescales with the button
                try:
                    # make top-bar button text scale but cap it to avoid huge fonts
                    font_pt = min(16, max(10, int(target_h * 0.34)))
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

        # Resize the search bar and dropdowns to match the top bar height and scale fonts
        try:
            font_pt = max(10, int(target_h * 0.40))
            from PySide6.QtWidgets import QLineEdit, QComboBox
            for w in getattr(self, 'top_bar_inputs', []):
                try:
                    w.setMinimumHeight(target_h)
                    w.setMaximumHeight(target_h)
                    f = w.font() or QFont()
                    f.setFamily('Inter')
                    f.setPointSize(font_pt)
                    f.setBold(False)
                    w.setFont(f)
                    # If this is a combo box, also adjust the view font for consistency
                    if isinstance(w, QComboBox) and w.view():
                        vf = w.view().font() or QFont()
                        vf.setFamily('Inter')
                        vf.setPointSize(max(9, font_pt - 1))
                        w.view().setFont(vf)
                except Exception:
                    pass
        except Exception:
            pass

        # Update card header fonts so they scale with window size as well
        try:
            # pick a card header font size based on window height, clamped to 12-18
            card_pt = max(12, min(18, int(win_h * 0.026)))
            for lbl in getattr(self, 'card_headers', []):
                try:
                    lf = lbl.font() or QFont()
                    lf.setFamily('Inter')
                    lf.setPointSize(card_pt)
                    lf.setBold(True)
                    lbl.setFont(lf)
                    # ensure the header text has no boxed background
                    lbl.setStyleSheet('background: transparent;')
                except Exception:
                    pass
            # card subtext slightly smaller and NOT bold
            sub_pt = max(10, min(15, int(card_pt * 0.85)))
            for lbl in getattr(self, 'card_subtexts', []):
                try:
                    lf = lbl.font() or QFont()
                    lf.setFamily('Inter')
                    lf.setPointSize(sub_pt)
                    lf.setBold(False)
                    lbl.setFont(lf)
                    # ensure subtext has no boxed background
                    lbl.setStyleSheet('background: transparent;')
                except Exception:
                    pass
        except Exception:
            pass

        # Re-layout the gallery based on current width to adjust columns responsively
        try:
            self.relayout_gallery()
        except Exception:
            pass

    def _tint_icon(self, path: str, hex_color: str) -> QIcon:
        """Return a QIcon with the source pixmap tinted to hex_color. Uses SourceIn composition to preserve alpha."""
        try:
            pix = QPixmap(path)
            if pix.isNull():
                # try rendering via QIcon for SVGs
                base = QIcon(path)
                if base.isNull():
                    return QIcon()
                # render to a reasonable base size; final iconSize will be set on button
                pix = base.pixmap(QSize(64, 64))
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

        qss_loaded = False
        if os.path.exists(qss_path):
            try:
                # Try to load the QSS file. Mark as loaded so we don't later
                # override it with the inline fallback.
                with open(qss_path, 'r', encoding='utf-8') as fh:
                    QApplication.instance().setStyleSheet(fh.read())
                    qss_loaded = True
            except Exception:
                qss_loaded = False

        # Only apply the inline fallback if we failed to load a QSS file
        if not qss_loaded:
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
                # lazily compute tinted icons
                if self._theme_icon_white is None:
                    self._theme_icon_white = self._tint_icon(self._theme_icon_path, '#FFFFFF')
                if self._theme_icon_black is None:
                    self._theme_icon_black = self._tint_icon(self._theme_icon_path, '#000000')

                if dark:
                    # dark mode: button background is black -> icon should be white
                    if self._theme_icon_white:
                        self.theme_button.setIcon(self._theme_icon_white)
                else:
                    # light mode: button background is white -> icon should be black
                    if self._theme_icon_black:
                        self.theme_button.setIcon(self._theme_icon_black)
                # keep icon size consistent with button
                try:
                    btn_h = self.theme_button.height() or self.theme_button.sizeHint().height() or 28
                    self.theme_button.setIconSize(QSize(max(8, btn_h - 8), max(8, btn_h - 8)))
                except Exception:
                    pass
        except Exception:
            pass

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

        # Keep references for responsive relayout
        self.gallery_container = container
        self.gallery_layout = gallery_layout
        # Optionally tune spacing/margins for the grid
        try:
            self.gallery_layout.setHorizontalSpacing(8)
            self.gallery_layout.setVerticalSpacing(8)
            self.gallery_layout.setContentsMargins(6, 6, 6, 6)
        except Exception:
            pass

        # Only populate cards once
        if not self.cards:
            for i in range(4):
                card = QWidget()
                layout = QVBoxLayout(card)
                layout.setContentsMargins(5, 5, 5, 5)

                thumbnail = QLabel("Thumbnail")
                # Allow the thumbnail to expand with the card and keep a minimum size
                thumbnail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                thumbnail.setMinimumSize(80, 80)
                thumbnail.setAlignment(Qt.AlignCenter)
                # mark for QSS styling
                thumbnail.setProperty('thumbnail', True)
                # If you later set a pixmap, scaledContents=True will make it scale to the label
                thumbnail.setScaledContents(True)
                layout.addWidget(thumbnail)

                name_label = QLabel(f"Model {i + 1}")
                # mark as a card header and track for dynamic font resizing (bold, not blue)
                name_label.setProperty('cardHeader', True)
                # remove any boxed background so the text appears directly on the card
                name_label.setStyleSheet('background: transparent;')
                layout.addWidget(name_label)
                # store reference for dynamic resizing
                self.card_headers.append(name_label)
                time_label = QLabel("Print time: 1h30m")
                time_label.setProperty('cardSub', True)
                # remove boxed background from the subtext as well
                time_label.setStyleSheet('background: transparent;')
                layout.addWidget(time_label)
                # store reference for dynamic resizing
                self.card_subtexts.append(time_label)

                btn_layout = QHBoxLayout()
                btn_3d = QPushButton("3D View")
                btn_edit = QPushButton("Edit")
                # set icons for the buttons (use SVGs)
                icons_dir = os.path.join(os.path.dirname(__file__), 'assets', 'icons')
                view_svg = os.path.join(icons_dir, '3dview.svg')
                edit_svg = os.path.join(icons_dir, 'editmodel.svg')
                if os.path.exists(view_svg):
                    btn_3d.setIcon(QIcon(view_svg))
                    btn_3d.setIconSize(QSize(18, 18))
                if os.path.exists(edit_svg):
                    btn_edit.setIcon(QIcon(edit_svg))
                    btn_edit.setIconSize(QSize(18, 18))
                btn_layout.addWidget(btn_3d)
                btn_layout.addWidget(btn_edit)
                layout.addLayout(btn_layout)
                # mark the card widget for QSS
                card.setProperty('card', True)

                self.cards.append(card)

        # Initial layout
        self.relayout_gallery()

    def relayout_gallery(self):
        """Compute number of columns based on available width and re-add cards to grid."""
        container = getattr(self, 'gallery_container', None)
        layout = getattr(self, 'gallery_layout', None)
        if container is None or layout is None or not self.cards:
            return

        # Determine available width inside the scroll area contents
        try:
            margins = layout.contentsMargins()
            available_w = max(1, container.width() - (margins.left() + margins.right()))
            spacing = layout.horizontalSpacing() if layout.horizontalSpacing() is not None else 6
        except Exception:
            available_w = max(1, container.width())
            spacing = 6

        # Choose a minimum card width and compute how many columns fit
        min_card_w = 240
        cols = max(1, int((available_w + spacing) / (min_card_w + spacing)))

        # Clear current layout placements (but keep widgets alive)
        try:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    layout.removeWidget(w)
        except Exception:
            pass

        # Add cards row by row
        r = 0
        c = 0
        for card in self.cards:
            layout.addWidget(card, r, c)
            c += 1
            if c >= cols:
                c = 0
                r += 1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # set global fonts (will fallback to system fonts if Inter / JetBrains Mono are not installed)
    try:
        app.setFont(QFont('Inter', 13))
    except Exception:
        pass
    window = MainWindow()
    window.show()
    # set application/window icon and title
    logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'logo.svg')
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
        window.setWindowIcon(QIcon(logo_path))
    window.setWindowTitle('zPrint')
    # Run an initial sizing pass after show to pick up platform metrics
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window._resize_top_buttons)
    sys.exit(app.exec())