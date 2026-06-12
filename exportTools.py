import adsk.core
import adsk.fusion
import os
import re
import traceback

# Fusion 360 keeps Python event handlers alive only while references exist.
handlers = []

CONFIG = {
    "workspaceId": "FusionSolidEnvironment",
    "panelId": "exporter_Tools",
    "panelName": "exporter Tools",
    "resourceFolder": "resources",
    "guiElements": [
        {
            "id": "exportTools_exportAllConfigs",
            "name": "Export all Configs",
            "tooltip": "Export all visible solid root bodies for every configuration as STL.",
            "function": "exportConfigSTL",
        },
        {
            "id": "exportTools_exportAllBodies",
            "name": "Export all Bodies",
            "tooltip": "Export all visible solid bodies in the root component as STL.",
            "function": "exportAllBodies",
        },
        {
            "id": "exportTools_exportAssemblyStructured",
            "name": "Export Assembly Bodies",
            "tooltip": "Export all visible solid bodies in the assembly as STL files in component subfolders.",
            "function": "exportAssemblyStructured",
        },
    ],
}


def log(text):
    """Write text to Fusion's Text Commands palette and stdout as fallback."""
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        palette = ui.palettes.itemById("TextCommands") if ui else None

        if palette:
            if not palette.isVisible:
                palette.isVisible = True
            palette.writeText(str(text) + "\n")
        else:
            print(text)
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
            # Skip invalid/stale body references.
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

    # Fusion commonly separates nested occurrences with '+'. Fall back to the
    # occurrence name when the full path is empty.
    raw_parts = [part for part in str(full_path).split("+") if part.strip()]
    if not raw_parts:
        raw_parts = [getattr(occurrence, "name", "Occurrence")]

    return [sanitize_filename_part(part) for part in raw_parts]


def get_visible_solid_assembly_bodies(design):
    """Return visible solid bodies from root plus every visible occurrence.

    Each item is a tuple: (body_or_proxy, folder_parts). The folder parts are
    used to recreate the assembly structure below the selected export folder.
    """
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
                # Skip invalid/stale body references.
                pass

    return items

def ask_export_folder(ui):
    folder_dlg = ui.createFolderDialog()
    folder_dlg.title = "Select folder to save STL files"
    if folder_dlg.showDialog() != adsk.core.DialogResults.DialogOK:
        log("Export canceled by user.")
        return None
    return folder_dlg.folder


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


# --- Add-in lifecycle ---
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        workspace = ui.workspaces.itemById(CONFIG["workspaceId"])
        if not workspace:
            log(f"❌ Workspace not found: {CONFIG['workspaceId']}")
            return

        cmd_defs = ui.commandDefinitions
        panel = workspace.toolbarPanels.itemById(CONFIG["panelId"])
        if not panel:
            panel = workspace.toolbarPanels.add(CONFIG["panelId"], CONFIG["panelName"])
            #panel.icon(os.path.join(os.path.dirname(__file__), "resources", "icon.svg") )

        # addin_dir = os.path.dirname(os.path.realpath(__file__))
        # resources_dir = os.path.join(addin_dir, CONFIG["resourceFolder"])
        # icon_resource = resources_dir if os.path.isdir(resources_dir) else ""

        for elem in CONFIG["guiElements"]:
            cmd_def = cmd_defs.itemById(elem["id"])
            if not cmd_def:
                cmd_def = cmd_defs.addButtonDefinition(
                    elem["id"],
                    elem["name"],
                    elem["tooltip"],
                    os.path.join(os.path.dirname(__file__), CONFIG["resourceFolder"] ),
                )

            on_command_created = GenericCommandCreatedHandler(elem["function"])
            cmd_def.commandCreated.add(on_command_created)
            handlers.append(on_command_created)

            if not panel.controls.itemById(elem["id"]):
                panel.controls.addCommand(cmd_def)

        log("✅ exportTools add-in initialized.")

    except Exception:
        if ui:
            log("❌ Add-in failed:\n{}".format(traceback.format_exc()))


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        workspace = ui.workspaces.itemById(CONFIG["workspaceId"])
        panel = workspace.toolbarPanels.itemById(CONFIG["panelId"]) if workspace else None

        for elem in CONFIG["guiElements"]:
            if panel:
                ctrl = panel.controls.itemById(elem["id"])
                if ctrl:
                    ctrl.deleteMe()

            cmd_def = ui.commandDefinitions.itemById(elem["id"])
            if cmd_def:
                cmd_def.deleteMe()

        if panel and panel.controls.count == 0:
            panel.deleteMe()

        handlers.clear()
        log("✅ exportTools add-in stopped.")

    except Exception:
        if ui:
            log("❌ Stop failed:\n{}".format(traceback.format_exc()))


# --- Event handlers ---
class GenericCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, function_name):
        super().__init__()
        self.function_name = function_name

    def notify(self, args):
        try:
            cmd = args.command
            on_execute = GenericCommandExecuteHandler(self.function_name)
            cmd.execute.add(on_execute)
            handlers.append(on_execute)
        except Exception:
            log("❌ Command creation failed:\n{}".format(traceback.format_exc()))


class GenericCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, function_name):
        super().__init__()
        self.function_name = function_name

    def notify(self, args):
        try:
            func = globals().get(self.function_name)
            if callable(func):
                func()
            else:
                log(f"❌ Function '{self.function_name}' not found.")
        except Exception:
            log("❌ Command execution failed:\n{}".format(traceback.format_exc()))


# --- Button functions ---
def exportConfigSTL():
    app, ui, design = get_app_ui_design()
    if not design:
        return

    try:
        design_table = design.configurationTopTable
    except RuntimeError as e:
        log("❌ Your account does not allow configurations.")
        return
    
    if not design_table or not design_table.rows or design_table.rows.count == 0:
        log("❌ No design table or configuration rows found.")
        return

    export_folder = ask_export_folder(ui)
    if not export_folder:
        return

    file_version = sanitize_filename_part(get_file_version(app))
    export_mgr = design.exportManager
    exported_count = 0
    failed_count = 0

    for config in design_table.rows:
        config_name = sanitize_filename_part(config.name)

        try:
            config.activate()
        except Exception:
            failed_count += 1
            log(f"❌ Could not activate configuration '{config.name}':\n{traceback.format_exc()}")
            continue

        # Re-query after activation because bodies can change between configurations.
        bodies = get_visible_solid_root_bodies(design)
        if not bodies:
            failed_count += 1
            log(f"⚠️ No visible solid root bodies in configuration '{config.name}'.")
            continue

        for body in bodies:
            try:
                body_name = sanitize_filename_part(body.name)
                filename = f"{body_name}_v{file_version}_{config_name}.stl"
                fullpath = os.path.join(export_folder, filename)
                export_body_as_stl(export_mgr, body, fullpath)
                exported_count += 1
            except Exception:
                failed_count += 1
                body_label = getattr(body, "name", "unknown body")
                log(f"❌ Failed to export '{body_label}' in configuration '{config.name}':\n{traceback.format_exc()}")

    log(
        f"✅ Configuration STL export complete.\n"
        f"Exported: {exported_count}\n"
        f"Failed/skipped: {failed_count}\n"
        f"Folder: {export_folder}"
    )

def exportAllBodies():
    app, ui, design = get_app_ui_design()
    if not design:
        return

    bodies = get_visible_solid_root_bodies(design)
    if not bodies:
        log("❌ No visible solid bodies found in the root component.")
        return

    message = "Visible solid bodies in root component:\n"
    for body in bodies:
        message += f"- {body.name}\n"
    log(message)

    export_folder = ask_export_folder(ui)
    if not export_folder:
        return

    file_version = sanitize_filename_part(get_file_version(app))
    export_mgr = design.exportManager
    exported_count = 0
    failed_count = 0

    for body in bodies:
        try:
            body_name = sanitize_filename_part(body.name)
            filename = f"{body_name}_v{file_version}.stl"
            fullpath = os.path.join(export_folder, filename)
            export_body_as_stl(export_mgr, body, fullpath)
            exported_count += 1
        except Exception:
            failed_count += 1
            body_label = getattr(body, "name", "unknown body")
            log(f"❌ Failed to export '{body_label}':\n{traceback.format_exc()}")

    log(
        f"✅ Body STL export complete.\n"
        f"Exported: {exported_count}\n"
        f"Failed/skipped: {failed_count}\n"
        f"Folder: {export_folder}"
    )

def exportAssemblyStructured():
    app, ui, design = get_app_ui_design()
    if not design:
        return

    body_items = get_visible_solid_assembly_bodies(design)
    if not body_items:
        log("❌ No visible solid bodies found in the assembly.")
        return

    export_folder = ask_export_folder(ui)
    if not export_folder:
        return

    file_version = sanitize_filename_part(get_file_version(app))
    export_mgr = design.exportManager
    exported_count = 0
    failed_count = 0

    log(f"Assembly structured export: found {len(body_items)} visible solid bodies.")

    for body, folder_parts in body_items:
        try:
            body_name = sanitize_filename_part(body.name)
            target_folder = os.path.join(export_folder, *folder_parts)
            os.makedirs(target_folder, exist_ok=True)

            filename = f"{body_name}_v{file_version}.stl"
            fullpath = get_unique_path(os.path.join(target_folder, filename))

            export_body_as_stl(export_mgr, body, fullpath)
            exported_count += 1
        except Exception:
            failed_count += 1
            body_label = getattr(body, "name", "unknown body")
            folder_label = os.path.join(*folder_parts) if folder_parts else "unknown folder"
            log(f"❌ Failed to export '{body_label}' in '{folder_label}':\n{traceback.format_exc()}")

    log(
        f"✅ Assembly structured STL export complete.\n"
        f"Exported: {exported_count}\n"
        f"Failed/skipped: {failed_count}\n"
        f"Folder: {export_folder}"
    )

