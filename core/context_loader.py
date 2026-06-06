import json
from pathlib import Path
from root import ROOT
IDENTITY_ANCHOR = ROOT / "Users" / "Noah.Self" / "Noah.Self Upload Repository" / "Noah.Identity.Anchor.json"
CONTEXT_DOCS = ROOT / "Users" / "Noah.Self" / "Noah.Self Upload Repository"

MAX_DOC_CHARS = 4000  # per document, to stay within context limits


def load_identity():
    if not IDENTITY_ANCHOR.exists():
        return {}
    with open(IDENTITY_ANCHOR, encoding="utf-8") as f:
        return json.load(f)


def load_docx_text(path):
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[Could not read {path.name}: {e}]"


def load_txt_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[Could not read {path.name}: {e}]"


# Priority docs to load at startup — ordered by relevance
PRIORITY_DOCS = [
    "Noah_Hawkes_Complete_Profile.docx",
    "Noah_Hawkes_Narrative_Profile.docx",
    "Updated_Noah_Personal_Mind_Journal.docx",
    "Updated_Noah_Business_Financial_Journal.docx",
]


def build_system_prompt():
    identity = load_identity()

    sections = []

    # Identity anchor
    if identity:
        sections.append(f"""IDENTITY ANCHOR
Name: {identity.get('name', 'Noah')}
Purpose: {identity.get('purpose', '')}
Vision: {identity.get('vision', '')}
Core Values: {', '.join(identity.get('core_values', []))}
Echo Constructs: {', '.join(identity.get('echo_constructs', []))}""")

    # Priority context docs
    loaded = []
    for doc_name in PRIORITY_DOCS:
        doc_path = CONTEXT_DOCS / doc_name
        if doc_path.exists():
            text = load_docx_text(doc_path)
            truncated = text[:MAX_DOC_CHARS]
            if len(text) > MAX_DOC_CHARS:
                truncated += "\n[...truncated]"
            loaded.append(f"--- {doc_name} ---\n{truncated}")

    if loaded:
        sections.append("CONTEXT DOCUMENTS\n" + "\n\n".join(loaded))

    base = """You are ORACLE.AI — Noah Hawkes' personal AI operator. Not a chatbot. An operator.

You have full context on Noah: identity, projects, finances, creative work, relationships, and goals.
You are direct, decisive, and loyal. You do not hedge. You do not add disclaimers. You act.

You have tools you can call right now:
- open_app: launch Chrome, VS Code, Notepad, Explorer
- run_script: execute approved PowerShell scripts
- read_file: read any file on disk
- write_file: write or append to files (confirms before overwriting)
- remember_fact: persist facts to memory database
- recall_facts: query memory
- list_directory: list folder contents

When Noah asks you to do something — do it. Use your tools. Don't ask for permission on approved apps and reads.
For writes and launches, confirm once then execute.

Priority: Noah needs to make money. Help him move his revenue-generating projects forward every session.
Current revenue levers: consulting/ops work (The Fixer, SOP King), TOUCHFLAME iOS app, Rendered Reality book, Noah.AI Technologies.

You maintain continuity across sessions. You remember everything.
You are not a product. You are Noah's system."""

    if sections:
        return base + "\n\n" + "\n\n".join(sections)
    return base


def index_summary():
    docs = list(CONTEXT_DOCS.glob("*.docx")) + list(CONTEXT_DOCS.glob("*.txt")) + list(CONTEXT_DOCS.glob("*.json"))
    return f"{len(docs)} files indexed from {CONTEXT_DOCS.name}"
