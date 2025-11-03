import sys
import os
import json
from functools import partial
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
# NEW: try QtSvg for reliable SVG rendering
try:
    from PySide6.QtSvg import QSvgRenderer  # type: ignore
except Exception:
    QSvgRenderer = None
import xml.etree.ElementTree as ET

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # theme state: False = light, True = dark
        self.app_dir = os.path.dirname(__file__)
        self.config = self._load_config()
        mode_theme = self.config.get('theme', 'light').lower()
        self.dark_theme = mode_theme == 'dark'
        self.models_root = self._resolve_models_root()
        self._icons_dir = os.path.join(self.app_dir, 'assets', 'icons')
        # track widgets/actions that need tinted icons reapplied on theme/resize
        self._icon_targets = []  # entries: {'kind': 'button'|'action', 'widget': QWidget, 'action': QAction|None, 'path': str}
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
            self._theme_icon_path = self._resolve_icon_path('toggletheme.svg')
            btn.setToolTip('Toggle theme')
            btn.clicked.connect(self.toggle_theme)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.theme_button = btn
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnReload') or (self.ui and self.ui.findChild(QPushButton, 'btnReload'))
        if btn:
            btn.clicked.connect(self.reload_files)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._register_icon(btn, ('reload.svg', 'refresh.svg'))
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnImport') or (self.ui and self.ui.findChild(QPushButton, 'btnImport'))
        if btn:
            btn.clicked.connect(self.import_files)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._register_icon(btn, ('import.svg', 'upload.svg', 'open.svg'))
            self.top_bar_buttons.append(btn)

        btn = self.findChild(QPushButton, 'btnAddModel') or (self.ui and self.ui.findChild(QPushButton, 'btnAddModel'))
        if btn:
            btn.clicked.connect(self.add_model)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._register_icon(btn, ('addmodel.svg', 'add.svg', 'plus.svg', 'new.svg'))
            self._btn_add_model = btn
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
        if search is None:
            from PySide6.QtWidgets import QLineEdit
            search = self.findChild(QLineEdit, 'searchBox') or (self.ui and self.ui.findChild(QLineEdit, 'searchBox'))
        if search is not None:
            from PySide6.QtWidgets import QLineEdit as _QLE
            search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            action = search.addAction(QIcon(), _QLE.LeadingPosition)
            self._register_icon(search, ('search.svg', 'magnify.svg', 'magnifier.svg'), action)
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

        # Align the second top bar layout margins/spacings so height matches the first bar
        try:
            from PySide6.QtWidgets import QHBoxLayout as _QHB
            bar2 = self.findChild(_QHB, 'topBar2Layout') or (self.ui and self.ui.findChild(_QHB, 'topBar2Layout'))
            if bar2:
                bar2.setContentsMargins(6, 6, 6, 6)
                bar2.setSpacing(6)
        except Exception:
            pass

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
            # theme button square only if an SVG icon is present
            if btn.objectName() == 'btnThemeToggle' and getattr(self, '_theme_icon_path', None):
                btn.setFixedSize(QSize(target_h, target_h))
                # Cap icon size so it doesn't get oversized on big windows
                icon_dim = min(24, max(12, target_h - 12))
                try:
                    btn.setIconSize(QSize(icon_dim, icon_dim))
                except Exception:
                    pass
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
                # Adjust icon size for icon-bearing buttons (only if explicitly set)
                if not btn.icon().isNull():
                    icon_dim = min(22, max(12, target_h - 14))
                    btn.setIconSize(QSize(icon_dim, icon_dim))
            except Exception:
                # don't fail on font errors
                pass

        # Resize the search bar and dropdowns to match the top bar height and scale fonts
        try:
            from PySide6.QtWidgets import QLineEdit, QComboBox
            # Determine input font to match the New Model button's font size
            try:
                add_font_pt = None
                if hasattr(self, '_btn_add_model') and self._btn_add_model is not None:
                    add_font_pt = self._btn_add_model.font().pointSize()
                    if add_font_pt is None or add_font_pt <= 0:
                        add_font_pt = None
                if add_font_pt is None:
                    # fallback: compute similarly to button sizing (same cap)
                    add_font_pt = min(16, max(10, int(target_h * 0.34)))
            except Exception:
                add_font_pt = min(16, max(10, int(target_h * 0.34)))
            # determine the max height to use based on the Add Model button's max height
            btn_max_h = target_h
            try:
                if hasattr(self, '_btn_add_model') and self._btn_add_model is not None:
                    # prefer the button's explicit maximumHeight if set; fall back to current height/size hint
                    btn_max_h = self._btn_add_model.maximumHeight() or self._btn_add_model.height() or self._btn_add_model.sizeHint().height() or target_h
            except Exception:
                btn_max_h = target_h
            for w in getattr(self, 'top_bar_inputs', []):
                try:
                    # make inputs' max height match the Add Model button's max side
                    w.setMaximumHeight(btn_max_h)
                    # keep min height aligned as well to avoid jitter
                    w.setMinimumHeight(btn_max_h)
                    f = w.font() or QFont()
                    f.setFamily('Inter')
                    f.setPointSize(add_font_pt)
                    f.setBold(False)
                    w.setFont(f)
                    # If this is a combo box, also adjust the view font for consistency
                    if isinstance(w, QComboBox) and w.view():
                        vf = w.view().font() or QFont()
                        vf.setFamily('Inter')
                        vf.setPointSize(max(9, add_font_pt - 1))
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
        # Update tinted icons to reflect any size changes from resize
        try:
            self._update_all_tinted_icons()
        except Exception:
            pass

    def _tint_icon(self, path: str, hex_color: str, size: QSize | None = None) -> QIcon:
        """Render an SVG (or image) and tint to hex_color. Uses QSvgRenderer if available."""
        try:
            if size is None:
                size = QSize(64, 64)
            w = max(1, size.width())
            h = max(1, size.height())

            # Prefer QSvgRenderer for SVGs
            if path.lower().endswith('.svg') and QSvgRenderer is not None:
                # Attempt to sanitize background rectangles from the SVG before rendering
                renderer = None
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        svg_text = fh.read()
                    # Parse and remove obvious full-canvas background rects
                    try:
                        root = ET.fromstring(svg_text)
                        # Determine canvas size from viewBox if available
                        vb = root.attrib.get('viewBox')
                        vb_w = vb_h = None
                        if vb:
                            parts = [p for p in vb.replace(',', ' ').split(' ') if p.strip()]
                            if len(parts) == 4:
                                try:
                                    vb_w = float(parts[2])
                                    vb_h = float(parts[3])
                                except Exception:
                                    vb_w = vb_h = None
                        # Iterate over rects and remove ones covering full canvas or 100%
                        removed_any = False
                        for parent in list(root.iter()):
                            # Work on a copy of list to allow removal
                            for rect in list(parent):
                                if rect.tag.lower().endswith('rect'):
                                    w_attr = rect.attrib.get('width', '')
                                    h_attr = rect.attrib.get('height', '')
                                    x_attr = rect.attrib.get('x', '0')
                                    y_attr = rect.attrib.get('y', '0')
                                    style = rect.attrib.get('style', '')
                                    fill = rect.attrib.get('fill', '')
                                    def to_float(v):
                                        try:
                                            v = v.replace('px', '')
                                            return float(v)
                                        except Exception:
                                            return None
                                    # Heuristic: 100% x 100% or matches viewBox size at x=0,y=0 and has a fill (not none)
                                    is_percent_full = (w_attr.strip().endswith('%') and h_attr.strip().endswith('%') and w_attr.strip().startswith('100') and h_attr.strip().startswith('100'))
                                    w_num = to_float(w_attr)
                                    h_num = to_float(h_attr)
                                    x_num = to_float(x_attr) or 0.0
                                    y_num = to_float(y_attr) or 0.0
                                    matches_vb = (vb_w is not None and vb_h is not None and w_num == vb_w and h_num == vb_h and abs(x_num) < 1e-6 and abs(y_num) < 1e-6)
                                    has_fill = ('fill:' in style and 'fill:none' not in style.replace(' ', '').lower()) or (fill and fill.lower() != 'none')
                                    if has_fill and (is_percent_full or matches_vb):
                                        try:
                                            parent.remove(rect)
                                            removed_any = True
                                        except Exception:
                                            pass
                        if removed_any:
                            cleaned = ET.tostring(root, encoding='utf-8')
                            renderer = QSvgRenderer(QByteArray(cleaned))
                        else:
                            renderer = QSvgRenderer(path)
                    except Exception:
                        # Fallback to loading directly if parsing fails
                        renderer = QSvgRenderer(path)
                except Exception:
                    renderer = QSvgRenderer(path)
                if renderer.isValid():
                    pm = QPixmap(w, h)
                    pm.fill(Qt.transparent)
                    p = QPainter(pm)
                    renderer.render(p)
                    p.end()

                    # Create solid color pixmap and mask it with rendered alpha
                    tinted = QPixmap(w, h)
                    tinted.fill(Qt.transparent)
                    p = QPainter(tinted)
                    p.fillRect(0, 0, w, h, QColor(hex_color))
                    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                    p.drawPixmap(0, 0, pm)
                    p.end()
                    return QIcon(tinted)

            # Fallback: load via QIcon and paint it, then tint
            base = QIcon(path)
            if base.isNull():
                return QIcon()
            pm = QPixmap(w, h)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            base.paint(p, 0, 0, w, h)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(0, 0, w, h, QColor(hex_color))
            p.end()
            return QIcon(pm)
        except Exception:
            return QIcon()

    def _load_config(self) -> dict:
        defaults = {
            'mode': 'local',
            'local_path': os.path.join(self.app_dir, 'testfiles'),
            'theme': 'light'
        }
        config_path = os.path.join(self.app_dir, 'testfiles', 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                defaults.update(data)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return defaults

    def _resolve_models_root(self) -> str:
        mode = (self.config.get('mode') or 'local').lower()
        path = None
        if mode == 'microsd':
            path = self.config.get('microsd_path') or self.config.get('local_path')
        else:
            path = self.config.get('local_path')
        if not path:
            path = os.path.join(self.app_dir, 'testfiles')
        path = os.path.expandvars(os.path.expanduser(path))
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self.app_dir, path))
        return path

    def _resolve_icon_path(self, candidates) -> str | None:
        if isinstance(candidates, str):
            candidates = (candidates,)
        for name in candidates:
            path = os.path.join(self._icons_dir, name)
            if os.path.exists(path):
                return path
        return None

    def _register_icon(self, widget, candidates, action=None) -> str | None:
        path = self._resolve_icon_path(candidates)
        if not path:
            return None
        self._icon_targets = [t for t in self._icon_targets if not (t.get('widget') is widget and t.get('action') is action)]
        self._icon_targets.append({'kind': 'action' if action else 'button', 'widget': widget, 'action': action, 'path': path})
        return path

    def _load_models_data(self) -> list[dict]:
        models = []
        root = self.models_root
        if not os.path.isdir(root):
            return models
        for entry in sorted(os.listdir(root)):
            folder_path = os.path.join(root, entry)
            if not os.path.isdir(folder_path):
                continue
            meta_path = os.path.join(folder_path, 'model.json')
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as fh:
                        meta = json.load(fh) or {}
                except Exception:
                    meta = {}
            model_name = meta.get('name') or entry
            preview_rel = meta.get('preview_image')
            preview_path = None
            if preview_rel:
                candidate = os.path.join(folder_path, preview_rel)
                if os.path.exists(candidate):
                    preview_path = candidate
            gcodes = meta.get('gcodes') or []
            display_time = ''
            for g in gcodes:
                time_text = g.get('print_time')
                if time_text:
                    display_time = str(time_text)
                    break
            if not display_time:
                display_time = str(meta.get('print_time', '')) if meta.get('print_time') is not None else ''
            models.append({
                'name': model_name,
                'folder': folder_path,
                'preview_path': preview_path,
                'gcodes': gcodes,
                'print_time': display_time,
                'metadata': meta
            })
        return models

    def _clear_gallery(self):
        # Remove previous card widgets and associated icon registrations
        if hasattr(self, 'cards') and self.cards:
            for card in self.cards:
                for btn in card.findChildren(QPushButton):
                    self._icon_targets = [t for t in self._icon_targets if t.get('widget') is not btn]
                card.deleteLater()
        self.cards = []
        self.card_headers = []
        self.card_subtexts = []
        if hasattr(self, 'gallery_layout') and self.gallery_layout is not None:
            while self.gallery_layout.count():
                item = self.gallery_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _refresh_gallery(self):
        data = self._load_models_data()
        self._clear_gallery()
        if not getattr(self, 'gallery_layout', None):
            return

        for model in data:
            card = QWidget()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(5, 5, 5, 5)

            thumbnail = QLabel()
            thumbnail.setAlignment(Qt.AlignCenter)
            thumbnail.setProperty('thumbnail', True)
            thumbnail.setScaledContents(True)
            thumbnail.setMinimumSize(120, 120)
            thumbnail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            preview_path = model.get('preview_path')
            if preview_path:
                pix = QPixmap(preview_path)
                if not pix.isNull():
                    thumbnail.setPixmap(pix)
                else:
                    thumbnail.setText('No Preview')
            else:
                thumbnail.setText('No Preview')
            layout.addWidget(thumbnail)

            name_label = QLabel(model.get('name', ''))
            name_label.setProperty('cardHeader', True)
            name_label.setStyleSheet('background: transparent;')
            layout.addWidget(name_label)
            self.card_headers.append(name_label)

            time_text = model.get('print_time') or 'N/A'
            time_label = QLabel(f"Print time: {time_text}")
            time_label.setProperty('cardSub', True)
            time_label.setStyleSheet('background: transparent;')
            layout.addWidget(time_label)
            self.card_subtexts.append(time_label)

            btn_layout = QHBoxLayout()
            btn_3d = QPushButton('3D View')
            self._register_icon(btn_3d, ('3dview.svg', '3dviewbutton.svg'))
            btn_3d.clicked.connect(partial(self.view_model, model))
            btn_edit = QPushButton('Edit')
            self._register_icon(btn_edit, ('editmodel.svg', 'editbutton.svg'))
            btn_edit.clicked.connect(partial(self.edit_model, model))
            btn_layout.addWidget(btn_3d)
            btn_layout.addWidget(btn_edit)
            layout.addLayout(btn_layout)

            card.setProperty('card', True)
            self.cards.append(card)

        self.relayout_gallery()
        self._update_all_tinted_icons()

    def _icon_color_for_theme(self) -> str:
        """Color for icons based on current theme: black on light, white on dark."""
        return '#000000' if not getattr(self, 'dark_theme', False) else '#FFFFFF'

    def _compute_icon_dim(self, widget) -> int:
        """Compute icon dimension from widget height with sensible clamps."""
        try:
            h = widget.height() or widget.sizeHint().height() or 28
        except Exception:
            h = 28
        return min(22, max(12, h - 14))

    def _update_all_tinted_icons(self):
        """Reapply tinted icons for all registered targets (toolbar/search/card)."""
        color = self._icon_color_for_theme()
        for entry in list(self._icon_targets):
            kind = entry.get('kind')
            path = entry.get('path')
            if not path or not os.path.exists(path):
                continue
            if kind == 'button':
                btn = entry.get('widget')
                if not btn:
                    continue
                dim = self._compute_icon_dim(btn)
                icon = self._tint_icon(path, color, QSize(dim, dim))
                if icon and not icon.isNull():
                    btn.setIcon(icon)
                    try:
                        btn.setIconSize(QSize(dim, dim))
                    except Exception:
                        pass
            elif kind == 'action':
                act = entry.get('action')
                w = entry.get('widget')
                if not act or not w:
                    continue
                dim = self._compute_icon_dim(w)
                icon = self._tint_icon(path, color, QSize(dim, dim))
                if icon and not icon.isNull():
                    act.setIcon(icon)

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
                with open(qss_path, 'r', encoding='utf-8') as fh:
                    QApplication.instance().setStyleSheet(fh.read())
                    qss_loaded = True
            except Exception:
                qss_loaded = False

        if not qss_loaded:
            if dark:
                dark_qss = '''
                QWidget { background-color: #2b2b2b; color: #e6e6e6; }
                QLineEdit, QComboBox, QScrollArea { background-color: #3c3c3c; }
                QPushButton { background-color: #444444; color: #e6e6e6; border: none; padding: 4px; }
                QPushButton:pressed { background-color: #555555; }
                '''
                QApplication.instance().setStyleSheet(dark_qss)
            else:
                QApplication.instance().setStyleSheet('')

        if hasattr(self, 'theme_button') and getattr(self, '_theme_icon_path', None):
            btn_h = self.theme_button.height() or self.theme_button.sizeHint().height() or 28
            dim = min(24, max(16, btn_h - 10))
            color = '#000000' if not dark else '#FFFFFF'
            icon = self._tint_icon(self._theme_icon_path, color, QSize(dim, dim))
            if icon and not icon.isNull():
                self.theme_button.setIcon(icon)
                self.theme_button.setIconSize(QSize(dim, dim))
                if self.theme_button.text():
                    self.theme_button.setText('')
            else:
                if not self.theme_button.text():
                    self.theme_button.setText('Theme')
                self.theme_button.setIcon(QIcon())

        self._update_all_tinted_icons()

    def reload_files(self):
        print("Reload files")

    def import_files(self):
        print("Import files")

    def add_model(self):
        print("Add new model")

    def view_model(self, model_data: dict):
        print(f"Preview 3D model: {model_data.get('name')} from {model_data.get('folder')}")

    def edit_model(self, model_data: dict):
        print(f"Edit model metadata: {model_data.get('name')} from {model_data.get('folder')}")

    def populate_gallery(self):
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

        self._refresh_gallery()

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
    # set application/window icon and title if a logo exists (support common local names)
    icons_dir = os.path.join(os.path.dirname(__file__), 'assets', 'icons')
    for logo_name in ('logo.svg', 'applogo.svg'):
        logo_path = os.path.join(icons_dir, logo_name)
        if os.path.exists(logo_path):
            app.setWindowIcon(QIcon(logo_path))
            window.setWindowIcon(QIcon(logo_path))
            break
    window.setWindowTitle('zPrint')
    # Run an initial sizing pass after show to pick up platform metrics
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window._resize_top_buttons)
    sys.exit(app.exec())