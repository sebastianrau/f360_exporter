import importlib
import os
import sys
import traceback

import adsk.core

ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)


def load_addin_module(name):
    module = importlib.import_module(name)
    return importlib.reload(module)


common = load_addin_module("export_tools.common")
config = load_addin_module("export_tools.config")
export_all_bodies = load_addin_module("export_tools.features.export_all_bodies")
export_all_configs = load_addin_module("export_tools.features.export_all_configs")
export_assembly_structured = load_addin_module("export_tools.features.export_assembly_structured")
apply_parameter_set = load_addin_module("export_tools.features.apply_parameter_set")
export_parameter_sets = load_addin_module("export_tools.features.export_parameter_sets")

log = common.log
CONFIG = config.CONFIG


# Fusion 360 keeps Python event handlers alive only while references exist.
handlers = []

COMMANDS = {
    "exportAllBodies": export_all_bodies.exportAllBodies,
    "exportAssemblyStructured": export_assembly_structured.exportAssemblyStructured,
    "exportConfigSTL": export_all_configs.exportConfigSTL,
    "applyParameterSet": apply_parameter_set,
    "exportParameterSets": export_parameter_sets.exportParameterSets,
}


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

        for elem in CONFIG["guiElements"]:
            cmd_def = cmd_defs.itemById(elem["id"])
            if not cmd_def:
                cmd_def = cmd_defs.addButtonDefinition(
                    elem["id"],
                    elem["name"],
                    elem["tooltip"],
                    os.path.join(ADDIN_DIR, CONFIG["resourceFolder"]),
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
            command_spec = COMMANDS.get(self.function_name)
            if hasattr(command_spec, "on_command_created"):
                created_handlers = command_spec.on_command_created(cmd)
                if not created_handlers:
                    return
                if not isinstance(created_handlers, (list, tuple)):
                    created_handlers = [created_handlers]
                for handler in created_handlers:
                    if isinstance(handler, adsk.core.CommandEventHandler):
                        cmd.execute.add(handler)
                    elif isinstance(handler, adsk.core.InputChangedEventHandler):
                        cmd.inputChanged.add(handler)
                    else:
                        continue
                    handlers.append(handler)
                return

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
            func = COMMANDS.get(self.function_name)
            if callable(func):
                func()
            else:
                log(f"❌ Function '{self.function_name}' not found.")
        except Exception:
            log("❌ Command execution failed:\n{}".format(traceback.format_exc()))
