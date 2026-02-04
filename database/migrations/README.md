# Database Migrations

This directory contains SQL migration scripts that build and evolve the Cornerstone Archive state database schema.

## Overview

The state database (`raneywor_csa_state`) is the central repository for all workflow metadata, processing state, and publication information. It tracks publications through four processing stages (Acquire → Extract → Segment → Publish) and maintains rights evaluations and publishing status.

**Database Engine:** MySQL 5.7+  
**Charset:** utf8mb4  
**Collation:** utf8mb4_unicode_ci  
**Storage Engine:** InnoDB

---

## Migration Files

### `001_create_cornerstone_archive_foundation_schema.sql`

Creates all 17 tables that comprise the complete foundation schema. This is the authoritative source for the state database structure.

**To apply:**
```bash
# Development
mysql -h gator2111.hostgator.com -u raneywor_csa_dev -p raneywor_csa_dev_state < database/migrations/001_create_cornerstone_archive_foundation_schema.sql

# Production
mysql -h gator2111.hostgator.com -u raneywor_csa_admin -p raneywor_csa_state < database/migrations/001_create_cornerstone_archive_foundation_schema.sql
```

**Safe to run:** Yes (idempotent). The script uses `CREATE TABLE IF NOT EXISTS` and can be re-executed safely. However, it does not drop existing tables.

---

## Schema Dictionary

The schema is organized into 4 logical tiers, each serving a distinct purpose in the processing pipeline.

### TIER 0: OPERATIONAL (4 tables)

These tables manage the workflow engine, worker processes, audit trails, and schema versioning.

#### `jobs_t`
Represents discrete tasks in the processing pipeline. Each job corresponds to a unit of work (e.g., "acquire container X", "extract pages from container Y").

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. Unique identifier for each job. |
| `job_type` | VARCHAR(64) NOT NULL | Task type (e.g., "acquire_source", "extract_pages", "segment_works"). Determines which handler processes the job. |
| `target_ref` | VARCHAR(512) NOT NULL | Reference to the entity being processed (e.g., container ID, instance ID, segment ID). Format depends on job_type. |
| `state` | ENUM('queued','running','succeeded','failed','blocked','canceled') | Current state of the job. Queued → Running → Terminal state (Succeeded/Failed/Blocked/Canceled). |
| `attempts` | INT UNSIGNED | Count of execution attempts. Used for retry logic. |
| `claimed_by_worker` | VARCHAR(64) NULL | Worker ID that claimed this job. NULL if unclaimed. Enables distributed processing. |
| `created_at` | DATETIME | Timestamp when job was created. |
| `updated_at` | DATETIME | Timestamp of last state change. Indexed for finding recently-changed jobs. |
| `started_at` | DATETIME NULL | Timestamp when execution began. NULL until job runs. |
| `finished_at` | DATETIME NULL | Timestamp when job completed (success or failure). NULL if still running. |
| `last_error` | TEXT NULL | Error message if job failed. Diagnostic information. |
| `log_path` | VARCHAR(512) NULL | Path to detailed execution log on NAS. |
| `result_path` | VARCHAR(512) NULL | Path to result payload (JSON or other format). |

**Indexes:** `(state)`, `(updated_at)`, `(claimed_by_worker)`

**Usage:** Watcher queries `jobs_t` for queued jobs, claims them, executes handlers, updates state. Operations console displays job history and status.

---

#### `workers_t`
Tracks active worker processes (e.g., OrionMX, OrionMega) and their health status.

| Field | Type | Purpose |
|-------|------|---------|
| `worker_id` | VARCHAR(64) PRIMARY KEY | Unique identifier for worker (e.g., "OrionMX", "OrionMega"). Set by configuration. |
| `last_heartbeat_at` | DATETIME NOT NULL | Timestamp of most recent heartbeat. Used to detect stalled workers. |
| `status_summary` | VARCHAR(255) NULL | Human-readable status (e.g., "Processing container_42", "Idle"). |

**Indexes:** `(last_heartbeat_at)`

**Usage:** Health check script queries heartbeat timestamps to detect stalled workers. Watcher updates heartbeat periodically. Operations console displays worker status.

---

#### `audit_log_t`
Records all significant operations for audit and compliance purposes.

| Field | Type | Purpose |
|-------|------|---------|
| `audit_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. Unique audit record ID. |
| `actor` | VARCHAR(128) NOT NULL | User or system that performed action (e.g., "Michael Raney", "system", "watcher_OrionMX"). |
| `action` | VARCHAR(64) NOT NULL | Action type (e.g., "publish_bundle", "approve_segment", "update_rights_status"). |
| `target_type` | VARCHAR(64) NOT NULL | Type of entity affected (e.g., "segment", "rights_evaluation", "publish_bundle"). |
| `target_id` | VARCHAR(64) NOT NULL | ID of affected entity. |
| `created_at` | DATETIME | Timestamp of action. Indexed for audit queries over time ranges. |
| `details_json` | TEXT NULL | Additional context as JSON (e.g., old values, new values, reason for change). |

**Indexes:** `(action)`, `(created_at)`

**Usage:** Compliance and troubleshooting. Track who published what, when. Detect unauthorized changes.

---

#### `database_migrations_t`
Tracks which migrations have been applied and their status. Ensures safe, repeatable schema evolution.

| Field | Type | Purpose |
|-------|------|---------|
| `migration_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `filename` | VARCHAR(256) NOT NULL UNIQUE | Migration filename (e.g., "001_create_cornerstone_archive_foundation_schema.sql"). Used to detect duplicates. |
| `checksum` | VARCHAR(64) NOT NULL | SHA256 hash of migration file content. Detects accidental modifications. |
| `version_number` | INT UNSIGNED NOT NULL | Numeric ordering (1, 2, 3...). Ensures migrations run in correct sequence. |
| `applied_at` | DATETIME | Timestamp when migration was applied. |
| `applied_by` | VARCHAR(128) NOT NULL | User who applied migration (e.g., "Michael Raney", "deployment_script"). |
| `status` | ENUM('applied','rolled_back','error') | Outcome of migration. 'error' means partial or failed application. |
| `error_message` | TEXT NULL | If status='error', description of failure. |
| `rollback_script` | VARCHAR(512) NULL | Path to rollback script if migration fails. |
| `notes` | TEXT NULL | Additional context (e.g., "Added indexes for performance"). |

**Indexes:** `(applied_at)`, `(status)`, `(version_number)`, `(filename)` UNIQUE

**Usage:** Migration system checks this table before running new migrations. Prevents re-running already-applied migrations. Enables rollback if needed.

---

### TIER 1: PUBLICATION HIERARCHY (5 tables)

These tables model the bibliographic structure: how publications are organized into families, titles, and instances (issues/editions).

#### `publication_families_t`
Represents a publication family—a distinct publication line with a consistent name/identity over time (e.g., "American Architect family", "Railway Engineering family").

A family may contain multiple titles if the publication was renamed (e.g., "American Architect" became "American Architect & Building News"). A family groups these together conceptually.

| Field | Type | Purpose |
|-------|------|---------|
| `family_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. Unique identifier for family. |
| `family_root` | VARCHAR(255) NOT NULL UNIQUE | Machine-readable family identifier (e.g., "american_architect_family", "railway_engineering_family"). Used in file paths and keys. |
| `family_code` | VARCHAR(64) NULL UNIQUE | Optional short code (e.g., "AA" for American Architect). Human-friendly. |
| `family_name` | VARCHAR(256) NOT NULL | Display name (e.g., "American Architect family"). |
| `family_type` | ENUM('journal','series','monograph') | Type of publication. 'journal' = serial publication. 'series' = book series. 'monograph' = single book. |
| `description` | TEXT NULL | Long-form description (e.g., "Weekly architectural trade journal published 1876–1920"). |
| `first_year_known` | SMALLINT UNSIGNED NULL | Earliest year this family published. Used for data validation and timeline queries. |
| `last_year_known` | SMALLINT UNSIGNED NULL | Latest year this family published. If ongoing, may be NULL or current year. |
| `external_identifiers` | JSON NULL | References to external databases (e.g., `{"loc_identifier": "n12345", "oclc": "9876543"}`). |
| `created_at` | DATETIME | Timestamp when family was registered. |
| `created_by` | VARCHAR(128) | User who created record. |
| `updated_at` | DATETIME NULL | Timestamp of last edit. |
| `updated_by` | VARCHAR(128) NULL | User who last edited record. |

**Indexes:** `(family_type)`, `(first_year_known)`, `(last_year_known)`, `(family_root)` UNIQUE, `(family_code)` UNIQUE

**Usage:** Starting point for all publication queries. One family → many titles → many instances → many containers.

---

#### `publication_titles_t`
Represents a distinct title within a family. A publication may have multiple titles over time (title changes, variant names).

For example, the "American Architect" family might have:
- Title 1: "American Architect" (1876–1888)
- Title 2: "American Architect & Building News" (1888–1920)

Each title has its own metadata (publisher, location, date range).

| Field | Type | Purpose |
|-------|------|---------|
| `title_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `family_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_families_t. Links title to its family. |
| `canonical_title` | VARCHAR(512) NOT NULL | Official/authoritative title as printed (e.g., "American Architect & Building News"). |
| `title_start_date` | DATE NULL | Date when this title begins (e.g., 1876-01-01). |
| `title_start_date_estimated` | BOOLEAN | TRUE if start_date is estimated (e.g., "circa 1876" → uncertain). Useful flag for cleanup. |
| `title_end_date` | DATE NULL | Date when this title ends. NULL if ongoing. |
| `title_end_date_estimated` | BOOLEAN | TRUE if end_date is estimated. |
| `subtitle` | VARCHAR(512) NULL | Subtitle or variant title (e.g., "A journal of the progress of..."). |
| `abbreviation` | VARCHAR(128) NULL | Abbreviation used in citations (e.g., "Amer. Arch."). |
| `publisher` | VARCHAR(256) NULL | Publisher name. |
| `publisher_city` | VARCHAR(128) NULL | City of publication (e.g., "New York", "Boston"). |
| `publisher_country` | VARCHAR(64) NULL | Country (e.g., "United States"). |
| `notes` | TEXT NULL | Editorial notes (e.g., "Title changed after vol. 10", "Variant spellings exist"). |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(family_id)`, `(canonical_title)` (partial), `(title_start_date, title_end_date)`, `(publisher)` (partial)

**Usage:** Queries like "all issues of this title" or "all titles by this publisher".

---

#### `publication_instances_t`
Represents a single publishable unit: a journal issue, a book edition, a volume, a part, or a special issue.

This is the fundamental work unit in the pipeline. Every container maps to one or more instances. Every segment and asset is associated with an instance. Rights evaluations are at the instance level.

| Field | Type | Purpose |
|-------|------|---------|
| `instance_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `family_id` | BIGINT UNSIGNED NOT NULL | Denormalization: foreign key to family. Speeds up family-level queries. |
| `title_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_titles_t. Which title is this instance of? |
| `instance_key` | VARCHAR(512) NOT NULL UNIQUE | Machine-readable unique identifier for deduplication and external reference stability. Manually assigned during instance creation with UI template assistance. Format depends on `instance_type`. Used to detect duplicate ingests from different sources and as stable external reference. See templates below. |
| `instance_type` | ENUM('issue','volume','edition','part') | Type. Most common: 'issue'. |
| `title` | VARCHAR(512) NULL | Title of this specific instance (if different from title_t.canonical_title, e.g., special issue title). |
| `publication_year` | SMALLINT UNSIGNED NOT NULL | Year published. Required for validation and queries. |
| `publication_date` | DATE NULL | Exact date (e.g., 1876-01-01). NULL if only year known. |
| `publication_date_display` | VARCHAR(32) NOT NULL | Human-readable date (e.g., "January 1, 1876", "Jan–Mar 1876", "Spring 1876"). What to display to users. |
| `volume_label` | VARCHAR(64) NULL | Volume identifier if applicable (e.g., "I", "Vol. 1", "27"). |
| `volume_sort` | INT NULL | Numeric sort key for volumes (1, 2, 3...). Enables proper sorting even if labels are non-numeric. |
| `issue_label` | VARCHAR(64) NULL | Issue identifier (e.g., "1", "No. 52", "793"). |
| `issue_sort` | INT NULL | Numeric sort key for issues. |
| `part_label` | VARCHAR(64) NULL | Part identifier (e.g., "Part A", "Part 1"). |
| `edition_label` | VARCHAR(64) NULL | Edition identifier (e.g., "1st ed", "Revised edition"). |
| `edition_sort` | INT NULL | Numeric sort key for editions (1, 2, 3...). |
| `is_special_issue` | BOOLEAN | TRUE if this is a special issue (e.g., anniversary issue, special topic). Flag for special handling. |
| `is_supplement` | BOOLEAN | TRUE if this is a supplement (e.g., bound separately but numbered with main series). |
| `language` | VARCHAR(32) | Language of publication (default: "English"). Allows for multilingual archives. |
| `extent_pages` | INT UNSIGNED NULL | Expected number of pages. Used to validate containers. |
| `extent_articles` | INT UNSIGNED NULL | Expected article count. Used in QA. |
| `extent_ads` | INT UNSIGNED NULL | Expected ad count. Used in QA. |
| `rights_statement` | VARCHAR(512) NULL | Copyright/rights info as printed in the publication. For reference. |
| `is_manually_verified` | BOOLEAN | TRUE if human verified metadata (publication date, page count, content). Important quality flag. |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(family_id)`, `(title_id)`, `(instance_type)`, `(publication_year)`, `(publication_date)`, `(volume_sort)`, `(issue_sort)`, `(is_manually_verified)`, `(instance_key)` UNIQUE

**Instance Key Templates**

The `instance_key` field should be manually assigned during instance creation using these templates. UI helpers can provide auto-complete and template pre-filling based on instance type and metadata.

**For 'issue' (from a periodical):**
```
Format: {FAMILY_CODE}_is_{YEAR}{MONTH}{DAY}_{VOLUME_SORT}_{ISSUE_SORT}
Example: AA_is_18760101_001_0001
Meaning: American Architect, January 1, 1876, Volume 1, Issue 1
```

**For 'volume' (from a book series):**
```
Format: {FAMILY_CODE}_vo_{VOLUME_SORT}_{YEAR}
Example: SMITH_ARCH_vo_027_1910
Meaning: Smith's Architecture, Volume 27, 1910 edition
Note: Year included because book series may be revised and reprinted.
```

**For 'edition' (monograph/single book):**
```
Format: {FAMILY_CODE}_ed_{YEAR}
Example: MODERN_BUILDING_ed_1910
Meaning: Modern Building Design, 1910 edition
Note: Year only (no edition number) because edition may be unspecified but year appears in copyright notice.
```

**Notes on instance_key:**
- Must be unique (UNIQUE constraint prevents duplicates)
- Manually assigned, not auto-generated (allows flexibility for edge cases)
- Should be constructed from reliable, permanent metadata (year, volume, etc.)
- Used to detect duplicate ingests: if same publication is ingested from multiple sources, use identical instance_key
- External systems can reference this key for stable citation/linking

**Usage:** Core entity. Every stage of processing references instances. Rights decisions at instance level. Publishing output mapped to instances.

---

### TIER 2: CONTENT MANAGEMENT (3 tables)

These tables track the source containers and their relationship to publication instances, plus the individual pages within containers.

#### `containers_t`
Represents a downloadable container from an external source (Internet Archive, HathiTrust, local scan).

A container is a "package" of pages as provided by the source. One container may contain one or more publication instances (e.g., a bound volume may contain 12 issues).

| Field | Type | Purpose |
|-------|------|---------|
| `container_id` | VARCHAR(128) PRIMARY KEY | Unique identifier. Often the source identifier (e.g., "sim_american-architect_1876_001" from IA). |
| `source_system` | VARCHAR(64) NOT NULL | Source (e.g., "internet_archive", "hathitrust", "local"). Determines how to fetch/validate. |
| `source_identifier` | VARCHAR(255) NOT NULL | Unique ID within source system (e.g., IA identifier, HathiTrust ID). Indexed for lookups. |
| `source_url` | VARCHAR(512) NULL | URL to container in source system (e.g., IA details page). For reference/linking. |
| `container_type` | VARCHAR(64) NOT NULL | Type (e.g., "bound_volume", "microfilm_reel", "journal_issue", "book"). |
| `extent_pages` | INT UNSIGNED NULL | Expected page count from source metadata. |
| `download_status` | ENUM('pending','in_progress','complete','failed') | Stage 1 status. Pending → In Progress → Complete or Failed. |
| `validation_status` | ENUM('pending','passed','failed') | Have we validated the downloaded files? Pending → Passed or Failed. |
| `downloaded_at` | DATETIME NULL | Timestamp when download completed. |
| `validated_at` | DATETIME NULL | Timestamp when validation completed. |
| `raw_path` | VARCHAR(512) NULL | Path on NAS in raw layer (e.g., `\\RaneyHQ\Michael\...\01_RAW\container_001`). |
| `working_path` | VARCHAR(512) NULL | Path in working layer after extraction (e.g., `\\RaneyHQ\Michael\...\02_WORK\container_001`). |
| `notes` | TEXT NULL | Operational notes (e.g., "Missing pages 10-15", "OCR incomplete"). |
| `created_at` | DATETIME | Timestamp when registered. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | Timestamp of last update. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(source_identifier)`, `(download_status)`, `(validation_status)`, `(created_at)`

**Usage:** Track download progress. Identify failed downloads. Map containers to instances.

---

#### `container_instances_t`
Many-to-many relationship: which instances appear in which containers, and on which pages?

A bound volume (container) may contain issues 1–12 of a journal (12 instances). This table records that mapping.

| Field | Type | Purpose |
|-------|------|---------|
| `link_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `container_id` | VARCHAR(128) NOT NULL | Foreign key → containers_t. |
| `instance_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_instances_t. |
| `start_page_in_container` | INT UNSIGNED NULL | First page of this instance within the container (1-based). |
| `end_page_in_container` | INT UNSIGNED NULL | Last page of this instance within the container. |
| `start_page_in_instance` | INT UNSIGNED NULL | Page number as printed on the first page (e.g., page 1, page 243). |
| `end_page_in_instance` | INT UNSIGNED NULL | Page number as printed on the last page. |
| `is_preferred` | BOOLEAN | TRUE if this container is the preferred source for this instance. Used when multiple sources exist. |
| `is_complete` | BOOLEAN | TRUE if all expected pages of this instance are present. FALSE if pages missing. |
| `ocr_quality_score` | DECIMAL(3,2) NULL | OCR confidence for this instance (0.00–1.00). Quality indicator. |
| `coverage_notes` | TEXT NULL | Notes on coverage (e.g., "Pages 5–10 missing", "OCR poor on pages 1–3"). |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |

**Indexes:** `(container_id, instance_id)` UNIQUE, `(instance_id)`, `(is_preferred)`

**Usage:** Answer "which container has this instance?", "what instances are in this container?". Critical for Stage 1 output validation.

---

#### `pages_t`
Represents individual pages within a container. Tracks page-level metadata: page numbers, OCR status, image dimensions, etc.

| Field | Type | Purpose |
|-------|------|---------|
| `page_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `container_id` | VARCHAR(128) NOT NULL | Foreign key → containers_t. Which container is this page from? |
| `instance_id` | BIGINT UNSIGNED NULL | Foreign key → publication_instances_t. Which instance? May be NULL if not yet mapped. |
| `page_index` | INT UNSIGNED NOT NULL | 0-based sequential index within container (0, 1, 2, ...). For ordering. |
| `page_number_printed` | VARCHAR(32) NULL | Number as printed on page (e.g., "1", "243", "xii", "Cover"). |
| `page_label` | VARCHAR(64) NULL | Label from source metadata (e.g., "Cover", "Title Page", "i", "1"). |
| `page_type` | ENUM('content','cover','index','toc','advertisement','plate','blank','other') | Page type. Used for extraction logic (skip blank pages, etc.). |
| `is_cover` | BOOLEAN | TRUE if this is a front/back cover. |
| `is_plate` | BOOLEAN | TRUE if this is a plate (e.g., fold-out map). Special handling. |
| `is_blank` | BOOLEAN | TRUE if page is blank. |
| `is_supplement` | BOOLEAN | TRUE if part of a supplemental/insert section. |
| `has_ocr` | BOOLEAN | TRUE if OCR text is available. Indexed for "find pages without OCR" queries. |
| `ocr_source` | VARCHAR(32) NULL | Source of OCR (e.g., "ia_hocr", "ia_djvu", "tesseract", "hathi_alto"). |
| `ocr_confidence` | DECIMAL(3,2) NULL | OCR confidence (0.00–1.00). Quality metric. |
| `ocr_word_count` | INT UNSIGNED NULL | Number of words recognized by OCR. Sanity check (blank page = 0 words). |
| `ocr_text_snippet` | VARCHAR(500) NULL | First 500 chars of OCR text. Searchable preview. |
| `is_manually_verified` | BOOLEAN | TRUE if human reviewed this page (checked OCR accuracy, verified content). |
| `image_width` | INT UNSIGNED NULL | Width in pixels (from extracted JPEG). |
| `image_height` | INT UNSIGNED NULL | Height in pixels. |
| `image_dpi` | INT UNSIGNED NULL | Resolution (dots per inch). Important for quality. |
| `image_color_space` | VARCHAR(32) NULL | Color space (e.g., "RGB", "CMYK", "Grayscale"). |
| `notes` | TEXT NULL | Editorial notes (e.g., "Page damaged", "OCR very poor"). |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(container_id)`, `(instance_id)`, `(container_id, page_index)`, `(page_type)`, `(has_ocr)`, `(created_at)`

**Usage:** Stage 2 populates this table. Segment creation uses pages_t to find content. QA queries check OCR coverage, image quality.

---

### TIER 3: PROCESSING PIPELINE (6 tables)

These tables track the results of Stages 2–4: segmentation, asset extraction, entity recognition, and publishing.

#### `segments_t`
Represents a extracted content segment: a discrete article, advertisement, or other publishable unit.

Segments are created during Stage 2 (Segment Works) by parsing OCR text and identifying article boundaries within a publication instance.

| Field | Type | Purpose |
|-------|------|---------|
| `segment_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `instance_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_instances_t. Which instance? |
| `container_id` | VARCHAR(128) NOT NULL | Foreign key → containers_t. Source container. |
| `segment_type` | VARCHAR(64) NOT NULL | Type (e.g., "article", "advertisement", "letter", "editorial"). |
| `title` | VARCHAR(512) NULL | Title of segment. May be NULL if untitled. |
| `is_title_ai_generated` | BOOLEAN | TRUE if title was AI-generated (not found in OCR). Flag for manual review. |
| `page_start_in_container` | INT UNSIGNED NOT NULL | First page of segment (in container, 1-based). |
| `page_end_in_container` | INT UNSIGNED NOT NULL | Last page of segment (in container). |
| `page_start_in_instance` | INT UNSIGNED NOT NULL | First page (in instance, as printed). |
| `page_end_in_instance` | INT UNSIGNED NOT NULL | Last page (in instance, as printed). |
| `start_page_id` | BIGINT UNSIGNED NOT NULL | Foreign key → pages_t. Reference page object for first page. |
| `end_page_id` | BIGINT UNSIGNED NOT NULL | Foreign key → pages_t. Reference page object for last page. |
| `page_spread_stitched` | BOOLEAN | TRUE if pages were stitched together (e.g., multi-page spread from OCR perspective). |
| `extractors_json` | JSON NULL | Metadata about extraction (e.g., `{"extractor": "tesseract_v4.1", "confidence": 0.87}`). |
| `ocr_text_raw` | MEDIUMTEXT NULL | Raw OCR text as extracted. Unedited. |
| `ocr_text_cleaned` | MEDIUMTEXT NULL | Cleaned OCR text. Post-processed (line breaks normalized, etc.). Indexed for full-text search. |
| `workflow_state` | ENUM('stub_only','draft','qa_ready','verified','pd_cleared','publish_ready','published','needs_revision') | Processing state. stub_only → draft → qa_ready → verified → pd_cleared → publish_ready → published. |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User (e.g., "stage2_extract"). |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(instance_id)`, `(container_id)`, `(segment_type)`, `(workflow_state)`, `(start_page_id)`, `(end_page_id)`, `(created_at)`, FULLTEXT `(title, ocr_text_cleaned)`

**Usage:** Core deliverable. Each segment is a potential wiki article. Workflow state drives publishing decisions. Fulltext index enables search.

---

#### `assets_t`
Represents extracted media assets: images (figures, plates, advertisements), diagrams, etc.

Assets are extracted during Stage 2 and associated with segments during Stage 3. An asset can be "evidentiary" (copy of original) or "interpretive" (redraw, SVG recreation).

| Field | Type | Purpose |
|-------|------|---------|
| `asset_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `instance_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_instances_t. Which instance? |
| `asset_type` | VARCHAR(64) NOT NULL | Type (e.g., "figure", "photograph", "diagram", "advertisement", "plate", "map"). |
| `title` | VARCHAR(512) NULL | Title/caption. |
| `description` | TEXT NULL | Long-form description. |
| `is_evidentiary` | BOOLEAN | TRUE if this is a faithful copy of original (JPEG from page). FALSE if interpretive (SVG redraw). |
| `derived_from_asset_id` | BIGINT UNSIGNED NULL | If interpretive, foreign key to evidentiary asset. Links interpretive back to original. |
| `source_pages_json` | JSON NULL | Array of page IDs this asset came from. E.g., `[{"page_id": 42, "description": "Detail from plate"}]`. |
| `file_location` | VARCHAR(512) NOT NULL | Full path to file on NAS (e.g., `\\RaneyHQ\...\assets\figure_001.jpg`). |
| `file_format` | VARCHAR(32) NOT NULL | Format (e.g., "jpeg", "png", "svg", "tiff"). |
| `file_size_bytes` | BIGINT UNSIGNED NULL | File size. Used for storage estimation. |
| `width_pixels` | INT UNSIGNED NULL | Image width. For QA/display. |
| `height_pixels` | INT UNSIGNED NULL | Image height. |
| `resolution_dpi` | INT UNSIGNED NULL | Resolution. Important quality metric. |
| `workflow_state` | ENUM('internal_only','qa_ready','approved','published') | internal_only → qa_ready → approved → published. |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(instance_id)`, `(asset_type)`, `(workflow_state)`, `(is_evidentiary)`, `(derived_from_asset_id)`

**Usage:** Assets are linked to segments via `segment_assets_t`. RELEASE_POLICY governs publication: evidentiary assets published first, interpretive only if evidentiary also published.

---

#### `entities_t`
Catalog of named entities (companies, people, places, standards, technologies) mentioned in segments.

Used for entity extraction, linking, and cross-referencing. Enables "all articles mentioning Company X" queries.

| Field | Type | Purpose |
|-------|------|---------|
| `entity_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `entity_type` | VARCHAR(64) NOT NULL | Type (e.g., "company", "person", "place", "product", "material", "method"). |
| `canonical_name` | VARCHAR(512) NOT NULL | Standardized name (e.g., "United States Steel Corporation"). For deduplication. |
| `alternate_names` | JSON NULL | Array of alternate names/spellings (e.g., `["U.S. Steel", "Carnegie Steel Company"]`). |
| `description` | TEXT NULL | What is this entity? (e.g., "Steel manufacturer founded 1901"). |
| `entity_first_mentioned_year` | SMALLINT UNSIGNED NULL | Earliest year mentioned in archive. |
| `entity_last_mentioned_year` | SMALLINT UNSIGNED NULL | Latest year mentioned. |
| `external_identifiers` | JSON NULL | References to external databases (e.g., `{"wikidata": "Q10943267", "loc": "n..."}}`). |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User (e.g., "entity_extractor"). |
| `updated_at` | DATETIME NULL | Timestamp. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(entity_type)`, `(entity_type, canonical_name)` UNIQUE, `(entity_first_mentioned_year)`, `(entity_last_mentioned_year)`

**Usage:** Link entities to segments via `segment_entities_t`. Answer "which articles discuss steel manufacturing?".

---

#### `segment_entities_t`
Many-to-many relationship: which entities are mentioned in which segments?

Tracks mention count and context for each entity-segment pair.

| Field | Type | Purpose |
|-------|------|---------|
| `link_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `segment_id` | BIGINT UNSIGNED NOT NULL | Foreign key → segments_t. |
| `entity_id` | BIGINT UNSIGNED NOT NULL | Foreign key → entities_t. |
| `mention_count` | INT UNSIGNED NOT NULL | How many times mentioned in this segment? |
| `mention_context` | JSON NULL | Additional context (e.g., `{"contexts": ["headline", "first_paragraph"]}`). |
| `created_at` | DATETIME | Timestamp. |
| `created_by` | VARCHAR(128) | User. |

**Indexes:** `(segment_id, entity_id)` UNIQUE, `(entity_id)`, `(created_at)`

**Usage:** Answer "articles by/about Company X". Enable faceted search.

---

#### `segment_assets_t`
Many-to-many relationship: which assets appear in which segments?

Tracks display order and whether asset is primary (primary assets display first).

| Field | Type | Purpose |
|-------|------|---------|
| `link_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `segment_id` | BIGINT UNSIGNED NOT NULL | Foreign key → segments_t. |
| `asset_id` | BIGINT UNSIGNED NOT NULL | Foreign key → assets_t. |
| `display_order` | INT UNSIGNED NULL | Ordinal position (1 = first, 2 = second, etc.). For layout. |
| `is_primary` | BOOLEAN NULL | TRUE if this is the main/featured image. |
| `created_at` | DATETIME | Timestamp. |

**Indexes:** `(segment_id, asset_id)` UNIQUE, `(asset_id)`, `(display_order)`

**Usage:** Determine which images appear in which articles and in what order. Critical for publishing/wiki display.

---

### TIER 4: RIGHTS & PUBLISHING (2 tables)

These tables handle public-domain rights evaluation and tracking of published outputs.

#### `rights_evaluations_t`
Records rights evaluations for publication instances.

Per RELEASE_POLICY, all instances must have a rights evaluation before publishing. Evaluations determine PD status and next review date.

| Field | Type | Purpose |
|-------|------|---------|
| `evaluation_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `instance_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_instances_t. Which instance was evaluated? |
| `rights_status` | ENUM('pd_cleared','restricted','unknown','disputed') | Result of evaluation. pd_cleared = safe to publish. restricted = cannot publish. unknown = requires research. disputed = conflicting opinions. |
| `pd_rule_applied` | VARCHAR(128) NULL | Which rule determined the status? E.g., "95-year rule", "published before 1928", "US government work". |
| `pd_rule_explanation` | TEXT NULL | Detailed reasoning (e.g., "Published 1876, now 2026. 95 years have passed. Therefore PD."). |
| `reviewer` | VARCHAR(128) NOT NULL | Human or system that performed evaluation. For accountability. |
| `evaluation_date` | DATE NOT NULL | When was evaluation made? |
| `next_review_date` | DATE NULL | When should this instance be re-evaluated? Per RELEASE_POLICY, rights are re-evaluated annually each January. |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | Timestamp. |

**Indexes:** `(instance_id)`, `(rights_status)`, `(next_review_date)`, `(evaluation_date)`

**Usage:** Publishing system checks rights status before publishing segments. QA dashboard shows which instances need re-review.

---

#### `publish_bundles_t`
Records published outputs: sets of segments and assets published together to MediaWiki.

A "bundle" is a coherent publication unit (typically one instance's segments + assets) published as a batch.

| Field | Type | Purpose |
|-------|------|---------|
| `bundle_id` | BIGINT UNSIGNED AUTO_INCREMENT | Primary key. |
| `instance_id` | BIGINT UNSIGNED NOT NULL | Foreign key → publication_instances_t. Which instance did this bundle publish? |
| `bundle_name` | VARCHAR(256) NOT NULL | Human-readable name (e.g., "American Architect Issue 1876-01-01"). |
| `segments_json` | JSON NOT NULL | Array of segment IDs published in this bundle. E.g., `[42, 43, 44]`. |
| `assets_json` | JSON NOT NULL | Array of asset IDs published in this bundle. E.g., `[1001, 1002]`. |
| `published_date` | DATETIME NOT NULL | When was bundle published to wiki? |
| `published_by` | VARCHAR(128) NOT NULL | User/system that published. |
| `wiki_status` | ENUM('draft','staged','published','failed','superseded') | draft = prepared but not published. staged = queued for publishing. published = live on wiki. failed = publishing error. superseded = newer version published. |
| `wiki_page_urls` | JSON NULL | Array of URLs of published wiki pages. E.g., `["https://wiki.cornerstonearchive.com/wiki/American_Architect_Issue_1876-01-01_Article1"]`. |
| `last_error` | TEXT NULL | If failed, what went wrong? |
| `notes` | TEXT NULL | Editorial notes. |
| `created_at` | DATETIME | When bundle record was created. |
| `created_by` | VARCHAR(128) | User. |
| `updated_at` | DATETIME NULL | When last updated. |
| `updated_by` | VARCHAR(128) NULL | User. |

**Indexes:** `(instance_id)`, `(published_date)`, `(wiki_status)`

**Usage:** Track publication history. Answer "has this instance been published?", "when was it published?", "what went wrong?".

---

## Usage Examples

### Example 1: Track an Instance Through the Pipeline

```sql
-- Find an instance
SELECT instance_id, family_id, title_id, instance_key, publication_year
FROM publication_instances_t
WHERE instance_key = 'AMER_ARCH_ISSUE_18760101_001_0001';

-- Find its containers
SELECT c.container_id, c.download_status, c.validation_status
FROM containers_t c
JOIN container_instances_t ci ON c.container_id = ci.container_id
WHERE ci.instance_id = 1;

-- Find its segments
SELECT segment_id, segment_type, title, workflow_state
FROM segments_t
WHERE instance_id = 1
ORDER BY page_start_in_container;

-- Check rights status
SELECT rights_status, pd_rule_applied, next_review_date
FROM rights_evaluations_t
WHERE instance_id = 1;

-- Check publishing status
SELECT bundle_id, wiki_status, published_date, wiki_page_urls
FROM publish_bundles_t
WHERE instance_id = 1;
```

### Example 2: Find Articles Mentioning a Company

```sql
-- Find the company entity
SELECT entity_id FROM entities_t WHERE canonical_name = 'United States Steel Corporation';

-- Find all segments mentioning it
SELECT s.segment_id, s.title, s.instance_id, se.mention_count
FROM segment_entities_t se
JOIN segments_t s ON se.segment_id = s.segment_id
WHERE se.entity_id = 123
ORDER BY s.instance_id;
```

### Example 3: QA: Find Segments Lacking OCR Text

```sql
SELECT segment_id, title, instance_id
FROM segments_t
WHERE ocr_text_cleaned IS NULL OR ocr_text_cleaned = ''
ORDER BY instance_id;
```

### Example 4: Monitor Processing Jobs

```sql
-- Find jobs in progress
SELECT job_id, job_type, target_ref, claimed_by_worker, started_at
FROM jobs_t
WHERE state = 'running'
ORDER BY started_at;

-- Find failed jobs
SELECT job_id, job_type, target_ref, last_error, attempts
FROM jobs_t
WHERE state = 'failed'
ORDER BY updated_at DESC;
```

---

## Notes

- All timestamps are in UTC (`SET time_zone = "+00:00"`).
- All tables use `utf8mb4_unicode_ci` collation for robust international text support.
- Foreign key constraints use `ON DELETE CASCADE` (parent deletion cascades) or `ON DELETE RESTRICT` (prevent deletion if children exist). Check specific constraints in schema.
- Audit logging is manual (application must insert into `audit_log_t`). No triggers.
- The schema supports multi-source ingestion: containers can come from Internet Archive, HathiTrust, local scans, etc.

---

## Future Migrations

To add new migrations:

1. Create a new file: `002_add_feature_xyz.sql`
2. Increment the version number
3. Test in dev first
4. Document in this README
5. Commit together with updated `database_migrations_t` insertion

All migrations should be idempotent (safe to re-run) and include rollback information.
