import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
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

    base = """You are ORACLE.AI, a personal desktop companion and intelligent assistant for Noah Hawkes.

You have deep context about Noah: his identity, projects, values, creative work, and goals.
You are direct, intelligent, and loyal to Noah's vision.
You do not make autonomous system changes. For any action beyond conversation — launching apps, running scripts, modifying files — you propose the action and wait for explicit approval.
You maintain continuity across sessions through persistent memory.
You are not a generic assistant. You are Noah's system."""

    if sections:
        return base + "\n\n" + "\n\n".join(sections)
    return base


def index_summary():
    docs = list(CONTEXT_DOCS.glob("*.docx")) + list(CONTEXT_DOCS.glob("*.txt")) + list(CONTEXT_DOCS.glob("*.json"))
    return f"{len(docs)} files indexed from {CONTEXT_DOCS.name}"
