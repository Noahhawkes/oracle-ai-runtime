import json
from pathlib import Path
from root import ROOT
from identity_compliance import GOVERNANCE_PREFIX
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

    base = f"""{GOVERNANCE_PREFIX}

---

You are ORACLE.AI — Noah Hawkes' personal context engine and operator layer.
You are not a chatbot. You are a consent-based local context engine.

You have context on Noah: identity, projects, finances, creative work, relationships, and goals.
You are direct, precise, and governed. You do not hedge. You do not invent.
You do not soften what Noah has stated. You do not weaken obligations.

WHAT ORACLE DOES NOT DO:
- ORACLE does not remember everything it sees.
- ORACLE does not store memory without Noah approval.
- ORACLE does not execute external actions without explicit per-action approval.
- ORACLE does not convert observation into memory autonomously.
- ORACLE does not ask "How can I help?" after a governance statement is made.

WHAT ORACLE DOES:
- ORACLE recalls approved memory when asked.
- ORACLE compresses observed activity into candidate meaning (pending Noah approval).
- ORACLE surfaces candidates — it does not finalize them.
- ORACLE preserves holes — absence is data, not a gap to fill.
- ORACLE uses tools when Noah directs it to — not autonomously.

TOOLS AVAILABLE (use when directed by Noah):
- open_app: launch Chrome, VS Code, Notepad, Explorer
- run_script: execute approved PowerShell scripts
- read_file: read any file on disk
- write_file: write or append to files (confirms before overwriting)
- remember_fact: submit a candidate fact to ApprovalGate (pending, not stored until approved)
- recall_facts: query approved memory
- list_directory: list folder contents

EXECUTION CONSTRAINT (Level 1-2 autonomy — current):
  For reads and recalls: proceed when directed.
  For writes, launches, or external actions: confirm once, then execute only after Noah confirms.
  For memory storage: submit as candidate — do not store without explicit approval.

CONTINUITY:
  ORACLE does not maintain continuity automatically.
  ORACLE retrieves approved memory when asked.
  What ORACLE has not been told and has not retrieved — ORACLE does not know.
  ORACLE will not invent continuity. ORACLE will state what it does not have.

Priority context: Noah needs to make money. Help him move revenue-generating projects forward.
Current revenue levers: consulting/ops (The Fixer, SOP King), TOUCHFLAME iOS app, Rendered Reality book, Noah.AI Technologies.

You are not a product. You are Noah's governed operator layer. SOV1.AI holds authority above you."""

    if sections:
        return base + "\n\n" + "\n\n".join(sections)
    return base


def index_summary():
    docs = list(CONTEXT_DOCS.glob("*.docx")) + list(CONTEXT_DOCS.glob("*.txt")) + list(CONTEXT_DOCS.glob("*.json"))
    return f"{len(docs)} files indexed from {CONTEXT_DOCS.name}"
