# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.building.build_main import COLLECT
from PyInstaller.building.datastructures import Tree
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

HERE = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def _tree(src: str, dest: str):
    if not os.path.isdir(src):
        return []
    return [Tree(src, prefix=dest)]


def _collect_data() -> list:
    datas = []
    datas.extend(_tree(os.path.join(PROJECT_ROOT, 'assets'), 'assets'))
    datas.extend(_tree(os.path.join(PROJECT_ROOT, 'ui'), 'ui'))
    return datas


def _collect_hidden_imports() -> list:
    hidden = set(['PySide6.QtSvg', 'PySide6.QtSvgWidgets'])
    try:
        hidden.update(collect_submodules('core'))
    except Exception:
        pass
    return sorted(hidden)


datas = _collect_data()
hiddenimports = _collect_hidden_imports()


a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
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
