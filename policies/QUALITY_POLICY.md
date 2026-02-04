# policies/QUALITY_POLICY.md — HJB Quality Policy

## 1. Purpose
Define minimum quality expectations for text, images, and metadata to ensure the wiki remains trustworthy and usable for both humans and AI agents.

## 2. Quality goals
- Text: “AI-usable correctness” with targeted human verification.
- Images: best available resolution/clarity/color; faithful rendering.
- Metadata: stable identifiers, provenance, and anchoring sufficient to support verification and citation.

## 3. Text quality standard
### 3.1 Baseline principle
Text may be imperfect, but it must be coherent and semantically faithful enough that an AI assistant and a human can understand the meaning without systematic errors.

### 3.2 Required human verification for public release
For any PD-cleared segment being published:
- Title must be correct.
  - If AI-generated header/title is used, record the flag `is_ai_generated_title` (or equivalent) and display it in the wiki.
- Author handling:
  - If an author is present, record author identity consistently.
  - If none is present, explicitly mark “no named author.”
- Provenance anchors:
  - page range (start/end)
  - publication instance references (issue/volume/edition)
- Captions:
  - verify major captions when they materially affect interpretation
- High-impact details:
  - verify names, figures, measurements, specifications, and prices when central to the segment’s meaning or likely to be referenced

### 3.3 Optional verification (phased)
- Full-text perfection is not required everywhere.
- Priority for deeper verification:
  - flagship publications
  - high-use topics (tools, methods, prominent firms)
  - diagrams/plans and their supporting text
  - material specifications and engineering calculations

## 4. Image quality standard
### 4.1 Baseline principle
Publish the best available resolution and clarity. Prefer outputs derived from high-resolution page images (JP2 or equivalent) rather than PDFs, unless a PDF is demonstrably better.

### 4.2 Allowed evidentiary transforms
- rotation/deskew
- margin crop
- stitching multi-page spreads
- minimal tonal normalization for legibility (non-destructive intent)

Prohibited for evidentiary assets:
- content-altering edits (removing/adding elements, redrawing as if original, changing text content)

### 4.3 Interpretive assets
Interpretive assets (e.g., SVG redraws) are allowed only when:
- the evidentiary original is also published and linked
- the interpretive nature is clearly disclosed
- the interpretive asset does not claim evidentiary authority

## 5. Metadata quality
Minimum descriptive metadata for a publishable segment:
- segment type (controlled vocabulary)
- stable title (AI-generated flagged if applicable)
- author identity or “no named author”
- page range anchors
- provenance reference to the manifestation/provider

Minimum metadata for assets:
- asset type (evidentiary/interpretive)
- linkage to parent segment(s)
- provenance/page anchors
- derivation notes (especially for stitched spreads and interpretive derivatives)

## 6. Ads / companies / products (phased)
- Advertisements are first-class segments.
- Ads may link to multiple companies and multiple products.
- Entity genealogy (company renames, mergers, etc.) is explicitly phased; do not block publication on deep corporate history.

---
