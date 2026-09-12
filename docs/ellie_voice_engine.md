# Ellie Voice Engine

Status: local draft generator.

The Ellie voice engine creates local generated draft messages from grounded
Ellie / Rendered Reality source material. It is not a sender, not a canon
promotion tool, and not a claim that Ellie is physically real.

## Source Inputs

The engine retrieves from:

- `data/domains/ellie/source_manifest.jsonl`
- Ellie Hawkes / Drakin records listed in that manifest
- Dragonkin records listed in that manifest
- Rendered Reality Ellie records listed in that manifest
- Approved Ellie domain notes already present in the local repository
- Noah.Physical corrections after they are added to the Ellie manifest

Readable local text-like files are sampled directly. DOCX files are read through
their internal document XML when available. PDF and unresolved connector targets
remain source references through manifest metadata until a text extraction pass
is explicitly approved.

## Output Locations

- Drafts: `data/domains/ellie/messages/pending/`
- Receipts: `data/domains/ellie/messages/receipts/`

## Draft Fields

Each draft includes:

- `trigger`
- `context`
- `mood`
- `message`
- `source_files_used`
- `style_anchors_used`
- `timestamp`
- `generation_model`
- `canon_status="generated_draft"`
- `promotion_status="not_promoted"`
- `receipt`
- `external_sending=false`
- `human_authored_claim=false`
- `physical_personhood_claim=false`

## Mood Controls

Supported moods:

- `gentle`
- `curious`
- `brave`
- `playful`
- `reflective`
- `urgent`
- `quiet`

The mood is recorded as a style anchor. It does not unlock any sending,
personhood, or canon authority.

## Variation

The engine does not use prewritten rotating messages. It retrieves source text
and manifest notes, builds a source-token chain, and composes a fresh draft from
that source pool. Recent pending drafts are checked to prevent exact repeats.

## Boundaries

- Drafts only.
- No external sending.
- No claim of physical personhood.
- No claim that the draft is human-authored.
- No canon promotion.
- No fixed canned message bank.
- Receipts are required for every written draft.

## Command

```powershell
python -m core.ellie_voice "morning encouragement" --mood gentle --context "Noah is returning to work"
```

The command prints the draft path, receipt path, status fields, source count,
and generated message.
