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
        {
            "id": "exportTools_exportParameterSets",
            "name": "Export Parameter Sets",
            "tooltip": "Read parameter sets from YAML, apply each set, and export visible root bodies as STL.",
            "function": "exportParameterSets",
        },
        {
            "id": "exportTools_applyParameterSet",
            "name": "Apply Parameter Set",
            "tooltip": "Read a YAML file, choose one parameter set, and apply it to the active design.",
            "function": "applyParameterSet",
        },
    ],
}
