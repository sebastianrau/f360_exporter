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


def exportConfigSTL():
    app, ui, design = get_app_ui_design()
    if not design:
        return

    try:
        design_table = design.configurationTopTable
    except RuntimeError:
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
