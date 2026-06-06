"""
Tool definitions for Claude tool-use API.
These are the tools Oracle can call autonomously.
"""

TOOL_DEFINITIONS = [
    {
        "name": "open_app",
        "description": (
            "Launch an approved application on Noah's machine. "
            "Only use for apps in the approved_apps config list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "App key from approved_apps (e.g. 'chrome', 'vscode', 'notepad')",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional command-line arguments (e.g. a URL for chrome)",
                },
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "run_script",
        "description": (
            "Execute an approved PowerShell script. "
            "Only use for scripts in the approved_scripts config list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Script path relative to project root (e.g. 'Scripts/setup_mirrorGPT.ps1')",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional arguments to pass to the script",
                },
            },
            "required": ["script_path"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file. Use to check documents, logs, or context files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path or path relative to project root",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 4000)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write or append content to a file. "
            "Requires explicit confirmation before overwriting existing files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path or path relative to project root",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write",
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "description": "'write' replaces the file; 'append' adds to it (default: append)",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "remember_fact",
        "description": (
            "Store a persistent fact in Oracle's memory database. "
            "Use to save important information Noah shares that should persist across sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category (e.g. 'personal', 'project', 'preference', 'goal')",
                },
                "key": {
                    "type": "string",
                    "description": "Fact identifier",
                },
                "value": {
                    "type": "string",
                    "description": "Fact content",
                },
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "recall_facts",
        "description": "Query Oracle's memory database for stored facts, optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (absolute or relative to project root)",
                },
            },
            "required": ["path"],
        },
    },
]
