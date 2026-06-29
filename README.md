# ExportTools for Fusion 360
ExportTools is a Fusion 360 add-in for exporting visible solid bodies as STL files. It also supports parameter-set exports from YAML: each set updates Fusion parameters, recomputes the design, and exports the resulting body.

## Commands
The add-in adds an `exporter Tools` panel in the Solid workspace.

- **Export all Configs**: exports visible solid root bodies for each Fusion configuration. (only in Fusion full version)
- **Export all Bodies**: exports all visible solid root bodies once.
- **Export Assembly Bodies**: exports all visible solid bodies in the assembly into one selected folder. Component path names are added to filenames to avoid collisions.
- **Export Parameter Sets**: reads a YAML file, applies each parameter set, and exports visible solid root bodies into one selected folder.

## Parameter Set YAML
Example:

```yaml
parameterSets:
  - name: a-b
    parameters:
      text: 'A-B'
      height: 18 mm
      width: 15 mm
      length: 40 mm
      opening: 4.5 mm
```

Rules:

- Parameter names must match Fusion parameter names.
- Text parameter values must be quoted, for example `text: 'A-B'`.
- Numeric values should include units, for example `18 mm`.
- Bare numeric values are assigned using the parameter's existing Fusion unit when possible.
- Exported STL filenames include the body name, Fusion file version, and parameter set name.

See [examples/parameter_sets.yaml](examples/parameter_sets.yaml) for a fuller sample.

## Installation
1. Place this folder in a Fusion 360 add-ins location. (Any folder is working)
2. Open Fusion 360.
3. Go to **Utilities > Add-Ins > Scripts and Add-Ins**.
4. Select **Add-Ins**, add or locate `ExportTools`, and run it.
5. Opene the **Add-Ins** Menu again, active `Run on Start-Up` and make sure `Run` is enabled.


## Notes
- All STL exporter uses high mesh refinement.
- The add-in logs progress to Fusion's Text Commands palette.
