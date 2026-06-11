# ORACLE Filesystem Metadata Tiers v0.1

Status: proposed architecture  
Scope: filesystem discovery, indexing, Drive Scope, continuity relevance

## Core Rule

ORACLE should not begin with unrestricted whole-machine content access.

The safer foundation is metadata-first discovery, relevance scoring, and explicit scope approval before deep reads.

## Why Not Start With System32

`C:\Windows\System32` contains tens of thousands of operating system files. Most have little or no continuity value for ORACLE.

Unrestricted content indexing would create:

- Massive processing overhead
- Meaningless metadata volume
- Slower indexing
- More false positives
- Higher risk around operating system files
- Poor signal-to-noise for Noah continuity

## Architecture

```text
Filesystem
-> Metadata Scanner
-> File Classification
-> Relevance Score
-> Candidate Index
-> Context Engine
-> Meaning Compression
```

The scanner should answer:

- What files exist?
- What changed?
- What projects are active?
- What documents may matter?

It should not attempt to memorize Windows itself.

## Access Tiers

### Tier 1: High Value

Examples:

- ORACLE.AI project folders
- Documents
- Downloads
- Desktop
- Git repositories
- Google Drive sync folders
- Linear exports
- Notes
- Writing projects

Default behavior:
Metadata scan only unless already approved by Drive Scope. Content reads still require scope validation.

### Tier 2: Medium Value

Examples:

- Pictures
- Videos
- Archives
- PDFs
- Spreadsheets

Default behavior:
Metadata scan first. Content extraction requires explicit purpose, approved scope, and file-type policy.

### Tier 3: Low Value

Examples:

- Program Files
- ProgramData
- AppData

Default behavior:
Metadata only by default. Content reads are blocked unless Noah approves a narrow path and purpose.

### Tier 4: Reference Only

Examples:

- Windows
- System32
- DriverStore
- WinSxS

Default behavior:
Metadata only. No content reads. No writes. No actuation. No recursive deep analysis unless Noah explicitly approves a narrow diagnostic task.

## System File Metadata Shape

Reference-only system files may be represented like this:

```json
{
  "path": "C:\\Windows\\System32\\notepad.exe",
  "size": 238592,
  "created": "timestamp",
  "modified": "timestamp",
  "extension": ".exe",
  "sha256": "optional-for-small-or-explicit-files",
  "category": "system_binary",
  "access_tier": "reference_only",
  "content_read": false
}
```

Hashing should be optional and bounded. ORACLE should not spend days hashing or indexing operating system binaries with no continuity value.

## Governance

All filesystem discovery must remain under Drive Scope and approval policy.

Unknown paths block.

Proposed-only paths block.

Governance unavailable blocks.

System paths are never approved merely because they are readable.

## Meaning Compression Boundary

Metadata is not memory.

A filesystem event becomes useful only after:

```text
metadata
-> relevance score
-> candidate context
-> meaning compression
-> memory authority review
```

ORACLE should preserve meaning, not raw machine clutter.
