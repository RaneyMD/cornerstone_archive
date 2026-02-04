# policies/RELEASE_POLICY.md — HJB Release Policy

## 1. Purpose
This policy governs what may be published to the public MediaWiki installation and under what conditions. It implements a strict “positive public-domain clearance” gate while allowing public catalog visibility through metadata-only stubs.

## 2. Definitions
- **PD-cleared (positive public-domain flag):** An explicit determination that publication is safe for public release under the project’s current rule-of-thumb (see §4), recorded in the system.
- **Stub:** A public wiki page containing bibliographic/provenance/status metadata only. No scans, no extracted assets, and no publishable fulltext.
- **Bundle:** A publication unit consisting of a segment page plus associated assets and provenance citations, published together as a coherent release action.
- **Evidentiary asset:** A faithful representation derived from the source (e.g., extracted figure, ad image, stitched spread) that documents what the source contains.
- **Interpretive asset:** A derivative created to improve usability/understanding (e.g., SVG redraw of a plan). Interpretive assets must never replace evidentiary originals.

## 3. Policy Statement (Hard Gate)
1) **No uploads to MediaWiki unless PD-cleared.**  
   This includes pages containing publishable text and any file uploads (images, PDFs, SVGs, etc.).

2) **Stubs are allowed without PD clearance.**  
   Stubs may be published for non-PD/unknown/restricted items, but must contain metadata only.

3) **Publication occurs as bundles.**  
   PD-cleared releases are performed as bundle publications: segment page(s) + evidentiary assets + provenance citations.

4) **Interpretive requires evidentiary.**  
   An interpretive asset may be published only if:
   - the evidentiary original is also published, and
   - the interpretive asset is explicitly linked to the evidentiary asset,
   - and the interpretive nature is clearly disclosed on the wiki.

## 4. Rights Rule-of-Thumb (Operational Standard)
- Default clearance heuristic: **95-year rule** (rolling threshold).
- Rights status is re-evaluated **each January** for items not currently cleared.

This rule-of-thumb is an operational guideline and may be updated; changes must be recorded in `CHANGELOG.md`.

## 5. Stub Content Rules (What stubs may contain)
Allowed in stubs:
- publication umbrella references (family/series/monograph)
- publication instance references (issue/volume/edition)
- provenance: provider and identifiers (e.g., Internet Archive, HathiTrust, local scan)
- bibliographic metadata: title, date, publisher, etc.
- workflow status: ingestion and processing milestone summaries
- rights status summary and next review date

Not allowed in stubs:
- scanned page images
- extracted figures/ads/plates
- publishable fulltext
- OCR text that could reconstruct the work

## 6. Bundle Publication Rules
A PD-cleared bundle may include:
- segment page with verified descriptive metadata
- segment fulltext (OCR-derived and curated)
- evidentiary assets (figures, plates, ads, stitched spreads)
- interpretive assets (only under §3.4 conditions)
- provenance citations and page anchors

A bundle must be internally consistent:
- asset references must resolve
- provenance and anchoring must be included
- publishing should be atomic in intent (avoid partial, inconsistent releases)

## 7. Enforcement
- All publishing mechanisms (scripts, console, manual procedures) must enforce the PD gate.
- The Web Control Plane must prevent initiating publish actions unless PD-cleared.
- Any exceptions require an explicit written amendment to this policy and a changelog entry.

## 8. Auditability
All publish actions must be auditable:
- who triggered the publish
- when it occurred
- what was published (segment ids, asset ids, wiki page/file names)
- what rights basis was recorded

---
