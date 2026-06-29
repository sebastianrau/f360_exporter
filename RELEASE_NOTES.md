# Release Notes

## 1.0.0

Initial stable release of ExportTools for Fusion 360.

### Added

- Export visible root bodies as STL files.
- Export visible assembly bodies as STL files into one selected folder.
- Export visible root bodies for every Fusion configuration.
- Export parameter-set variants from a YAML file.
- Apply Fusion parameter values from YAML before each export.
- Support text parameter expressions such as `'A-B'`.
- Support numeric parameter expressions with units such as `18 mm`.
- Preserve existing files by appending `_2`, `_3`, and so on when needed.
- Log export progress to Fusion's Text Commands palette.
- Example cable holder parameter-set YAML.

### Changed

- Refactored the add-in into one entrypoint plus separate feature files.
- Assembly exports now use flat output filenames instead of creating component subfolders.
- Parameter-set exports now write all STL files directly into the selected output folder.

### Notes

- Fusion can cache Python add-in modules during development. Restart Fusion if changes do not appear after stopping and starting the add-in.
- Parameter names in YAML must match Fusion parameter names.
- Text values in YAML should be quoted.
