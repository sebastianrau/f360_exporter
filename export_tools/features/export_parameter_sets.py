import os
import re
import traceback

from export_tools.common import (
    ask_export_folder,
    ask_yaml_file,
    export_body_as_stl,
    get_app_ui_design,
    get_file_version,
    get_unique_path,
    get_visible_solid_root_bodies,
    log,
    sanitize_filename_part,
)

BARE_NUMBER_RE = re.compile(r"^-?(\d+|\d+\.\d*|\d*\.\d+)(e[-+]?\d+)?$", re.IGNORECASE)
PARAMETER_SET_EXPORT_VERSION = "2026-06-29-flat-export-v3"


def strip_yaml_comment(line):
    """Strip comments outside of simple single/double quoted strings."""
    in_single = False
    in_double = False
    escaped = False

    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            return line[:index]

    return line


def parse_yaml_scalar(value):
    value = strip_yaml_comment(str(value)).strip()
    if not value:
        return ""

    return value


def strip_enclosing_quotes(value):
    text = str(value).strip()
    if (
        (text.startswith("'") and text.endswith("'"))
        or (text.startswith('"') and text.endswith('"'))
    ):
        return text[1:-1]
    return text


def expression_for_parameter(parameter, value):
    expression = str(value).strip()
    if (
        (expression.startswith("'") and expression.endswith("'"))
        or (expression.startswith('"') and expression.endswith('"'))
    ):
        expression = strip_enclosing_quotes(expression)
        return "'{}'".format(expression.replace("'", "\\'"))

    if not BARE_NUMBER_RE.match(expression):
        try:
            current_value = parameter.value
        except Exception:
            current_value = None

        if isinstance(current_value, str):
            return "'{}'".format(expression.replace("'", "\\'"))

        return expression

    try:
        unit = str(parameter.unit).strip()
    except Exception:
        unit = ""

    if unit:
        return f"{expression} {unit}"
    return expression


def parse_yaml_mapping_value(text):
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return parse_yaml_scalar(text)

    result = {}
    inner = text[1:-1].strip()
    if not inner:
        return result

    for part in inner.split(","):
        if ":" not in part:
            raise ValueError(f"Invalid inline YAML mapping entry: {part}")
        key, value = part.split(":", 1)
        result[str(parse_yaml_scalar(key)).strip()] = parse_yaml_scalar(value)

    return result


def parse_simple_yaml_parameter_sets(path):
    """Parse a small YAML subset used for parameter-set exports."""
    with open(path, "r", encoding="utf-8") as yaml_file:
        raw_lines = yaml_file.readlines()

    lines = []
    for raw_line in raw_lines:
        line = strip_yaml_comment(raw_line.rstrip("\n"))
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, line.strip()))

    if not lines:
        raise ValueError("YAML file is empty.")

    sets = []
    current_set = None
    in_sets_block = False
    in_parameter_sets_block = False
    in_parameters_block = False
    pending_set_name = None

    for indent, text in lines:
        if indent == 0:
            in_sets_block = text in ("sets:", "parameter_sets:", "parameterSets:")
            in_parameter_sets_block = text in ("parameter_sets:", "parameterSets:")
            in_parameters_block = False
            pending_set_name = None

            if in_sets_block:
                continue

            if text.endswith(":"):
                current_set = {"name": text[:-1].strip(), "parameters": {}}
                sets.append(current_set)
                continue

            raise ValueError(f"Unsupported top-level YAML entry: {text}")

        if in_parameter_sets_block and text.startswith("- "):
            item_text = text[2:].strip()
            current_set = {"name": "", "parameters": {}}
            sets.append(current_set)
            in_parameters_block = False

            if item_text:
                if ":" not in item_text:
                    raise ValueError(f"Invalid parameter set entry: {text}")
                key, value = item_text.split(":", 1)
                current_set[key.strip()] = parse_yaml_mapping_value(value)
            continue

        if in_sets_block and not in_parameter_sets_block and indent == 2 and text.endswith(":"):
            current_set = {"name": text[:-1].strip(), "parameters": {}}
            sets.append(current_set)
            in_parameters_block = True
            pending_set_name = current_set["name"]
            continue

        if ":" not in text:
            raise ValueError(f"Invalid YAML line: {text}")

        key, value = text.split(":", 1)
        key = key.strip()
        parsed_value = parse_yaml_mapping_value(value)

        if in_sets_block and not in_parameter_sets_block and indent == 2:
            current_set = {"name": key, "parameters": {}}
            sets.append(current_set)
            pending_set_name = key
            if isinstance(parsed_value, dict):
                current_set["parameters"].update(parsed_value)
            continue

        if current_set is None:
            raise ValueError(f"Parameter entry without a set: {text}")

        if key == "name" and not in_parameters_block:
            current_set["name"] = strip_enclosing_quotes(parsed_value)
            continue

        if key in ("parameters", "params"):
            if isinstance(parsed_value, dict):
                current_set["parameters"].update(parsed_value)
            in_parameters_block = True
            continue

        if in_parameter_sets_block and indent == 4 and not in_parameters_block:
            current_set[key] = parsed_value
            continue

        if pending_set_name and indent == 2:
            current_set = {"name": key, "parameters": {}}
            sets.append(current_set)
            pending_set_name = key
            if isinstance(parsed_value, dict):
                current_set["parameters"].update(parsed_value)
            continue

        current_set["parameters"][key] = parsed_value

    normalized_sets = []
    for index, parameter_set in enumerate(sets, start=1):
        name = strip_enclosing_quotes(parameter_set.get("name") or f"set_{index}")
        parameters = parameter_set.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise ValueError(f"Parameter set '{name}' has invalid parameters.")
        if not parameters:
            raise ValueError(f"Parameter set '{name}' does not define any parameters.")
        normalized_sets.append({"name": name, "parameters": parameters})

    if not normalized_sets:
        raise ValueError("No parameter sets found in YAML file.")

    return normalized_sets


def get_parameter_by_name(design, parameter_name):
    try:
        parameter = design.userParameters.itemByName(parameter_name)
        if parameter:
            return parameter
    except Exception:
        pass

    try:
        parameter = design.allParameters.itemByName(parameter_name)
        if parameter:
            return parameter
    except Exception:
        pass

    return None


def apply_parameter_set(design, parameter_set):
    missing = []
    failed = []

    for parameter_name, value in parameter_set["parameters"].items():
        parameter = get_parameter_by_name(design, parameter_name)
        if not parameter:
            missing.append(parameter_name)
            continue

        expression = expression_for_parameter(parameter, value)
        log(f"    Applying parameter: {parameter_name} = {expression}")
        try:
            parameter.expression = expression
        except Exception:
            failed.append(f"{parameter_name}={expression}")

    if missing or failed:
        return False, missing, failed

    try:
        design.computeAll()
    except Exception:
        log(f"⚠️ computeAll failed after applying '{parameter_set['name']}':\n{traceback.format_exc()}")

    return True, missing, failed


def exportParameterSets():
    app, ui, design = get_app_ui_design()
    if not design:
        return

    yaml_path = ask_yaml_file(ui)
    if not yaml_path:
        return

    try:
        parameter_sets = parse_simple_yaml_parameter_sets(yaml_path)
    except Exception:
        log(f"❌ Could not read YAML parameter sets:\n{traceback.format_exc()}")
        return

    export_folder = ask_export_folder(ui)
    if not export_folder:
        return

    file_version = sanitize_filename_part(get_file_version(app))
    export_mgr = design.exportManager
    exported_count = 0
    failed_count = 0
    skipped_sets = 0

    for parameter_set in parameter_sets:
        set_name = sanitize_filename_part(parameter_set["name"])
        log(f"Using Prameter Set {parameter_set['name']}")

        try:
            applied, missing, failed = apply_parameter_set(design, parameter_set)
            if not applied:
                skipped_sets += 1
                failed_count += 1
                messages = []
                if missing:
                    messages.append("missing: " + ", ".join(missing))
                if failed:
                    messages.append("failed: " + ", ".join(failed))
                log(f"❌ Skipping parameter set '{parameter_set['name']}' ({'; '.join(messages)}).")
                continue
        except Exception:
            skipped_sets += 1
            failed_count += 1
            log(f"❌ Could not apply parameter set '{parameter_set['name']}':\n{traceback.format_exc()}")
            continue

        bodies = get_visible_solid_root_bodies(design)
        if not bodies:
            skipped_sets += 1
            failed_count += 1
            log(f"⚠️ No visible solid root bodies after applying '{parameter_set['name']}'.")
            continue

        for body in bodies:
            try:
                body_name = sanitize_filename_part(body.name)
                filename = f"{body_name}_v{file_version}_{set_name}.stl"
                fullpath = get_unique_path(os.path.join(export_folder, filename))
                export_body_as_stl(export_mgr, body, fullpath)
                exported_count += 1
            except Exception:
                failed_count += 1
                body_label = getattr(body, "name", "unknown body")
                log(f"❌ Failed to export '{body_label}' for parameter set '{parameter_set['name']}':\n{traceback.format_exc()}")

    log(
        f"✅ Parameter set STL export complete.\n"
        f"Sets: {len(parameter_sets)}\n"
        f"Skipped sets: {skipped_sets}\n"
        f"Exported: {exported_count}\n"
        f"Failed/skipped: {failed_count}\n"
        f"Folder: {export_folder}"
    )
