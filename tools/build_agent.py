"""
ORACLE.AI — Build Agent (Phase 2)
Scaffolds projects, installs dependencies, compiles code, runs builds.
Gives ORACLE the ability to CREATE software autonomously.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

# Import shell agent for command execution
sys._path_patched = True
import sys
sys.path.insert(0, str(ROOT / "tools"))
from shell_agent import run_powershell, pip_install, format_result


# ── Project Templates ─────────────────────────────────────────────────────────

TEMPLATES = {
    "python_cli": {
        "description": "Python command-line application",
        "files": {
            "main.py": '#!/usr/bin/env python3\n"""\n{name} — {description}\n"""\n\ndef main():\n    print("Hello from {name}")\n\nif __name__ == "__main__":\n    main()\n',
            "requirements.txt": "# Add dependencies here\n",
            "README.md": "# {name}\n\n{description}\n\n## Setup\n\n```bash\npip install -r requirements.txt\npython main.py\n```\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\ndist/\nbuild/\n*.egg-info/\n"
        }
    },
    "python_flask": {
        "description": "Python Flask web application",
        "files": {
            "app.py": 'from flask import Flask, render_template, jsonify\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return jsonify({{"status": "ok", "app": "{name}"}})\n\nif __name__ == "__main__":\n    app.run(debug=True)\n',
            "requirements.txt": "flask>=3.0.0\npython-dotenv>=1.0.0\n",
            "README.md": "# {name}\n\n{description}\n\n## Run\n\n```bash\npip install -r requirements.txt\npython app.py\n```\n",
            ".env": "FLASK_ENV=development\nSECRET_KEY=change-me\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n"
        }
    },
    "python_desktop": {
        "description": "Python desktop app (tkinter)",
        "files": {
            "main.py": 'import tkinter as tk\nfrom tkinter import ttk, messagebox\n\nclass {classname}(tk.Tk):\n    def __init__(self):\n        super().__init__()\n        self.title("{name}")\n        self.geometry("800x600")\n        self.configure(bg="#1a1a2e")\n        self._build_ui()\n\n    def _build_ui(self):\n        label = tk.Label(\n            self,\n            text="{name}",\n            font=("Helvetica", 24, "bold"),\n            bg="#1a1a2e",\n            fg="#e94560"\n        )\n        label.pack(pady=40)\n\ndef main():\n    app = {classname}()\n    app.mainloop()\n\nif __name__ == "__main__":\n    main()\n',
            "requirements.txt": "# tkinter is built-in — add other deps here\n",
            "README.md": "# {name}\n\n{description}\n\n## Run\n\n```bash\npython main.py\n```\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\ndist/\nbuild/\n"
        }
    },
    "node_api": {
        "description": "Node.js REST API (Express)",
        "files": {
            "index.js": 'const express = require("express");\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.use(express.json());\n\napp.get("/", (req, res) => {{\n    res.json({{ status: "ok", app: "{name}" }});\n}});\n\napp.listen(PORT, () => console.log(`{name} running on port ${{PORT}}`));\n',
            "package.json": '{{\n  "name": "{name_slug}",\n  "version": "1.0.0",\n  "description": "{description}",\n  "main": "index.js",\n  "scripts": {{\n    "start": "node index.js",\n    "dev": "nodemon index.js"\n  }},\n  "dependencies": {{\n    "express": "^4.18.0"\n  }},\n  "devDependencies": {{\n    "nodemon": "^3.0.0"\n  }}\n}}\n',
            "README.md": "# {name}\n\n{description}\n\n## Run\n\n```bash\nnpm install\nnpm start\n```\n",
            ".gitignore": "node_modules/\n.env\ndist/\n",
            ".env": "PORT=3000\n"
        }
    },
    "html_site": {
        "description": "Static HTML/CSS/JS website",
        "files": {
            "index.html": '<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>{name}</title>\n    <link rel="stylesheet" href="style.css">\n</head>\n<body>\n    <div class="container">\n        <h1>{name}</h1>\n        <p>{description}</p>\n    </div>\n    <script src="app.js"></script>\n</body>\n</html>\n',
            "style.css": '* {{ margin: 0; padding: 0; box-sizing: border-box; }}\nbody {{ font-family: "Segoe UI", sans-serif; background: #1a1a2e; color: #eee; }}\n.container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}\nh1 {{ color: #e94560; font-size: 2.5rem; margin-bottom: 1rem; }}\n',
            "app.js": '// {name} — JavaScript\nconsole.log("{name} loaded");\n',
            "README.md": "# {name}\n\n{description}\n\nOpen `index.html` in a browser.\n"
        }
    }
}


def create_project(
    name: str,
    template: str = "python_cli",
    description: str = "",
    location: str = None,
    install_deps: bool = True
) -> str:
    """
    Scaffold a new project from a template.
    
    Args:
        name: Project name
        template: Template key (python_cli, python_flask, python_desktop, node_api, html_site)
        description: Project description
        location: Where to create it (defaults to Desktop)
        install_deps: Auto-install dependencies after scaffolding
    """
    if template not in TEMPLATES:
        return f"Unknown template: {template}. Available: {list(TEMPLATES.keys())}"

    # Resolve location
    if not location:
        location = str(Path.home() / "Desktop")

    project_dir = Path(location) / name.replace(" ", "_")

    if project_dir.exists():
        return f"Directory already exists: {project_dir}"

    project_dir.mkdir(parents=True, exist_ok=True)

    tpl = TEMPLATES[template]
    desc = description or tpl["description"]
    classname = "".join(word.capitalize() for word in name.replace("-", " ").replace("_", " ").split())
    name_slug = name.lower().replace(" ", "-")

    results = [f"Created project: {project_dir}"]

    # Write template files
    for filename, content in tpl["files"].items():
        file_content = content.format(
            name=name,
            name_slug=name_slug,
            description=desc,
            classname=classname
        )
        file_path = project_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_content, encoding="utf-8")
        results.append(f"  Created: {filename}")

    # Initialize git
    git_result = run_powershell("git init", cwd=str(project_dir))
    if git_result["success"]:
        run_powershell('git add -A && git commit -m "Initial scaffold by ORACLE.AI"', cwd=str(project_dir))
        results.append("  Git initialized + initial commit")

    # Install dependencies
    if install_deps:
        req_file = project_dir / "requirements.txt"
        pkg_file = project_dir / "package.json"

        if req_file.exists() and template.startswith("python"):
            results.append("  Installing Python dependencies...")
            install = run_powershell(f"pip install -r requirements.txt", cwd=str(project_dir))
            if install["success"]:
                results.append("  Dependencies installed.")
            else:
                results.append(f"  Dep install warning: {install['stderr'][:200]}")

        if pkg_file.exists():
            results.append("  Installing Node dependencies...")
            install = run_powershell("npm install", cwd=str(project_dir))
            if install["success"]:
                results.append("  npm packages installed.")
            else:
                results.append(f"  npm warning: {install['stderr'][:200]}")

    results.append(f"\nProject ready: {project_dir}")
    return "\n".join(results)


def build_python_exe(project_path: str, entry_file: str = "main.py", name: str = None) -> str:
    """Build a Python project into a Windows .exe using PyInstaller."""
    path = Path(project_path)
    entry = path / entry_file

    if not entry.exists():
        return f"Entry file not found: {entry}"

    exe_name = name or path.name
    install_result = run_powershell("pip install pyinstaller")

    cmd = f"pyinstaller --onefile --name {exe_name} {entry_file}"
    result = run_powershell(cmd, cwd=str(path), timeout=300)

    if result["success"]:
        exe_path = path / "dist" / f"{exe_name}.exe"
        return f"Build complete: {exe_path}"
    return f"Build failed:\n{result['stderr'][:500]}"


def run_project(project_path: str, command: str = None) -> str:
    """Run a project using its default run command or a custom command."""
    path = Path(project_path)

    if not command:
        # Auto-detect run command
        if (path / "main.py").exists():
            command = "python main.py"
        elif (path / "app.py").exists():
            command = "python app.py"
        elif (path / "index.js").exists():
            command = "node index.js"
        elif (path / "package.json").exists():
            command = "npm start"
        else:
            return "Cannot auto-detect run command. Please specify one."

    result = run_powershell(command, cwd=str(path), timeout=30)
    return format_result(result)


def install_playwright() -> str:
    """Install Playwright and download Chromium browser."""
    r1 = run_powershell("pip install playwright", timeout=300)
    r2 = run_powershell("playwright install chromium", timeout=300)
    if r1["success"] and r2["success"]:
        return "Playwright installed with Chromium."
    return f"Playwright install result:\n{format_result(r1)}\n{format_result(r2)}"


def list_templates() -> str:
    """List all available project templates."""
    lines = ["Available Project Templates:", ""]
    for key, tpl in TEMPLATES.items():
        lines.append(f"  {key}: {tpl['description']}")
        lines.append(f"    Files: {', '.join(tpl['files'].keys())}")
        lines.append("")
    return "\n".join(lines)


def scaffold_oracle_plugin(plugin_name: str) -> str:
    """Scaffold a new ORACLE tool/plugin in the tools/ directory."""
    plugin_file = ROOT / "tools" / f"{plugin_name.lower()}.py"

    if plugin_file.exists():
        return f"Plugin already exists: {plugin_file}"

    content = f'''"""
ORACLE.AI — {plugin_name} Plugin
Auto-scaffolded by Build Agent on {datetime.now().strftime("%Y-%m-%d")}
"""

# Add your plugin functions here


def {plugin_name.lower()}_main() -> str:
    """Main entry point for {plugin_name} plugin."""
    return "{plugin_name} plugin ready."
'''

    plugin_file.write_text(content, encoding="utf-8")
    return f"Plugin scaffolded: {plugin_file}"
