# zPrint

> ## Streamlined model viewer &amp; print file organiser

*Work in progress*

**Current:** creating basic structure, mostly setup stuff...

## Release Notes

### 0.30 (2025-11-03)

- Added determinate loading overlays for gallery refreshes and the VisPy preview dialog so the window stays responsive during heavy work.
- Expanded the Edit Model dialog with preview swapping, metadata validation, and full G-code management (add, remove, copy, delete).
- Persisted theme selection and default storage mode immediately on change to keep import defaults in sync across sessions.
- Improved 3MF preview generation by rendering multi-part models directly and falling back to embedded thumbnails when available.

### 0.20 Beta (2025-11-03)

- Replaced the STL preview dialog with a VisPy-powered renderer for smooth, GPU-accelerated orbit and zoom.
- Added 3MF support across gallery thumbnails and the interactive 3D viewer.
- Added configurable import flow with folder creation and config persistence in `%APPDATA%\zPrint`.
- Simplified empty gallery state and ensured document-root defaults target the user Documents directory.
- Introduced PyInstaller/ Inno Setup packaging scripts for portable builds and Windows installers.
- Embedded official logo into executable, installer, and shortcuts.

### 0.10 Beta (initial drop)

- Established gallery UI with search, sort, and material filtering controls.
- Wired theme toggle, loading overlays, and adaptive STL thumbnail rendering.
- Added New Model dialog skeleton and core JSON-loading pipeline.

## Building

### Windows executable and installer

1. Install build dependencies: `pip install -r requirements.txt` (PyInstaller is included).
2. (Optional) Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) if you want an installer; ensure `ISCC.exe` is on your `PATH` or installed in the default location.
3. Run the release script from PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/build_windows_release.ps1`.

The script produces two outputs inside `dist/`:

- `dist/zPrint/` contains the portable PyInstaller bundle.
- `dist/installer/zPrint-Setup.exe` is the Inno Setup installer (skipped when `-SkipInstaller` is passed).

Use `scripts/build_windows_release.ps1 -SkipInstaller` if you only need the standalone folder without an installer.
