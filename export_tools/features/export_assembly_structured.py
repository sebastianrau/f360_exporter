import os
import traceback

from export_tools.common import (
    ask_export_folder,
    export_body_as_stl,
    get_app_ui_design,
    get_file_version,
    get_unique_path,
    get_visible_solid_assembly_bodies,
    log,
    sanitize_filename_part,
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
            path_prefix = sanitize_filename_part("_".join(folder_parts)) if folder_parts else "Assembly"
            filename = f"{path_prefix}_{body_name}_v{file_version}.stl"
            fullpath = get_unique_path(os.path.join(export_folder, filename))

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
