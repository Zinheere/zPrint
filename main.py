import sys
import os
import json
import re
import shutil
from datetime import datetime
from functools import partial
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QMainWindow,
    QMessageBox,
    QLabel,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
    QWidget,
    QProgressBar,
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap

from core.svg_rendering import tint_icon
from core.stl_preview import render_stl_preview
from ui.new_model_dialog import NewModelDialog
from ui.edit_model_dialog import EditModelDialog
from ui.stl_preview_dialog import StlPreviewDialog

APP_VERSION = "0.20 Beta"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # theme state: False = light, True = dark
        self.app_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self._config_dir = self._determine_config_dir()
        self._config_path = os.path.join(self._config_dir, 'config.json')
        self.config = self._load_config()
        mode_theme = self.config.get('theme', 'light').lower()
        self.dark_theme = mode_theme == 'dark'
        self.models_root = self._resolve_models_root()
        self._icons_dir = os.path.join(self.app_dir, 'assets', 'icons')
        # track widgets/actions that need tinted icons reapplied on theme/resize
        self._icon_targets = []  # entries: {'kind': 'button'|'action', 'widget': QWidget, 'action': QAction|None, 'path': str}
        self.search_box = None
        self.sort_dropdown = None
        self.filter_dropdown = None
        self.loading_overlay = None
        self.loading_label = None
        self.loading_progress = None
        self.load_ui()
        # apply the chosen theme immediately on startup
        self.apply_theme(self.dark_theme)
        # tracked card header labels for dynamic font resizing
        self.card_headers = []
        self.card_subtexts = []
        self.cards = []
        self._models = []
        self._visible_models = []
        self._preview_cache = {}
        self._thumbnail_sources = {}
        self._search_term = ''
        self._current_material_filter = 'All Materials'
        self._current_sort_index = 0
        self.populate_gallery()

    def load_ui(self):
        ui_path = os.path.join(self.app_dir, 'ui', 'forms', 'main_window.ui')
        ui_file = QFile(ui_path)
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
        from PySide6.QtWidgets import QLineEdit as _QLE
        search = self.findChild(_QLE, 'searchBox') or (self.ui and self.ui.findChild(_QLE, 'searchBox'))
        if search is not None:
            search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            action = search.addAction(QIcon(), _QLE.LeadingPosition)
            self._register_icon(search, ('search.svg', 'magnify.svg', 'magnifier.svg'), action)
            search.textChanged.connect(self._on_search_changed)
            self.search_box = search
            self.top_bar_inputs.append(search)
            # capture initial search text for filtering
            self._search_term = search.text().strip()
        else:
            fallback = self.findChild(QLabel, 'searchBox') or (self.ui and self.ui.findChild(QLabel, 'searchBox'))
            if fallback is not None:
                fallback.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.top_bar_inputs.append(fallback)

        from PySide6.QtWidgets import QComboBox
        for name in ('sortDropdown', 'filterDropdown'):
            dd = self.findChild(QComboBox, name) or (self.ui and self.ui.findChild(QComboBox, name))
            if dd:
                try:
                    dd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                except Exception:
                    pass
                if name == 'sortDropdown':
                    self.sort_dropdown = dd
                    self._current_sort_index = dd.currentIndex()
                    dd.currentIndexChanged.connect(self._on_sort_changed)
                elif name == 'filterDropdown':
                    self.filter_dropdown = dd
                    self._current_material_filter = dd.currentText()
                    dd.currentIndexChanged.connect(self._on_filter_changed)
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

        self._create_loading_overlay()

    def resizeEvent(self, event):
        # Update button sizes whenever the main window resizes so they scale with the window
        try:
            self._resize_top_buttons()
        except Exception:
            pass
        try:
            self._update_loading_overlay_geometry()
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
            return tint_icon(path, hex_color, size)
        except Exception:
            return QIcon()

    def _determine_config_dir(self) -> str:
        if getattr(sys, 'frozen', False):
            base = os.getenv('APPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
            path = os.path.join(base, 'zPrint')
        else:
            path = self.app_dir
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return path

    def _default_models_directory(self) -> str:
        docs = os.path.join(os.path.expanduser('~'), 'Documents')
        return os.path.abspath(os.path.join(docs, 'zPrint'))

    def _load_config(self) -> dict:
        if not getattr(self, '_config_path', None):
            self._config_path = os.path.join(self._determine_config_dir(), 'config.json')
        defaults = {
            'mode': 'local',
            'local_path': self._default_models_directory(),
            'microsd_path': '',
            'theme': 'light'
        }
        data = {}
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh) or {}
            except Exception:
                data = {}
        else:
            legacy_path = os.path.join(self.app_dir, 'testfiles', 'config.json')
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, 'r', encoding='utf-8') as fh:
                        data = json.load(fh) or {}
                except Exception:
                    data = {}
        config = defaults.copy()
        config.update(data)
        if not config.get('local_path'):
            config['local_path'] = self._default_models_directory()
        if 'microsd_path' not in config:
            config['microsd_path'] = ''
        for key in ('local_path', 'microsd_path'):
            value = config.get(key)
            if value:
                config[key] = os.path.abspath(os.path.expanduser(os.path.expandvars(str(value))))
        if not os.path.exists(self._config_path):
            try:
                os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
                with open(self._config_path, 'w', encoding='utf-8') as fh:
                    json.dump(config, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return config

    def _save_config(self) -> None:
        if not getattr(self, '_config_path', None):
            self._config_path = os.path.join(self._determine_config_dir(), 'config.json')
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as fh:
                json.dump(self.config, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _resolve_models_root(self) -> str:
        mode = (self.config.get('mode') or 'local').lower()
        path = None
        if mode == 'microsd':
            path = self.config.get('microsd_path') or os.path.abspath(os.path.sep)
        else:
            path = self.config.get('local_path') or self._default_models_directory()
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        if not os.path.isdir(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception:
                pass
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
            materials = []
            display_time = ''
            for g in gcodes:
                material = g.get('material')
                if material:
                    materials.append(str(material))
                time_text = g.get('print_time')
                if time_text and not display_time:
                    display_time = str(time_text)
                colour = g.get('colour') or g.get('color')
            if not display_time:
                display_time = str(meta.get('print_time', '')) if meta.get('print_time') is not None else ''
            materials = [m for m in materials if m]
            last_modified_dt = self._parse_iso_datetime(meta.get('last_modified'))
            time_created_dt = self._parse_iso_datetime(meta.get('time_created'))
            print_minutes = self._parse_print_time_to_minutes(display_time)
            model_file = meta.get('model_file') or meta.get('stl_file')
            search_terms = [model_name, entry, model_file, display_time]
            for g in gcodes:
                search_terms.append(g.get('file'))
                search_terms.append(g.get('material'))
                search_terms.append(g.get('colour') or g.get('color'))
            search_blob = ' '.join(str(term) for term in search_terms if term).lower()
            models.append({
                'name': model_name,
                'folder': folder_path,
                'preview_path': preview_path,
                'gcodes': gcodes,
                'print_time': display_time,
                'metadata': meta,
                'materials': sorted(set(materials)),
                'last_modified_dt': last_modified_dt,
                'time_created_dt': time_created_dt,
                'print_time_minutes': print_minutes,
                'search_blob': search_blob,
                'stl_file': meta.get('stl_file') or model_file,
                'model_file': model_file,
            })
        return models

    def _parse_iso_datetime(self, value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            try:
                if text.endswith('Z'):
                    return datetime.fromisoformat(text.replace('Z', '+00:00'))
            except Exception:
                pass
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
                try:
                    return datetime.strptime(text, fmt)
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _parse_print_time_to_minutes(self, value) -> int | None:
        if not value:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        total = 0
        matches = re.findall(r'(\d+)\s*([hm])', text)
        for amount, unit in matches:
            try:
                qty = int(amount)
            except Exception:
                continue
            if unit == 'h':
                total += qty * 60
            elif unit == 'm':
                total += qty
        if total:
            return total
        digits = re.findall(r'(\d+)', text)
        if digits:
            try:
                return int(digits[0])
            except Exception:
                return None
        return None

    def _prepare_gallery_layout(self) -> bool:
        container = getattr(self, 'gallery_container', None)
        layout = getattr(self, 'gallery_layout', None)
        if container is not None and layout is not None:
            return True

        container = self.findChild(QWidget, 'scrollAreaWidgetContents')
        if container is None and self.ui is not None:
            container = self.ui.findChild(QWidget, 'scrollAreaWidgetContents')
        if container is None:
            return False

        layout = container.layout()
        if layout is None:
            return False

        self.gallery_container = container
        self.gallery_layout = layout
        try:
            self.gallery_layout.setHorizontalSpacing(8)
            self.gallery_layout.setVerticalSpacing(8)
            self.gallery_layout.setContentsMargins(6, 6, 6, 6)
        except Exception:
            pass
        return True

    def _clear_gallery(self):
        # Remove previous card widgets and associated icon registrations
        if hasattr(self, 'cards') and self.cards:
            for card in self.cards:
                for btn in card.findChildren(QPushButton):
                    self._icon_targets = [t for t in self._icon_targets if t.get('widget') is not btn]
                for lbl in card.findChildren(QLabel):
                    if lbl in self._thumbnail_sources:
                        lbl.removeEventFilter(self)
                        self._thumbnail_sources.pop(lbl, None)
                card.deleteLater()
        self.cards = []
        self.card_headers = []
        self.card_subtexts = []
        self._visible_models = []
        self._thumbnail_sources = {}
        if hasattr(self, 'gallery_layout') and self.gallery_layout is not None:
            while self.gallery_layout.count():
                item = self.gallery_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _refresh_gallery(self, models: list[dict] | None = None):
        models = list(models) if models is not None else list(self._models)
        self._clear_gallery()
        if not getattr(self, 'gallery_layout', None):
            return

        if not models:
            placeholder = QLabel('')
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setProperty('emptyState', True)
            placeholder.setMinimumSize(200, 200)
            placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.cards = [placeholder]
            self.gallery_layout.addWidget(placeholder, 0, 0)
            self._visible_models = []
            self.relayout_gallery()
            try:
                self._update_all_tinted_icons()
            except Exception:
                pass
            return

        visible = []
        theme_key = 'dark' if getattr(self, 'dark_theme', False) else 'light'
        for model in models:
            card = QWidget()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(5, 5, 5, 5)

            thumbnail = QLabel()
            thumbnail.setAlignment(Qt.AlignCenter)
            thumbnail.setProperty('thumbnail', True)
            thumbnail.setScaledContents(False)
            thumbnail.setMinimumSize(160, 120)
            thumbnail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            thumbnail_pixmap = None
            preview_path = model.get('preview_path')
            if preview_path:
                pix = QPixmap(preview_path)
                if pix and not pix.isNull():
                    thumbnail_pixmap = pix

            if thumbnail_pixmap is None:
                stl_name = model.get('model_file') or model.get('stl_file')
                folder = model.get('folder')
                if folder and stl_name:
                    stl_path = os.path.join(folder, stl_name)
                    if os.path.exists(stl_path):
                        cache_key = (os.path.abspath(stl_path), theme_key)
                        cached = self._preview_cache.get(cache_key)
                        if cached is not None and not cached.isNull():
                            thumbnail_pixmap = cached
                        else:
                            generated = render_stl_preview(stl_path, QSize(720, 720), dark_theme=(theme_key == 'dark'))
                            if generated and not generated.isNull():
                                thumbnail_pixmap = generated
                                self._preview_cache[cache_key] = generated

            if thumbnail_pixmap and not thumbnail_pixmap.isNull():
                if thumbnail not in self._thumbnail_sources:
                    thumbnail.installEventFilter(self)
                self._thumbnail_sources[thumbnail] = thumbnail_pixmap
                thumbnail.setPixmap(thumbnail_pixmap)
                thumbnail.setAlignment(Qt.AlignCenter)
                self._apply_thumbnail_pixmap(thumbnail)
            else:
                thumbnail.setText('No Preview')
                if thumbnail in self._thumbnail_sources:
                    thumbnail.removeEventFilter(self)
                    self._thumbnail_sources.pop(thumbnail, None)
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
            btn_3d.setIconSize(QSize(18, 18))
            btn_edit = QPushButton('Edit')
            self._register_icon(btn_edit, ('editmodel.svg', 'editbutton.svg'))
            btn_edit.clicked.connect(partial(self.edit_model, model))
            btn_edit.setIconSize(QSize(18, 18))
            btn_layout.addWidget(btn_3d)
            btn_layout.addWidget(btn_edit)
            layout.addLayout(btn_layout)

            card.setProperty('card', True)
            self.cards.append(card)
            visible.append(model)

        self._visible_models = visible

        self.relayout_gallery()
        try:
            self._update_all_tinted_icons()
        except Exception:
            pass

    def _apply_thumbnail_pixmap(self, label: QLabel) -> None:
        pixmap = self._thumbnail_sources.get(label)
        if not pixmap or pixmap.isNull():
            return
        size = label.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = pixmap.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if scaled.width() > size.width() or scaled.height() > size.height():
            crop_x = max(0, (scaled.width() - size.width()) // 2)
            crop_y = max(0, (scaled.height() - size.height()) // 2)
            scaled = scaled.copy(crop_x, crop_y, min(size.width(), scaled.width()), min(size.height(), scaled.height()))
        label.setPixmap(scaled)
        label.setAlignment(Qt.AlignCenter)

    def _populate_material_filters(self, models: list[dict]):
        if not self.filter_dropdown:
            return
        materials = sorted({mat for model in models for mat in model.get('materials', []) if mat})
        options = ['All Materials'] + materials
        current = self._current_material_filter or 'All Materials'
        try:
            self.filter_dropdown.blockSignals(True)
        except Exception:
            pass
        self.filter_dropdown.clear()
        for option in options:
            self.filter_dropdown.addItem(option)
        if current in options:
            index = options.index(current)
        else:
            index = 0
            current = 'All Materials'
        self.filter_dropdown.setCurrentIndex(index)
        try:
            self.filter_dropdown.blockSignals(False)
        except Exception:
            pass
        self._current_material_filter = current

    def _apply_model_filters(self):
        if not self._models:
            self._refresh_gallery([])
            return
        filtered = list(self._models)
        term = (self._search_term or '').strip().lower()
        if term:
            filtered = [
                model for model in filtered
                if term in (model.get('name', '').lower())
                or term in (model.get('search_blob', ''))
            ]
        material = (self._current_material_filter or '').strip()
        if material and material.lower() != 'all materials':
            filtered = [model for model in filtered if material in model.get('materials', [])]
        sorted_models = self._sort_models(filtered)
        self._refresh_gallery(sorted_models)

    def _sort_models(self, models: list[dict]) -> list[dict]:
        index = self._current_sort_index or 0
        reverse = False

        def _dt_key(value):
            dt = value if isinstance(value, datetime) else None
            if dt is None:
                return float('-inf')
            try:
                return float(dt.timestamp())
            except Exception:
                try:
                    return float(datetime.fromisoformat(str(value)).timestamp())
                except Exception:
                    return float('-inf')

        if index == 0:
            key = lambda m: _dt_key(m.get('last_modified_dt'))
            reverse = True
        elif index == 1:
            key = lambda m: _dt_key(m.get('time_created_dt'))
            reverse = True
        elif index == 2:
            key = lambda m: m.get('name', '').lower()
        elif index == 3:
            key = lambda m: m.get('name', '').lower()
            reverse = True
        elif index == 4:
            key = lambda m: m.get('print_time_minutes') if m.get('print_time_minutes') is not None else float('inf')
        else:
            key = lambda m: m.get('name', '').lower()

        try:
            return sorted(models, key=key, reverse=reverse)
        except Exception:
            return list(models)

    def _on_search_changed(self, text: str):
        self._search_term = text or ''
        self._apply_model_filters()

    def _on_sort_changed(self, value):
        try:
            index = int(value)
        except Exception:
            index = self.sort_dropdown.currentIndex() if self.sort_dropdown else 0
        self._current_sort_index = index
        self._apply_model_filters()

    def _on_filter_changed(self, value):
        if isinstance(value, str):
            selected = value
        elif self.filter_dropdown:
            selected = self.filter_dropdown.currentText()
        else:
            selected = 'All Materials'
        self._current_material_filter = selected or 'All Materials'
        self._apply_model_filters()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and obj in self._thumbnail_sources:
            self._apply_thumbnail_pixmap(obj)  # type: ignore[arg-type]
        return super().eventFilter(obj, event)

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

        theme_icon_candidates = ('lightmode.svg', 'sun.svg', 'toggletheme.svg') if dark else ('darkmode.svg', 'moon.svg', 'toggletheme.svg')
        theme_icon_path = self._resolve_icon_path(theme_icon_candidates)
        if not theme_icon_path:
            theme_icon_path = getattr(self, '_theme_icon_path', None)
        else:
            self._theme_icon_path = theme_icon_path

        if hasattr(self, 'theme_button') and theme_icon_path:
            btn_h = self.theme_button.height() or self.theme_button.sizeHint().height() or 28
            dim = min(24, max(16, btn_h - 10))
            color = '#000000' if not dark else '#FFFFFF'
            icon = self._tint_icon(theme_icon_path, color, QSize(dim, dim))
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

    def _load_ui_widget(self, relative_path: str, parent=None):
        path = os.path.join(self.app_dir, relative_path)
        if not os.path.exists(path):
            return None
        ui_file = QFile(path)
        if not ui_file.open(QFile.ReadOnly):
            return None
        loader = QUiLoader()
        try:
            widget = loader.load(ui_file, parent)
        except Exception:
            widget = None
        finally:
            ui_file.close()
        return widget

    def _create_loading_overlay(self):
        central = self.centralWidget()
        if central is None:
            return
        if self.loading_overlay is not None and self.loading_overlay.parent() is central:
            self._update_loading_overlay_geometry()
            return

        overlay = QWidget(central)
        overlay.setObjectName('loadingOverlay')
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        overlay.setStyleSheet('background-color: rgba(12, 16, 24, 210);')
        overlay.hide()

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content = self._load_ui_widget(os.path.join('ui', 'forms', 'loading_screen.ui'), overlay)
        self.loading_label = None
        self.loading_progress = None

        if content is not None:
            layout.addWidget(content)
            self.loading_label = content.findChild(QLabel, 'loadingLabel')
            self.loading_progress = content.findChild(QProgressBar, 'loadingProgress')
            if self.loading_label is None:
                self.loading_label = content.findChild(QLabel)
            if self.loading_progress is None:
                self.loading_progress = content.findChild(QProgressBar)
        else:
            fallback = QWidget(overlay)
            fallback_layout = QVBoxLayout(fallback)
            fallback_layout.setContentsMargins(48, 48, 48, 48)
            fallback_layout.setSpacing(12)
            fallback_layout.setAlignment(Qt.AlignCenter)

            message = QLabel('Loading…', fallback)
            message.setAlignment(Qt.AlignCenter)
            message.setStyleSheet('color: #FFFFFF; font-size: 18px; font-weight: 600;')

            progress = QProgressBar(fallback)
            progress.setRange(0, 0)
            progress.setTextVisible(False)
            progress.setFixedWidth(240)
            progress.setStyleSheet(
                'QProgressBar {border: 1px solid rgba(255,255,255,90); border-radius: 10px; '
                'background: rgba(255,255,255,28); } '
                'QProgressBar::chunk { background: rgba(255,255,255,190); border-radius: 10px; }'
            )

            fallback_layout.addWidget(message)
            fallback_layout.addSpacing(6)
            fallback_layout.addWidget(progress, alignment=Qt.AlignCenter)
            layout.addWidget(fallback)

            self.loading_label = message
            self.loading_progress = progress

        self.loading_overlay = overlay
        self._update_loading_overlay_geometry()
        overlay.raise_()

    def _update_loading_overlay_geometry(self):
        if self.loading_overlay is None:
            return
        central = self.centralWidget()
        if central is None:
            return
        self.loading_overlay.setGeometry(central.rect())

    def _show_loading(self, message: str = 'Loading…'):  # pragma: no cover - UI behaviour
        self._create_loading_overlay()
        if self.loading_overlay is None:
            return
        if self.loading_label is not None:
            self.loading_label.setText(message)
        self._update_loading_overlay_geometry()
        self.loading_overlay.raise_()
        self.loading_overlay.show()
        QApplication.processEvents()

    def _hide_loading(self):  # pragma: no cover - UI behaviour
        if self.loading_overlay is not None:
            self.loading_overlay.hide()

    def reload_files(self):
        self._show_loading('Refreshing models…')
        QTimer.singleShot(0, self._reload_files_async)

    def _reload_files_async(self):
        try:
            if not self._prepare_gallery_layout():
                return
            self._models = self._load_models_data()
            self._populate_material_filters(self._models)
            self._apply_model_filters()
        finally:
            self._hide_loading()

    def _pick_existing_models_folder(self, start_dir: str) -> str | None:
        dialog = QFileDialog(self, 'Select Models Folder')
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        directory = start_dir if os.path.isdir(start_dir) else os.path.expanduser('~')
        dialog.setDirectory(directory)
        if dialog.exec() != QFileDialog.Accepted:
            return None
        selected = dialog.selectedFiles()
        if not selected:
            return None
        chosen = os.path.abspath(selected[0])
        if not os.path.isdir(chosen):
            return None
        return chosen

    def _create_new_models_folder(self, start_dir: str) -> str | None:
        base_dir = QFileDialog.getExistingDirectory(
            self,
            'Choose Parent Directory',
            start_dir if os.path.isdir(start_dir) else os.path.expanduser('~')
        )
        if not base_dir:
            return None
        name, ok = QInputDialog.getText(self, 'Create Models Folder', 'Folder name:', text='zPrint Models')
        if not ok:
            return None
        name = name.strip()
        if not name:
            QMessageBox.warning(self, 'Create Models Folder', 'Folder name cannot be empty.')
            return None
        new_path = os.path.abspath(os.path.join(base_dir, name))
        try:
            os.makedirs(new_path, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(self, 'Create Models Folder', f'Unable to create folder:\n{exc}')
            return None
        self._initialize_models_folder(new_path)
        return new_path

    def _initialize_models_folder(self, folder_path: str) -> None:
        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception:
            return
        stub_path = os.path.join(folder_path, 'config.json')
        if not os.path.exists(stub_path):
            payload = {
                'name': os.path.basename(os.path.abspath(folder_path)) or 'models',
                'created': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                'models': []
            }
            try:
                with open(stub_path, 'w', encoding='utf-8') as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def import_files(self):
        start_mode = (self.config.get('mode') or 'local').lower()
        if start_mode == 'microsd':
            default_dir = self.config.get('microsd_path') or os.path.abspath(os.path.sep)
        else:
            default_dir = self.config.get('local_path') or self._default_models_directory()
        default_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(default_dir)))

        chooser = QMessageBox(self)
        chooser.setIcon(QMessageBox.Question)
        chooser.setWindowTitle('Import Models')
        chooser.setText('How would you like to set up your models folder?')
        existing_btn = chooser.addButton('Select Existing Folder', QMessageBox.AcceptRole)
        create_btn = chooser.addButton('Create New Folder', QMessageBox.ActionRole)
        cancel_btn = chooser.addButton(QMessageBox.Cancel)
        chooser.exec()
        clicked = chooser.clickedButton()
        if clicked is None or clicked is cancel_btn:
            return
        if clicked is create_btn:
            chosen = self._create_new_models_folder(default_dir)
        else:
            chosen = self._pick_existing_models_folder(default_dir)
        if not chosen:
            return

        chosen = os.path.abspath(os.path.expandvars(os.path.expanduser(chosen)))
        if start_mode == 'microsd':
            self.config['microsd_path'] = chosen
        else:
            self.config['local_path'] = chosen
        self._save_config()
        self.models_root = self._resolve_models_root()
        self.reload_files()

    def add_model(self):
        try:
            dialog = NewModelDialog(self.app_dir, self.config, getattr(self, 'dark_theme', False), self)
        except Exception as exc:
            QMessageBox.critical(self, 'New Model', f'Unable to open dialog:\n{exc}')
            return

        if dialog.exec() != QDialog.Accepted:
            return

        result = getattr(dialog, 'result_data', {}) or {}
        location = (result.get('location') or '').lower()
        base_path = result.get('base_path')
        if base_path:
            if location == 'local':
                self.config['local_path'] = base_path
            elif location == 'microsd':
                self.config['microsd_path'] = base_path
        self.models_root = self._resolve_models_root()
        self.reload_files()

    def view_model(self, model_data: dict):
        if not model_data:
            return

        try:
            dialog = StlPreviewDialog(
                model_data,
                dark_theme=getattr(self, 'dark_theme', False),
                parent=self,
            )
        except Exception as exc:
            QMessageBox.critical(self, '3D Preview', f'Unable to open preview:\n{exc}')
            return

        dialog.exec()

    def edit_model(self, model_data: dict):
        if not model_data:
            return

        try:
            dialog = EditModelDialog(model_data, self)
        except Exception as exc:
            QMessageBox.critical(self, 'Edit Model', f'Unable to open editor:\n{exc}')
            return

        if dialog.exec() != QDialog.Accepted:
            return

        folder = model_data.get('folder')
        if dialog.delete_requested:
            if not folder or not os.path.isdir(folder):
                QMessageBox.critical(self, 'Delete Model', 'Model folder could not be located on disk.')
                return
            try:
                shutil.rmtree(folder)
            except Exception as exc:
                QMessageBox.critical(self, 'Delete Model', f'Unable to delete model folder:\n{exc}')
                return
            if hasattr(self, '_preview_cache') and self._preview_cache:
                folder_abs = os.path.abspath(folder)
                stale_keys = [
                    key for key in self._preview_cache
                    if isinstance(key, tuple) and key and isinstance(key[0], str) and key[0].startswith(folder_abs)
                ]
                for key in stale_keys:
                    self._preview_cache.pop(key, None)
            self.reload_files()
            return

        updated = getattr(dialog, 'updated_metadata', None)
        if not updated:
            return

        if not folder:
            QMessageBox.critical(self, 'Save Changes', 'Model folder is unknown; cannot write metadata.')
            return

        preview_changed = getattr(dialog, 'preview_changed', False)
        new_preview_source = getattr(dialog, 'new_preview_source_path', None)
        new_preview_name = getattr(dialog, 'new_preview_filename', '') or ''
        original_preview_name = getattr(dialog, 'original_preview_name', '') or ''

        if preview_changed:
            if new_preview_source and new_preview_name:
                dest_path = os.path.join(folder, new_preview_name)
                try:
                    if os.path.abspath(new_preview_source) != os.path.abspath(dest_path):
                        shutil.copy2(new_preview_source, dest_path)
                except Exception as exc:
                    QMessageBox.critical(self, 'Save Changes', f'Unable to copy preview image:\n{exc}')
                    return
                if original_preview_name and original_preview_name != new_preview_name:
                    old_path = os.path.join(folder, original_preview_name)
                    if os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
            else:
                if original_preview_name:
                    old_path = os.path.join(folder, original_preview_name)
                    if os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass

        meta_path = os.path.join(folder, 'model.json')
        try:
            with open(meta_path, 'w', encoding='utf-8') as fh:
                json.dump(updated, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            QMessageBox.critical(self, 'Save Changes', f'Unable to write model metadata:\n{exc}')
            return

        self.reload_files()

    def populate_gallery(self):
        self._show_loading('Loading models…')
        QTimer.singleShot(0, self._populate_gallery_async)

    def _populate_gallery_async(self):
        try:
            if not self._prepare_gallery_layout():
                return
            self._models = self._load_models_data()
            self._populate_material_filters(self._models)
            self._apply_model_filters()
        finally:
            self._hide_loading()

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
    app.setApplicationName('zPrint')
    app.setApplicationVersion(APP_VERSION)
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
    window.setWindowTitle(f'zPrint {APP_VERSION}')
    # Run an initial sizing pass after show to pick up platform metrics
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window._resize_top_buttons)
    sys.exit(app.exec())