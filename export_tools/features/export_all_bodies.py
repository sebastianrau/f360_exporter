import os
import traceback

from export_tools.common import (
    ask_export_folder,
    export_body_as_stl,
    get_app_ui_design,
    get_file_version,
    get_visible_solid_root_bodies,
    log,
    sanitize_filename_part,
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
