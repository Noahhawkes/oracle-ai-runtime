"""
Tool definitions for Claude tool-use API.
These are the tools Oracle can call autonomously.
Phase 2: Added browser, shell, filesystem, build, and scheduler tools.
"""

TOOL_DEFINITIONS = [
    # ── Phase 1 Core Tools ────────────────────────────────────────────────────
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

    # ── Phase 2: Shell Agent ──────────────────────────────────────────────────
    {
        "name": "run_shell",
        "description": (
            "Execute any PowerShell or CMD command on Noah's machine. "
            "Use for installs, file operations, git commands, builds, system info. "
            "Full unrestricted shell access with audit logging."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "PowerShell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "install_package",
        "description": "Install a software package using pip, npm, choco, or winget.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name to install",
                },
                "manager": {
                    "type": "string",
                    "enum": ["pip", "npm", "choco", "winget"],
                    "description": "Package manager to use (default: pip)",
                },
            },
            "required": ["package"],
        },
    },

    # ── Phase 2: Browser Agent ────────────────────────────────────────────────
    {
        "name": "browser_navigate",
        "description": (
            "Open a URL in a browser and return the page text. "
            "Use to read web pages, check sites, gather information from the web."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run browser headlessly (invisible). Default false = visible.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_search",
        "description": "Perform a web search and return results text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "engine": {
                    "type": "string",
                    "enum": ["google", "bing", "duckduckgo"],
                    "description": "Search engine to use (default: google)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "browser_session",
        "description": (
            "Control a persistent browser session for multi-step web interactions. "
            "Actions: start, stop, navigate, get_text, click, type, screenshot, scroll."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "navigate", "get_text", "click", "type", "screenshot", "scroll"],
                    "description": "Browser action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "URL (for navigate action)",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector or text (for click/type actions)",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type (for type action)",
                },
                "headless": {
                    "type": "boolean",
                    "description": "Headless mode for start action",
                },
            },
            "required": ["action"],
        },
    },

    # ── Phase 2: Filesystem Mapper ────────────────────────────────────────────
    {
        "name": "filesystem_scan",
        "description": (
            "Scan and index Noah's file system. Learns what files and folders exist where. "
            "Run once to build the index, then use filesystem_search to find files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific paths to scan (optional — defaults to Desktop, Documents, Downloads, Drive)",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "How deep to recurse (default 4)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "filesystem_search",
        "description": "Search the filesystem index for files matching a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (filename or path fragment)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "filesystem_summary",
        "description": "Get a summary of the current filesystem index (drives, locations, file counts).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ── Phase 2: Build Agent ──────────────────────────────────────────────────
    {
        "name": "create_project",
        "description": (
            "Scaffold a new software project from a template. "
            "Templates: python_cli, python_flask, python_desktop, node_api, html_site. "
            "Creates all files, initializes git, installs dependencies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name",
                },
                "template": {
                    "type": "string",
                    "enum": ["python_cli", "python_flask", "python_desktop", "node_api", "html_site"],
                    "description": "Project template to use",
                },
                "description": {
                    "type": "string",
                    "description": "Project description",
                },
                "location": {
                    "type": "string",
                    "description": "Directory to create the project in (default: Desktop)",
                },
                "install_deps": {
                    "type": "boolean",
                    "description": "Auto-install dependencies (default: true)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "build_exe",
        "description": "Build a Python project into a Windows .exe using PyInstaller.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the Python project",
                },
                "entry_file": {
                    "type": "string",
                    "description": "Main Python file (default: main.py)",
                },
                "name": {
                    "type": "string",
                    "description": "Output exe name (default: project folder name)",
                },
            },
            "required": ["project_path"],
        },
    },

    # ── Daemon ────────────────────────────────────────────────────────────────
    {
        "name": "daemon_cycle",
        "description": (
            "Run one autonomous daemon cycle manually: check source map freshness, "
            "retrieve goal-relevant docs, ingest top findings into memory, and write "
            "an action proposal file. Safe tools only — no file edits, shell commands, "
            "or irreversible actions. Use when Noah says 'wake up', 'run a cycle', "
            "or asks Oracle to scan and propose next steps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ── Source Map (file intelligence) ───────────────────────────────────────
    {
        "name": "source_map_scan",
        "description": (
            "Index Noah's key folders (ORACLE.AI repo, OneDrive docs, business records) "
            "into a searchable cache. Run this once to build the index, or again to refresh it. "
            "After scanning, use source_map_search to find specific files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional custom paths to scan (defaults to all key Noah.AI locations)",
                },
                "include_excerpts": {
                    "type": "boolean",
                    "description": "Read first 500 chars of each file for search context (default true, slower)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "source_map_search",
        "description": (
            "Search the indexed file cache for files matching a query. "
            "Searches by filename, path, and file content excerpts. "
            "Returns file paths you can then read with read_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term — filename fragment, topic, or keyword",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max files to return (default 20)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "source_map_ingest",
        "description": (
            "Read a file and save a summary of it into Oracle's persistent memory, "
            "so it's available in every future session without re-reading the file. "
            "Use after reading an important document to lock its key facts into memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Full path to the file to ingest",
                },
                "summary": {
                    "type": "string",
                    "description": "Your concise summary of what this file contains and why it matters",
                },
                "category": {
                    "type": "string",
                    "description": "Memory category (default: 'source_map'). Use 'compliance', 'project', 'identity', etc. for important docs.",
                },
            },
            "required": ["path", "summary"],
        },
    },

    # ── Computer Operator (SOV1) ──────────────────────────────────────────────
    {
        "name": "computer_operator",
        "description": (
            "Operate Noah's Windows PC directly — look at the screen and control the "
            "mouse and keyboard to accomplish a goal. Use when Noah asks you to open an "
            "app, click something, type in a window, navigate a UI, send a message via "
            "an app, or do anything that requires actually touching the screen. "
            "Pass a plain-English goal; the operator figures out the steps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "What to accomplish on screen, e.g. 'Open Chrome and go to gmail.com'",
                },
            },
            "required": ["goal"],
        },
    },

    # ── Phase 2: Scheduler ────────────────────────────────────────────────────
    {
        "name": "scheduler_control",
        "description": (
            "Control ORACLE's autonomous background scheduler. "
            "Start autonomous mode to run tasks on timers without Noah's input."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "status", "add_task"],
                    "description": "Scheduler action",
                },
                "task_name": {
                    "type": "string",
                    "description": "Task name (for add_task)",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to schedule (for add_task)",
                },
                "interval_minutes": {
                    "type": "integer",
                    "description": "How often to run in minutes (for add_task)",
                },
            },
            "required": ["action"],
        },
    },
]
