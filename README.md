# zPrint

> ### Streamlined print file organiser &amp; model gallery

**Current:** 0.4.2 – *G-code preview & metadata*

## ⬇️ Install ⬇️

### ✅ DOWNLOAD INSTALLER FROM [RELEASES](https://github.com/Zinheere/zPrint/releases/latest)
- Run it to install zPrint with shortcuts and file associations.
- Prefer a portable build? Use the self-contained folder in `dist\zPrint\`.

## Using zPrint

### First Launch

1. Install via `zPrint-Setup.exe` from [releases](https://github.com/Zinheere/zPrint/releases/latest).
2. Start zPrint; the welcome prompts guide you through selecting a storage location and default theme. The app creates a `models.json` library and folders if needed.
3. You can update both choices later from the gear menu in the main window.

### Organising Models

- Click **Import** to add existing STL/3MF models and associated G-code. zPrint creates a folder per model and copies the selected files into the library.
- Use the top search bar and sort/material filters to locate models quickly.
- Mark G-code files as *active* and copy them to removable storage via the Edit Model dialog.

### Editing Metadata & Previews

- Select a card and press **Edit Model** to change name, material, nozzle, and notes. Validation runs inline so you catch issues before saving.
- Use **Regenerate Preview** to rebuild the thumbnail from the source mesh. You can also choose a custom preview image.

### 3D Viewer

- Hit **3D View** on any card to open the VisPy preview. Orbit with left-drag, pan with right-drag, zoom with the wheel.
- Multi-part 3MF files load as a combined mesh; if processing fails, zPrint falls back to embedded thumbnails.

### Managing Files

- Copy, remove, or replace associated G-code directly from the Edit dialog without leaving the app.
- The gallery shows determinate progress overlays during heavy operations so the window stays responsive.

## Release Notes

### 0.4.2 (2025-11-04)

- Added an interactive G-code toolpath preview inside the 3D viewer with improved lighting and shadows for clearer layer inspection.
- Extracted slicer-supplied material, colour, and print time metadata directly from G-code comments, normalising colour labels and trimming print durations to minutes.
- Introduced a storage setting to automatically delete source files after import, persisting the preference in the app configuration.
- Brought the light and dark themes to parity with styled checkbox indicators so toggles remain visible across both modes.

## Building

### Windows executable and installer

1. Install build dependencies: `pip install -r requirements.txt` (PyInstaller is included).
2. (Optional) Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) if you want an installer; ensure `ISCC.exe` is on your `PATH` or installed in the default location.
3. Run the release script from PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/build_windows_release.ps1`.

The script produces two outputs inside `dist/`:

- `dist/zPrint/` contains the portable PyInstaller bundle.
- `dist/installer/zPrint-Setup.exe` is the Inno Setup installer (skipped when `-SkipInstaller` is passed).

Use `scripts/build_windows_release.ps1 -SkipInstaller` if you only need the standalone folder without an installer.
