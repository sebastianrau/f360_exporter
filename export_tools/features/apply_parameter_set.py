import json
import os
import traceback

import adsk.core

from export_tools.common import get_app_ui_design, log
from export_tools.features.export_parameter_sets import (
    apply_parameter_set,
    parse_simple_yaml_parameter_sets,
)

YAML_PATH_INPUT_ID = "yamlPath"
YAML_BROWSE_INPUT_ID = "browseYaml"
PARAMETER_SET_INPUT_ID = "parameterSet"
STATUS_INPUT_ID = "status"
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".exporttools_cache.json")
CACHE_YAML_PATH_KEY = "applyParameterSetYamlPath"


def unique_choice_names(parameter_sets):
    counts = {}
    for parameter_set in parameter_sets:
        name = parameter_set["name"]
        counts[name] = counts.get(name, 0) + 1

    seen = {}
    choices = []
    for parameter_set in parameter_sets:
        name = parameter_set["name"]
        seen[name] = seen.get(name, 0) + 1
        display_name = name
        if counts[name] > 1:
            display_name = f"{name} [{seen[name]}]"
        choices.append((display_name, parameter_set))

    return choices


def add_status_input(inputs, text):
    try:
        inputs.addTextBoxCommandInput(STATUS_INPUT_ID, "Status", text, 3, True)
    except Exception:
        log(text)


def read_cached_yaml_path():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as cache_file:
            cached_values = json.load(cache_file)
        yaml_path = cached_values.get(CACHE_YAML_PATH_KEY, "")
        if yaml_path and os.path.exists(yaml_path):
            return yaml_path
    except Exception:
        pass
    return ""


def write_cached_yaml_path(yaml_path):
    try:
        cached_values = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as cache_file:
                cached_values = json.load(cache_file)
                if not isinstance(cached_values, dict):
                    cached_values = {}

        cached_values[CACHE_YAML_PATH_KEY] = yaml_path
        with open(CACHE_PATH, "w", encoding="utf-8") as cache_file:
            json.dump(cached_values, cache_file, indent=2, sort_keys=True)
    except Exception:
        log(f"⚠️ Could not cache YAML file path:\n{traceback.format_exc()}")


def ask_yaml_file(ui, current_path=""):
    file_dlg = ui.createFileDialog()
    file_dlg.title = "Select YAML parameter set file"
    file_dlg.filter = "YAML files (*.yaml;*.yml)"

    if current_path:
        try:
            file_dlg.initialDirectory = os.path.dirname(current_path)
        except Exception:
            pass
        try:
            file_dlg.filename = current_path
        except Exception:
            pass

    if file_dlg.showOpen() != adsk.core.DialogResults.DialogOK:
        return None
    return file_dlg.filename


def set_ok_visible(command, is_visible):
    try:
        command.isOKButtonVisible = is_visible
    except Exception:
        pass


def set_status(inputs, text):
    status_input = inputs.itemById(STATUS_INPUT_ID)
    if status_input:
        try:
            status_input.text = text
            return
        except Exception:
            pass
    add_status_input(inputs, text)


def clear_dropdown_items(dropdown):
    try:
        dropdown.listItems.clear()
        return
    except Exception:
        pass

    last_count = None
    while True:
        try:
            current_count = dropdown.listItems.count
        except Exception:
            return

        if current_count == 0 or current_count == last_count:
            return

        last_count = current_count
        try:
            dropdown.listItems.item(current_count - 1).deleteMe()
        except Exception:
            return


def on_command_created(command):
    _app, ui, design = get_app_ui_design()
    inputs = command.commandInputs

    inputs.addBoolValueInput(YAML_BROWSE_INPUT_ID, "Open YAML file", False, "", False)
    try:
        inputs.addTextBoxCommandInput(YAML_PATH_INPUT_ID, "YAML file", "", 2, True)
    except Exception:
        pass

    dropdown = inputs.addDropDownCommandInput(
        PARAMETER_SET_INPUT_ID,
        "Parameter set",
        adsk.core.DropDownStyles.TextListDropDownStyle,
    )

    add_status_input(inputs, "")
    state = ApplyParameterSetDialogState(ui, command)

    if not design:
        state.set_status("No active Fusion 360 design.")
        set_ok_visible(command, False)
        return None

    cached_yaml_path = read_cached_yaml_path()
    if cached_yaml_path:
        state.load_yaml_path(cached_yaml_path, cache=False)
    else:
        state.set_status("Choose a YAML file.")
        set_ok_visible(command, False)

    return [
        ApplyParameterSetInputChangedHandler(state),
        ApplyParameterSetExecuteHandler(state),
    ]


class ApplyParameterSetDialogState:
    def __init__(self, ui, command):
        self.ui = ui
        self.command = command
        self.yaml_path = ""
        self.choices = {}
        self.is_browsing = False

    def input(self, input_id):
        return self.command.commandInputs.itemById(input_id)

    def set_status(self, text):
        set_status(self.command.commandInputs, text)

    def set_yaml_path_text(self, yaml_path):
        yaml_path_input = self.input(YAML_PATH_INPUT_ID)
        if yaml_path_input:
            try:
                yaml_path_input.text = yaml_path
            except Exception:
                pass

    def populate_dropdown(self, parameter_sets):
        dropdown = self.input(PARAMETER_SET_INPUT_ID)
        if not dropdown:
            return

        clear_dropdown_items(dropdown)
        choices = unique_choice_names(parameter_sets)
        self.choices = dict(choices)
        for index, (display_name, _parameter_set) in enumerate(choices):
            dropdown.listItems.add(display_name, index == 0)

    def load_yaml_path(self, yaml_path, cache=True):
        try:
            parameter_sets = parse_simple_yaml_parameter_sets(yaml_path)
        except Exception:
            self.yaml_path = ""
            self.choices = {}
            self.populate_dropdown([])
            self.set_yaml_path_text(yaml_path)
            self.set_status("Could not read YAML parameter sets. See Text Commands for details.")
            set_ok_visible(self.command, False)
            log(f"❌ Could not read YAML parameter sets:\n{traceback.format_exc()}")
            return False

        self.yaml_path = yaml_path
        self.set_yaml_path_text(yaml_path)
        self.populate_dropdown(parameter_sets)
        self.set_status(f"Loaded {len(parameter_sets)} parameter set(s).")
        set_ok_visible(self.command, True)
        if cache:
            write_cached_yaml_path(yaml_path)
        return True

    def browse_yaml_path(self):
        if self.is_browsing:
            return

        self.is_browsing = True
        try:
            yaml_path = ask_yaml_file(self.ui, self.yaml_path)
            if not yaml_path:
                return
            self.load_yaml_path(yaml_path, cache=True)
        finally:
            self.is_browsing = False


class ApplyParameterSetInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input and changed_input.id == YAML_BROWSE_INPUT_ID:
                self.state.browse_yaml_path()
        except Exception:
            log(f"❌ Could not update parameter set dialog:\n{traceback.format_exc()}")


class ApplyParameterSetExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            _app, _ui, design = get_app_ui_design()
            if not design:
                return

            inputs = args.command.commandInputs
            dropdown = inputs.itemById(PARAMETER_SET_INPUT_ID)
            selected_item = dropdown.selectedItem if dropdown else None
            selected_name = selected_item.name if selected_item else None
            parameter_set = self.state.choices.get(selected_name)

            if not parameter_set:
                log("❌ No parameter set selected.")
                return

            log(f"Using Parameter Set {parameter_set['name']}")
            applied, missing, failed = apply_parameter_set(design, parameter_set)
            if not applied:
                messages = []
                if missing:
                    messages.append("missing: " + ", ".join(missing))
                if failed:
                    messages.append("failed: " + ", ".join(failed))
                log(f"❌ Could not apply parameter set '{parameter_set['name']}' ({'; '.join(messages)}).")
                return

            log(f"✅ Applied parameter set '{parameter_set['name']}'.")
        except Exception:
            log(f"❌ Could not apply parameter set:\n{traceback.format_exc()}")
