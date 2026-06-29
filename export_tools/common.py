import os
import re
import traceback

import adsk.core
import adsk.fusion


def log(text):
    """Write text to Fusion's Text Commands palette and stdout as fallback."""
    try:
        message = str(text).rstrip("\n")
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        palette = ui.palettes.itemById("TextCommands") if ui else None

        if palette:
            if not palette.isVisible:
                palette.isVisible = True
            for line in message.splitlines() or [""]:
                palette.writeText(line)
        else:
            print(message)
    except Exception:
        print("Logging failed:\n{}".format(traceback.format_exc()))


def sanitize_filename_part(value):
    """Make body/config names safe for Windows/macOS filenames."""
    value = str(value).strip() or "unnamed"
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    value = re.sub(r"\s+", " ", value)
    return value[:120]


def get_app_ui_design():
    app = adsk.core.Application.get()
    ui = app.userInterface if app else None
    design = app.activeProduct if app else None

    if not isinstance(design, adsk.fusion.Design):
        log("❌ No active Fusion 360 design.")
        return app, ui, None

    return app, ui, design


def get_file_version(app):
    try:
        data_file = app.activeDocument.dataFile
        return str(data_file.versionNumber) if data_file else "1"
    except Exception:
        return "1"


def get_visible_solid_root_bodies(design):
    root_comp = design.rootComponent
    if not root_comp:
        return []

    bodies = []
    for body in root_comp.bRepBodies:
        try:
            if body.isSolid and body.isVisible:
                bodies.append(body)
        except Exception:
            pass
    return bodies


def get_unique_path(path):
    """Return a non-existing filepath by appending _2, _3, ... when needed."""
    if not os.path.exists(path):
        return path

    folder, filename = os.path.split(path)
    stem, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(folder, f"{stem}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def get_occurrence_path_parts(occurrence):
    """Build safe folder parts from an occurrence path."""
    try:
        full_path = occurrence.fullPathName
    except Exception:
        full_path = getattr(occurrence, "name", "Occurrence")

    raw_parts = [part for part in str(full_path).split("+") if part.strip()]
    if not raw_parts:
        raw_parts = [getattr(occurrence, "name", "Occurrence")]

    return [sanitize_filename_part(part) for part in raw_parts]


def get_visible_solid_assembly_bodies(design):
    """Return visible solid bodies from root plus every visible occurrence."""
    root_comp = design.rootComponent
    if not root_comp:
        return []

    items = []

    for body in root_comp.bRepBodies:
        try:
            if body.isSolid and body.isVisible:
                items.append((body, ["Root Component"]))
        except Exception:
            pass

    for occurrence in root_comp.allOccurrences:
        try:
            if not occurrence.isVisible:
                continue
        except Exception:
            pass

        folder_parts = get_occurrence_path_parts(occurrence)

        try:
            occurrence_bodies = occurrence.bRepBodies
        except Exception:
            occurrence_bodies = []

        for body in occurrence_bodies:
            try:
                if body.isSolid and body.isVisible:
                    items.append((body, folder_parts))
            except Exception:
                pass

    return items


def ask_export_folder(ui):
    folder_dlg = ui.createFolderDialog()
    folder_dlg.title = "Select folder to save STL files"
    if folder_dlg.showDialog() != adsk.core.DialogResults.DialogOK:
        log("Export canceled by user.")
        return None
    return folder_dlg.folder


def ask_yaml_file(ui):
    file_dlg = ui.createFileDialog()
    file_dlg.title = "Select YAML parameter set file"
    file_dlg.filter = "YAML files (*.yaml;*.yml)"
    if file_dlg.showOpen() != adsk.core.DialogResults.DialogOK:
        log("YAML parameter export canceled by user.")
        return None
    return file_dlg.filename


def create_stl_options(export_mgr, body, fullpath):
    """Create STL options in a way that works across Fusion API versions."""
    try:
        stl_options = export_mgr.createSTLExportOptions(body, fullpath)
    except TypeError:
        stl_options = export_mgr.createSTLExportOptions(body)
        stl_options.filename = fullpath

    stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    return stl_options


def export_body_as_stl(export_mgr, body, fullpath):
    stl_options = create_stl_options(export_mgr, body, fullpath)
    export_mgr.execute(stl_options)
