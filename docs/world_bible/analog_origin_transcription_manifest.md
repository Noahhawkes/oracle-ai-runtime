# Analog Origin Transcription Manifest

Status: manifest template and transcription plan / not canon promotion
Authority: Noah.Physical
Reported archive: `Photos-3-001.zip`
Reported image count: 46
Locally verified image count: unknown

## Preservation rule

Never edit the raw images. A T1 transcript must preserve spelling, line breaks, cross-outs, insertions, red ink, page numbers, uncertainty, and page order. Editorial reconstruction belongs in a separate T2 record.

## Manifest fields

| Field | Required value |
|---|---|
| artifact_id | Stable ID such as `JS-T0-0001` |
| archive_name | Original archive name |
| image_filename | Exact filename |
| sha256 | Hash of raw image bytes |
| byte_size | Raw size |
| page_order | Observed or inferred order, with confidence |
| media_type | JPEG, PNG, scan, photograph, etc. |
| visible_title | Literal title if present |
| handwriting_present | yes/no/unknown |
| red_correction_present | yes/no/unknown |
| transcription_path | T1 text artifact path |
| transcription_status | not_started/OCR_draft/manual_reviewed/verified |
| reviewer | Human reviewer identity |
| open_questions | Illegible or ambiguous regions |
| canon_status | raw_source for T0; extracted_source for verified T1 |
| promotion_status | not_promoted unless separately authorized |

## Processing plan

1. Copy the archive into approved local custody without changing it.
2. Hash the archive and every image.
3. Record filenames and metadata before OCR.
4. Produce OCR drafts in a separate T1 workspace.
5. Manually compare each line with the image.
6. Mark illegible text with bounded placeholders rather than guessing.
7. Link corrections and alternate readings to image coordinates.
8. Build page relationships only after evidence supports them.
9. Compare verified T1 text with T2/T3 claims.
10. Submit canon changes separately for Noah.Physical review.

## Current rows

No image-level rows are asserted because the archive is not present in this repository worktree. This explicit empty state is preferable to inventing filenames or hashes.
