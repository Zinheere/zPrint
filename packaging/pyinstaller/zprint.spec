# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.building.build_main import COLLECT
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

PROJECT_ROOT = os.path.abspath(os.getcwd())
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
