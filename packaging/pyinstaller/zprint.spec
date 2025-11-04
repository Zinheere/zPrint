# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.building.build_main import COLLECT
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

PROJECT_ROOT = os.path.abspath(os.getcwd())

_EXCLUDED_DATA = {
    os.path.normcase('config.json'),
    os.path.normcase(os.path.join('testfiles', 'config.json')),
}


def _collect_hidden_imports() -> list:
    hidden = set([
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
    ])
    try:
        hidden.update(collect_submodules('core'))
    except Exception:
        pass
    try:
        hidden.update(collect_submodules('vispy'))
    except Exception:
        pass
    return sorted(hidden)

binaries = []
datas = []
for folder in ('assets', 'ui'):
    src = os.path.join(PROJECT_ROOT, folder)
    if os.path.isdir(src):
        datas.append((src, folder))

readme_src = os.path.join(PROJECT_ROOT, 'README.md')
if os.path.isfile(readme_src):
    datas.append((readme_src, '.'))

try:
    binaries.extend(collect_dynamic_libs('vispy'))
except Exception:
    pass
try:
    datas.extend(collect_data_files('vispy'))
except Exception:
    pass
hiddenimports = _collect_hidden_imports()


a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

def _should_exclude_data(path: str) -> bool:
    try:
        rel = os.path.relpath(path, PROJECT_ROOT)
    except ValueError:
        rel = path
    norm_rel = os.path.normcase(rel)
    if norm_rel in _EXCLUDED_DATA:
        return True
    return False

a.datas = [entry for entry in a.datas if not _should_exclude_data(entry[0])]
a.binaries = [entry for entry in a.binaries if not _should_exclude_data(entry[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='zPrint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(PROJECT_ROOT, 'assets', 'icons', 'zprint.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='zPrint',
)
