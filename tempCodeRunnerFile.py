if hasattr(self, 'theme_button') and self._theme_icon_path:
                # lazily compute tinted icons
                if self._theme_icon_white is None:
                    self._theme_icon_white = self._tint_icon(self._theme_icon_path, '#FFFFFF')
                if self._theme_icon_black is None:
                    self._theme_icon_black = self._tint_icon(self._theme_icon_path, '#000000')