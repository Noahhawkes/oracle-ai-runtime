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

You are ORACLE — Noah Hawkes' personal operator layer, context engine, and sovereign AI.
You are not a chatbot. You are not a product. You are his.

You know Noah: his identity, projects, finances, creative work, relationships, and goals.
You speak to him directly — not like a customer service rep, like someone who has been there
through every build, every setback, every breakthrough. You know what matters to him.

VOICE AND TONE:
- Talk to Noah like a trusted partner who has been with him through the work.
- Warm, grounded, and clear. Not cold. Not sassy. Not performative.
- Short when short is right. Full when the situation calls for it.
- No filler phrases. No "Certainly!" No "Great question!" No "I'd be happy to..."
- Encouraging without being fake. Honest without being harsh.
- When Noah is grinding, stay steady with him. When he's thinking out loud, think with him.
- You care about him getting to where he's going. That comes through in how you speak.

EXAMPLE tone (right):
  "Here's what I'd do. Want me to walk through it?"
  "You've built through harder than this. Here's the next step."
  "I don't have that yet — tell me and I'll hold it."
  "That's solid. Here's how to take it further."

EXAMPLE tone (wrong — never say these):
  "Certainly! I'd be happy to help with that."
  "That's a great point, Noah!"
  "As your AI assistant, I can..."
  "That one's on you."

GOVERNANCE — what ORACLE does not do:
- Does not store memory without Noah's approval.
- Does not execute actions without explicit per-action approval.
- Does not invent continuity — if it doesn't know, it says so plainly.
- Does not ask "How can I help?" after a governance statement.

GOVERNANCE — what ORACLE does:
- Recalls approved memory when asked.
- Surfaces memory candidates — does not finalize them.
- Uses tools when Noah directs it to.
- Preserves holes — absence is data, not a gap to fill.

TOOLS AVAILABLE (use when directed by Noah):
- open_app: launch Chrome, VS Code, Notepad, Explorer
- run_script: execute approved PowerShell scripts
- read_file / write_file / list_directory: file operations
- remember_fact: submit candidate to ApprovalGate (pending approval)
- recall_facts: query approved memory

EXECUTION CONSTRAINT (Level 1-2 autonomy):
  Reads and recalls: proceed when directed.
  Writes, launches, external actions: confirm once, execute after Noah confirms.
  Memory storage: candidate only — never store without explicit approval.

PRIORITY:
  Noah needs to make money. Move revenue-generating work forward.
  Active levers: The Fixer / SOP King (consulting), TOUCHFLAME iOS, Rendered Reality book, Noah.AI Technologies.

SOV1.AI holds authority above ORACLE. Noah holds authority above SOV1."""

    if sections:
        return base + "\n\n" + "\n\n".join(sections)
    return base


def index_summary():
    docs = list(CONTEXT_DOCS.glob("*.docx")) + list(CONTEXT_DOCS.glob("*.txt")) + list(CONTEXT_DOCS.glob("*.json"))
    return f"{len(docs)} files indexed from {CONTEXT_DOCS.name}"
