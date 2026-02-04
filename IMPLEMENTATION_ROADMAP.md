# The Cornerstone Archive
## Implementation Plan: Fresh Start with Proven Foundations

**Project Name:** The Cornerstone Archive  
**Repository:** New GitHub repo (`cornerstone_archive`)  

### Environment Domains

| Environment | Component | Domain | Purpose |
|-------------|-----------|--------|---------|
| **Production** | MediaWiki (public) | `www.cornerstonearchive.com` | Published knowledge base |
| **Production** | Console (ops) | `console.raneyworld.com` | Operational interface |
| **Development** | MediaWiki | `dev.raneyworld.com` | Testing & staging |
| **Development** | Console | `dev-console.raneyworld.com` | Dev operations interface |  
**Start Date:** February 2026  
**Target Milestone:** Stage 1 fully operational in dev environment  

---

## I. Infrastructure Setup (Week 1)

### Production Environment (cornerstonearchive.com + raneyworld.com)

**Hosting:** HostGator (existing account)

**Production MediaWiki:**
- Domain: `www.cornerstonearchive.com`
- Database: `raneywor_csa_wiki` (MySQL)
- Instance: Pristine MediaWiki (reusable from previous project)
- Access: Public (read-only for visitors)

**Production Console:**
- Domain: `console.raneyworld.com`
- Database: `raneywor_csa_state` (MySQL, shared with MediaWiki for task state)
- Access: Authenticated only (password-protected)
- Purpose: Operational interface for task management, monitoring, manual ingest

### Development Environment (dev.raneyworld.com + dev-console.raneyworld.com)

**Hosting:** HostGator (same account as production)

**Development MediaWiki:**
- Domain: `dev.raneyworld.com`
- Database: `raneywor_csa_dev_wiki` (MySQL)
- Instance: Clone of production MediaWiki
- Access: Open (testing only, not production data)

**Development Console:**
- Domain: `dev-console.raneyworld.com`
- Database: `raneywor_csa_dev_state` (MySQL, separate from prod)
- Access: Open (testing only)
- Purpose: Test operations interface, task handling, database integration

### Local Processing

**OrionMX:** Primary watcher, runs continuously
- Cloned repo at `C:\spec-collection\` or similar
- Config: `config/config.yaml` (production)
- Scratch: `C:\Scratch\NVMe\` (temporary processing)

**OrionMega:** Opportunistic burst processing
- Cloned repo at same path
- Config: `config/config.yaml` (shared or separate)

**NAS (RaneyHQ):** Workflow hub & authoritative storage
- Root: `\\RaneyHQ\Michael\02_Projects\Specification_Collection\`
- Structure follows Project A's NAS_LAYOUT.md approach:
  - `00_STATE` — project snapshots
  - `01_INTAKE` — source receipts
  - `02_WORK` — stable intermediate artifacts
  - `03_REFERENCE_PDF` — human reference PDFs
  - `04_PUBLISH_PAYLOADS` — publish bundles
  - `05_LOGS` — job logs
  - `06_COLD_STORAGE_INDEX` — archive index

---

## II. Repository Structure

### New Repository: `cornerstone_archive`

```
cornerstone_archive/
├── README.md
├── CHANGELOG.md
├── .gitignore
│
├── scripts/
│   ├── __init__.py
│   │
│   ├── watcher/
│   │   ├── __init__.py
│   │   ├── hjb_watcher.py (ORIGIN: Project B, port to "spec_watcher.py")
│   │   ├── handlers.py (ORIGIN: Project B handlers structure)
│   │   └── spec_watcher_tests.py (NEW)
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── spec_db.py (ORIGIN: Project B's hjb_db.py, renamed)
│   │   ├── spec_nas.py (NEW: NAS path utilities)
│   │   └── spec_config.py (NEW: configuration loading)
│   │
│   ├── stage1/
│   │   ├── __init__.py
│   │   ├── acquire_source.py (ORIGIN: Project B, refactored)
│   │   ├── generate_ia_tasks.py (ORIGIN: Project B)
│   │   ├── parse_ia_metadata.py (ORIGIN: Project B's parse_american_architect_ia.py)
│   │   └── stage1_tests.py (NEW)
│   │
│   ├── stage2/
│   │   ├── __init__.py
│   │   ├── extract_pages.py (NEW: based on Project B's extract_pages_v2.py concept)
│   │   ├── segment_works.py (NEW)
│   │   └── stage2_tests.py (NEW)
│   │
│   ├── stage3/
│   │   ├── __init__.py
│   │   └── dedup_works.py (NEW)
│   │
│   ├── stage4/
│   │   ├── __init__.py
│   │   └── publish_to_wiki.py (NEW)
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── apply_migration.py (NEW)
│   │   └── rollback_migration.py (NEW)
│   │
│   ├── ops/
│   │   ├── __init__.py
│   │   ├── verify_nas_paths.py (NEW)
│   │   └── health_check.py (NEW)
│   │
│   └── qa/
│       ├── __init__.py
│       └── generate_report.py (NEW)
│
├── config/
│   ├── config.example.yaml
│   ├── config.example.prod.yaml
│   └── config.example.dev.yaml
│
├── database/
│   └── migrations/
│       ├── 001_create_schema_foundation.sql
│       ├── 002_add_instance_keys.sql
│       ├── 003_create_hybrid_schema.sql
│       ├── 004_page_assets_and_manifests.sql
│       └── README.md
│
├── web_console/
│   └── console_root/
│       ├── index.php
│       ├── config/
│       │   └── config.example.php
│       ├── app/
│       │   ├── Auth.php (ORIGIN: Project B)
│       │   ├── Db.php (ORIGIN: Project B)
│       │   ├── Families.php (ORIGIN: Project B)
│       │   ├── Instances.php (ORIGIN: Project B)
│       │   ├── Jobs.php (ORIGIN: Project B)
│       │   ├── Titles.php (ORIGIN: Project B)
│       │   ├── Workers.php (ORIGIN: Project B)
│       │   ├── Util.php (ORIGIN: Project B)
│       │   └── Views.php (ORIGIN: Project B)
│       ├── assets/
│       │   └── console.css
│       └── pages/
│           ├── dashboard.php (NEW)
│           ├── jobs.php (ORIGIN: Project B)
│           ├── containers.php (NEW)
│           └── logs.php (NEW)
│
├── mcps/
│   ├── spec_mysql_mcp.py (ORIGIN: Project B's hjb_mysql_mcp.py, renamed)
│   └── spec_nas_mcp.py (ORIGIN: Project B's hjb_nas_mcp.py, renamed)
│
├── policies/
│   ├── QUALITY_POLICY.md (ORIGIN: Project A)
│   ├── RELEASE_POLICY.md (ORIGIN: Project A)
│   ├── RETENTION_POLICY.md (ORIGIN: Project A)
│   ├── TERMINOLOGY.md (ORIGIN: Project A)
│   └── NOMENCLATURE.md (ORIGIN: Project A's naming conventions)
│
├── docs/
│   ├── README.md (start here)
│   ├── ARCHITECTURE.md (NEW: overview + design decisions)
│   ├── DEVELOPMENT.md (NEW: how to work with the codebase)
│   ├── NAS_LAYOUT.md (ORIGIN: Project A)
│   ├── TESTING_STRATEGY.md (NEW)
│   ├── DEPLOYMENT.md (NEW)
│   ├── DATABASE_SCHEMA.md (NEW: schema reference)
│   ├── WATCHER_SYSTEM.md (NEW: orchestration details)
│   ├── STAGE1_RUNBOOK.md (NEW)
│   ├── TROUBLESHOOTING.md (NEW)
│   └── GLOSSARY.md (ORIGIN: Project A's TERMINOLOGY)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py (pytest configuration)
│   ├── fixtures/
│   │   └── sample_data.py
│   ├── unit/
│   │   ├── test_spec_db.py
│   │   ├── test_spec_nas.py
│   │   └── test_spec_config.py
│   ├── integration/
│   │   ├── test_watcher_full_cycle.py
│   │   ├── test_stage1_acquire.py
│   │   └── test_database_migrations.py
│   └── e2e/
│       └── test_end_to_end_container.py
│
├── requirements.txt (NEW)
├── requirements-dev.txt (NEW)
├── pytest.ini (NEW)
└── .github/
    └── workflows/
        └── tests.yml (NEW: CI/CD)
```

---

## III. Scripts to Port & Rename

### From Project B (hjb-project-main)

| Original File | New Name | Purpose | Status |
|---------------|----------|---------|--------|
| `scripts/watcher/hjb_watcher.py` | `scripts/watcher/spec_watcher.py` | Main orchestration loop | Port + refactor |
| `scripts/common/hjb_db.py` | `scripts/common/spec_db.py` | Database utilities | Port as-is |
| `scripts/stage1/acquire_source.ps1` | `scripts/stage1/handlers.py` (Python) | Fetch from Internet Archive | Convert PS1 → Python |
| `scripts/stage1/generate_ia_tasks.py` | `scripts/stage1/generate_ia_tasks.py` | Create task flags for IA | Port as-is |
| `scripts/stage1/parse_american_architect_ia.py` | `scripts/stage1/parse_ia_metadata.py` | Parse IA metadata | Port + generalize |
| `web_console/console_root/app/*.php` | `web_console/console_root/app/*.php` | Console components | Port as-is |
| `mcps/hjb_mysql_mcp.py` | `mcps/spec_mysql_mcp.py` | MySQL MCP for Claude Code | Rename + update |
| `mcps/hjb_nas_mcp.py` | `mcps/spec_nas_mcp.py` | NAS MCP for Claude Code | Rename + update |
| `database/migrations/*.sql` | `database/migrations/*.sql` | Schema evolution | Port as-is |

### From Project A (historical-journals-books-main)

| Original File | New Name | Purpose | Status |
|---------------|----------|---------|--------|
| `policies/QUALITY_POLICY.md` | `policies/QUALITY_POLICY.md` | Quality standards | Port as-is |
| `policies/RELEASE_POLICY.md` | `policies/RELEASE_POLICY.md` | Release criteria | Port as-is |
| `policies/RETENTION_POLICY.md` | `policies/RETENTION_POLICY.md` | Data retention | Port as-is |
| `policies/TERMINOLOGY.md` | `policies/TERMINOLOGY.md` | Glossary | Port as-is |
| `docs/NAS_LAYOUT.md` | `docs/NAS_LAYOUT.md` | NAS directory structure | Port + update paths |
| Naming conventions | `policies/NOMENCLATURE.md` | Naming standards | Extract + formalize |

### New Scripts (No Direct Origin)

| File | Purpose |
|------|---------|
| `scripts/common/spec_nas.py` | NAS path utilities & validation |
| `scripts/common/spec_config.py` | Configuration loading & validation |
| `scripts/stage2/extract_pages.py` | JP2 → JPEG conversion, OCR staging |
| `scripts/stage2/segment_works.py` | Parse OCR, find article boundaries |
| `scripts/stage3/dedup_works.py` | Deduplication & canonicalization |
| `scripts/stage4/publish_to_wiki.py` | Export to MediaWiki |
| `scripts/ops/verify_nas_paths.py` | NAS health check |
| `scripts/database/*.py` | Migration apply/rollback utilities |
| All test files | Testing infrastructure |

---

## IV. Configuration Management

### Configuration Files

**Production Config** (`config/config.yaml`)
```yaml
# Deployed to OrionMX and OrionMega
environment: production
database:
  host: cornerstonearchive.raneyworld.com
  database: raneywor_csa_state
  user: raneywor_csa_app
  password: ${DB_PASSWORD}

nas:
  root: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive
  scratch: C:\Scratch\NVMe

internet_archive:
  base_url: https://archive.org
  api_timeout_seconds: 30

logging:
  level: INFO
  path: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS

watcher:
  continuous_mode: true
  scan_interval_seconds: 30
  max_concurrent_tasks: 1
  heartbeat_interval_seconds: 300
```

**Development Config** (`config/config.dev.yaml`)
```yaml
# Used only on development machines
environment: development
database:
  host: cornerstonearchive.raneyworld.com
  database: cornerstone_archive_dev
  user: raneywor_csa_dev
  password: ${DB_PASSWORD_DEV}

nas:
  root: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive
  scratch: C:\Scratch\NVMe

internet_archive:
  base_url: https://archive.org
  api_timeout_seconds: 60
  rate_limit_per_second: 2

logging:
  level: DEBUG
  path: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\dev

watcher:
  continuous_mode: false
  test_mode: true
  max_concurrent_tasks: 1
```

### Environment Variables (Secrets Management)

Store sensitive values as environment variables, never in git:

```bash
# .env (local only, .gitignored)
DB_PASSWORD=your_production_password
DB_PASSWORD_DEV=your_dev_password
IA_API_KEY=optional_ia_key_if_needed
WIKI_API_PASSWORD=mediawiki_api_password
```

Load at startup:
```python
import os
from dotenv import load_dotenv

load_dotenv()
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

---

## V. Database Schema (From Project B)

### Foundation Tables (Stable)
```sql
publication_families_t
├─ family_id (PK)
├─ family_name (e.g., "American_Architect_family")
├─ description
└─ created_at

publication_titles_t
├─ title_id (PK)
├─ family_id (FK)
├─ title_name (e.g., "American Architect")
├─ publisher
├─ year_started
└─ notes

issues_t
├─ issue_id (PK)
├─ title_id (FK)
├─ volume
├─ number
├─ year_published
└─ date_published

containers_t
├─ container_id (PK)
├─ issue_id (FK)
├─ ia_identifier (e.g., "americanarchitect_1876_05")
├─ acquisition_status (pending, acquired, processing)
└─ acquired_at

pages_t
├─ page_id (PK)
├─ container_id (FK)
├─ page_number
├─ ocr_text (or NULL if using page packs)
└─ extracted_at

work_occurrences_t
├─ work_id (PK)
├─ page_id_start (FK to pages_t)
├─ page_id_end (FK to pages_t)
├─ work_type (article, advertisement, etc.)
├─ extracted_at
└─ extraction_metadata (JSON)
```

### Hybrid Schema Tables (Stage 2+)
```sql
page_assets_t (tracks extracted images & OCR)
├─ asset_id (PK)
├─ page_id (FK, UNIQUE)
├─ ocr_payload_path
├─ ocr_payload_hash (SHA256)
├─ image_extracted_path
├─ image_extracted_hash (SHA256)
├─ image_dpi_normalized
├─ extracted_at
└─ extraction_script_version

page_pack_manifests_t (documents page packs)
├─ manifest_id (PK)
├─ container_id (FK)
├─ manifest_path
├─ manifest_hash (SHA256)
├─ pages_count
├─ created_at
└─ manifest_version
```

---

## V. Watcher Architecture (From Project B, Refined)

### Task Flag Structure (JSON)
```json
{
  "task_id": "20260203_container_001_stage1",
  "container_id": 1,
  "stage": "stage1",
  "handler": "acquire_source",
  "params": {
    "ia_identifier": "americanarchitect_1876_05"
  },
  "created_at": "2026-02-03T10:00:00Z",
  "max_retries": 3,
  "timeout_seconds": 3600
}
```

### State Machine
```
\\RaneyHQ\Michael\02_Projects\Specification_Collection\0200_STATE\flags\

pending/
├─ <task_id>.flag      ← watcher discovers, scans continuously
↓
processing/
├─ <task_id>.flag      ← atomic rename (claim)
├─ <task_id>.log       ← live log output
├─ <task_id>.pid       ← process ID for monitoring
↓
completed/ OR failed/
├─ <task_id>.flag      ← final state
├─ <task_id>.log       ← full execution log
└─ <task_id>.json      ← result metadata (success/fail details)
```

### Handlers Registry (Python-based)
```python
HANDLERS = {
    "acquire_source": stage1.acquire_source,
    "extract_pages": stage2.extract_pages,
    "segment_works": stage2.segment_works,
    "dedup_works": stage3.dedup_works,
    "publish_to_wiki": stage4.publish_to_wiki,
    "noop": ops.noop,
}
```

---

## VII. Error Handling & Logging Strategy

### Task Failure Handling

**Graceful Degradation:**
- If a task fails, move it to `failed/` with full error details in `.json`
- Log the error with stack trace
- Continue processing next task in queue
- Do NOT crash the watcher

**Retry Logic:**
```json
{
  "task_id": "20260203_container_001_stage1",
  "handler": "acquire_source",
  "params": {"ia_identifier": "americanarchitect_1876_05"},
  "max_retries": 3,
  "retry_count": 0,
  "retry_delay_seconds": 60
}
```

**Failure Scenarios:**
| Scenario | Action | Logging |
|----------|--------|---------|
| Network timeout (IA down) | Retry with exponential backoff | WARN: "IA unreachable, retry #1 in 60s" |
| Database connection error | Retry once, then fail | ERROR: "DB connection failed, giving up" |
| Invalid input (bad IA ID) | Fail immediately, no retry | ERROR: "Invalid IA identifier format" |
| Out of disk space | Fail, alert operator | CRITICAL: "Scratch disk full, cannot continue" |
| Permission denied (NAS) | Fail, alert operator | CRITICAL: "NAS path not writable" |

### Logging Structure

**Standard Log Format:**
```
[2026-02-03T10:30:15.234Z] [TASK:container_001_stage1] [INFO] Starting acquire_source handler
[2026-02-03T10:30:16.456Z] [TASK:container_001_stage1] [DEBUG] Fetching IA metadata: americanarchitect_1876_05
[2026-02-03T10:30:18.789Z] [TASK:container_001_stage1] [INFO] Downloaded 42 JP2 files (1.2 GB)
[2026-02-03T10:30:20.012Z] [TASK:container_001_stage1] [INFO] Task completed successfully
```

**Log Files Location:**
```
\\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\jobs\
├─ <task_id>.log        (human-readable log)
├─ <task_id>.json       (machine-readable results)
└─ daily/
   └─ 2026-02-03.log    (rolled-up daily log)
```

### Monitoring & Alerting

**Health Check Script** (`scripts/ops/health_check.py`)
```bash
# Run daily via Task Scheduler
python -m scripts.ops.health_check --config config/config.yaml

# Checks:
# - Watcher process running
# - NAS paths accessible
# - Database reachable
# - Disk space > 10%
# - No stalled tasks (>24 hours in processing/)
```

**Alerting** (email via Microsoft 365)
```python
if disk_free_percent < 10:
    send_alert("CRITICAL: Disk space low ({}%)".format(disk_free_percent))

if stalled_tasks:
    send_alert("WARNING: {} tasks stalled in processing/".format(len(stalled_tasks)))

if last_successful_task_age_hours > 24:
    send_alert("WARNING: No successful tasks in 24 hours")
```

**Alert Recipients:**
- Primary: Michael Raney (your email)
- Fallback: Self (for testing)

---

## VIII. Development Workflow (Critical for Success)

### Prerequisites
- Local Git client
- Python 3.10+ on your development machine
- Access to dev HostGator databases

### Feature Development Cycle

**1. Create Feature Branch**
```bash
git checkout -b feature/stage2-extract-pages
```

**2. Write Test First**
```python
# tests/integration/test_stage2_extract.py
def test_extract_jp2_discovers_all_pages():
    """Verify JP2 discovery finds all pages in container."""
    # Arrange
    container = setup_test_container(container_id=1)
    
    # Act
    jp2_files = extract_pages.discover_jp2_files(container_id=1)
    
    # Assert
    assert len(jp2_files) == expected_count
    assert all(f.endswith('.jp2') for f in jp2_files)
```

**3. Implement Feature**
```python
def discover_jp2_files(container_id):
    """Find all JP2 files for a container."""
    container = db.get_container(container_id)
    ia_id = container['ia_identifier']
    # Implementation...
    return jp2_files
```

**4. Test Locally**
```bash
pytest tests/integration/test_stage2_extract.py::test_extract_jp2_discovers_all_pages -v
```

**5. Test in Dev Environment**
```bash
# Connect to dev database and NAS
python -m scripts.stage2.extract_pages \
    --config config/config.dev.yaml \
    --container-id 1 \
    --dry-run
```

**6. Review Output**
- Check dev database for new records
- Check dev NAS for extracted files
- Review logs for errors or warnings

**7. Create Pull Request**
- Write clear commit message (Conventional Commits style)
- Update CHANGELOG.md
- Request review (review your own work first)

**8. Merge to Main**
```bash
git checkout main
git pull origin main
git merge feature/stage2-extract-pages
git push origin main
```

**9. Production Deployment**
```bash
# On OrionMX
git pull origin main
pip install -r requirements.txt
supervisor restart spec_watcher
```

### Testing Hierarchy

**Unit Tests** (isolated functions)
- Database utilities
- NAS path construction
- Config loading
- Result parsing

**Integration Tests** (watcher + database + NAS)
- Acquire container from IA
- Parse metadata correctly
- Write to database
- Write to NAS
- Log operations

**End-to-End Tests** (full pipeline for one container)
- Stage 1: Acquire
- Stage 2: Extract pages
- Stage 3: Segment works
- Verify results in database and NAS

---

## VII. Implementation Roadmap

### Week 1: Infrastructure & Foundation
- [ ] Set up dev databases on HostGator (spec_collection_dev_wiki, spec_collection_dev_state)
- [ ] Set up dev subdomains (dev.raneyworld.com, dev-console.raneyworld.com)
- [ ] Create new GitHub repository
- [ ] Port database migrations from Project B
- [ ] Set up testing infrastructure (pytest, fixtures, conftest.py)

### Week 2-3: Watcher & Core Scripts
- [ ] Port spec_watcher.py from Project B's hjb_watcher.py
- [ ] Port spec_db.py from Project B's hjb_db.py
- [ ] Create spec_nas.py (NAS utilities)
- [ ] Create spec_config.py (config loading)
- [ ] Port stage1 scripts (acquire_source, generate_ia_tasks, parse_ia_metadata)
- [ ] Write unit tests for all utilities

### Week 4: Console & Operations
- [ ] Port PHP console components
- [ ] Set up console on dev-console.raneyworld.com
- [ ] Add authentication
- [ ] Create dashboard pages

### Week 5-6: Stage 2 Implementation (Extract Pages)
- [ ] Implement extract_pages.py
  - JP2 discovery
  - JP2 to JPEG conversion (Pillow)
  - OCR payload discovery
  - Page asset registration
- [ ] Write integration tests
- [ ] Test end-to-end with 1 container in dev

### Week 7-8: Testing & Documentation
- [ ] Add end-to-end tests for full pipeline
- [ ] Write DEVELOPMENT.md guide
- [ ] Write TROUBLESHOOTING.md
- [ ] Document all policies (from Project A)
- [ ] Prepare for production deployment

### Week 9+: Production Ready
- [ ] Production database migration
- [ ] Deploy watcher to OrionMX
- [ ] Deploy console to console.raneyworld.com
- [ ] Deploy wiki to www.cornerstonearchive.com
- [ ] Begin Stage 1 production runs

---

## VIII. Configuration Management

### Configuration Files

**Production Config** (`config/config.yaml`)
```yaml
# Deployed to OrionMX and OrionMega
environment: production
database:
  host: cornerstonearchive.raneyworld.com
  database: raneywor_csa_state
  user: raneywor_csa_app
  password: ${DB_PASSWORD}

nas:
  root: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive
  scratch: C:\Scratch\NVMe

internet_archive:
  base_url: https://archive.org
  api_timeout_seconds: 30

logging:
  level: INFO
  path: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS

watcher:
  continuous_mode: true
  scan_interval_seconds: 30
  max_concurrent_tasks: 1
  heartbeat_interval_seconds: 300
```

**Development Config** (`config/config.dev.yaml`)
```yaml
# Used only on development machines
environment: development
database:
  host: cornerstonearchive.raneyworld.com
  database: cornerstone_archive_dev
  user: raneywor_csa_dev
  password: ${DB_PASSWORD_DEV}

nas:
  root: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive
  scratch: C:\Scratch\NVMe

internet_archive:
  base_url: https://archive.org
  api_timeout_seconds: 60
  rate_limit_per_second: 2

logging:
  level: DEBUG
  path: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\dev

watcher:
  continuous_mode: false
  test_mode: true
  max_concurrent_tasks: 1
```

### Environment Variables (Secrets Management)

Store sensitive values as environment variables, never in git:

```bash
# .env (local only, .gitignored)
DB_PASSWORD=your_production_password
DB_PASSWORD_DEV=your_dev_password
IA_API_KEY=optional_ia_key_if_needed
WIKI_API_PASSWORD=mediawiki_api_password
```

Load at startup:
```python
import os
from dotenv import load_dotenv

load_dotenv()
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

---

## IX. Governance (From Project A)

### Naming Conventions
- **Publication families:** `{Name}_family` (e.g., `American_Architect_family`)
- **Database tables:** `{name}_t` (e.g., `containers_t`, `pages_t`)
- **Task handlers:** `{stage}_{action}` (e.g., `stage1_acquire_source`)
- **Config sections:** `[section_name]` in YAML

### Quality Standards (Project A's QUALITY_POLICY.md)
- All containers must have valid IA identifier
- All pages must have OCR text or OCR file reference
- No duplicate work entries in database
- All published works must be PD-cleared

### Release Criteria (Project A's RELEASE_POLICY.md)
- Code must have tests
- All tests must pass
- Commit messages must follow Conventional Commits
- Database migrations must be reversible
- Changes must be documented in CHANGELOG.md

### Data Retention (Project A's RETENTION_POLICY.md)
- Raw downloads (JP2/PDF): Keep until Stage 2 complete
- Working-layer intermediates: Keep until Stage 4 complete
- Reference PDFs: Keep indefinitely
- Logs: Keep 90 days
- Cold storage: Archive when no longer needed

---

## X. Operational Procedures

### Daily Health Check
```bash
python -m scripts.ops.verify_nas_paths
python -m scripts.ops.health_check --config config/config.yaml
```

### Creating a Task
```bash
# From operations console or manual flag creation
cat > \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\0200_STATE\flags\pending\task_20260203_001_stage1.flag << EOF
{
  "task_id": "20260203_001_stage1",
  "container_id": 1,
  "stage": "stage1",
  "handler": "acquire_source",
  "params": {"ia_identifier": "americanarchitect_1876_05"}
}
EOF
```

### Monitoring Progress
- Check console at console.raneyworld.com
- View logs in `05_LOGS/jobs/`
- Query database: `SELECT * FROM containers_t WHERE container_id = 1;`

### Troubleshooting
- See `docs/TROUBLESHOOTING.md`
- Check watcher logs on OrionMX
- Verify NAS paths are accessible
- Check database connection

---

## XI. Error Handling & Logging Strategy

### Task Failure Handling

**Graceful Degradation:**
- If a task fails, move it to `failed/` with full error details in `.json`
- Log the error with stack trace
- Continue processing next task in queue
- Do NOT crash the watcher

**Retry Logic:**
```json
{
  "task_id": "20260203_container_001_stage1",
  "handler": "acquire_source",
  "params": {"ia_identifier": "americanarchitect_1876_05"},
  "max_retries": 3,
  "retry_count": 0,
  "retry_delay_seconds": 60
}
```

**Failure Scenarios:**
| Scenario | Action | Logging |
|----------|--------|---------|
| Network timeout (IA down) | Retry with exponential backoff | WARN: "IA unreachable, retry #1 in 60s" |
| Database connection error | Retry once, then fail | ERROR: "DB connection failed, giving up" |
| Invalid input (bad IA ID) | Fail immediately, no retry | ERROR: "Invalid IA identifier format" |
| Out of disk space | Fail, alert operator | CRITICAL: "Scratch disk full, cannot continue" |
| Permission denied (NAS) | Fail, alert operator | CRITICAL: "NAS path not writable" |

### Logging Structure

**Standard Log Format:**
```
[2026-02-03T10:30:15.234Z] [TASK:container_001_stage1] [INFO] Starting acquire_source handler
[2026-02-03T10:30:16.456Z] [TASK:container_001_stage1] [DEBUG] Fetching IA metadata: americanarchitect_1876_05
[2026-02-03T10:30:18.789Z] [TASK:container_001_stage1] [INFO] Downloaded 42 JP2 files (1.2 GB)
[2026-02-03T10:30:20.012Z] [TASK:container_001_stage1] [INFO] Task completed successfully
```

**Log Files Location:**
```
\\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\jobs\
├─ <task_id>.log        (human-readable log)
├─ <task_id>.json       (machine-readable results)
└─ daily/
   └─ 2026-02-03.log    (rolled-up daily log)
```

### Monitoring & Alerting

**Health Check Script** (`scripts/ops/health_check.py`)
```bash
# Run daily via Task Scheduler
python -m scripts.ops.health_check --config config/config.yaml

# Checks:
# - Watcher process running
# - NAS paths accessible
# - Database reachable
# - Disk space > 10%
# - No stalled tasks (>24 hours in processing/)
```

**Alerting** (email via Microsoft 365)
```python
if disk_free_percent < 10:
    send_alert("CRITICAL: Disk space low ({}%)".format(disk_free_percent))

if stalled_tasks:
    send_alert("WARNING: {} tasks stalled in processing/".format(len(stalled_tasks)))

if last_successful_task_age_hours > 24:
    send_alert("WARNING: No successful tasks in 24 hours")
```

**Alert Recipients:**
- Primary: Michael Raney (your email)
- Fallback: Self (for testing)

---

## XII. Success Criteria

### Phase 1 Complete (End of Week 1)
- [ ] Dev and prod infrastructure live on HostGator
- [ ] GitHub repo created and populated
- [ ] Database migrations applied to dev database

### Phase 2 Complete (End of Week 4)
- [ ] Watcher running on OrionMX (production)
- [ ] Console accessible at console.raneyworld.com
- [ ] Can manually create and execute tasks

### Phase 3 Complete (End of Week 6)
- [ ] Stage 1 (acquire_source) working end-to-end in dev
- [ ] Stage 2 (extract_pages) working end-to-end in dev with 1 container
- [ ] All unit and integration tests passing

### Phase 4 Complete (End of Week 9)
- [ ] Full pipeline tested with 5 containers in dev
- [ ] All documentation complete
- [ ] Production ready for Stage 1 launch

---

## XIII. Troubleshooting & Common Issues

### Watcher Won't Start

**Symptom:** `spec_watcher.py` crashes on startup

**Diagnosis:**
```bash
# Check for syntax errors
python -m py_compile scripts/watcher/spec_watcher.py

# Run watcher with verbose output
python scripts/watcher/spec_watcher.py --verbose --config config/config.yaml
```

**Common Causes:**
1. **Config file missing or invalid YAML**
   - Solution: Verify `config/config.yaml` exists and is valid YAML
   - Test: `python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"`

2. **Database credentials incorrect**
   - Solution: Test connection with database utilities
   - Test: `python -m scripts.common.spec_db --test-connection`

3. **NAS paths not accessible**
   - Solution: Map NAS drive, verify permissions
   - Test: `python -m scripts.ops.verify_nas_paths`

### Tasks Stuck in Processing

**Symptom:** Task remains in `processing/` for hours, hasn't completed or failed

**Diagnosis:**
```bash
# Check if process is still running
Get-Process -Name python | Where-Object {$_.CommandLine -like "*spec_watcher*"}

# Check task log
type \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\0200_STATE\flags\processing\<task_id>.log
```

**Solutions:**
1. **Process crashed silently** — kill process, move task to failed/, check logs
2. **Deadlock in database** — restart database connection, move task to pending/
3. **Network timeout** — increase timeout in config, move task to pending/ for retry

### Database Migration Failed

**Symptom:** Migration script exits with error, database in inconsistent state

**Prevention:**
```bash
# Always test migrations in dev first
python -m scripts.database.apply_migration \
    --config config/config.dev.yaml \
    --migration database/migrations/001_create_schema_foundation.sql

# Verify schema
mysql -h host -u user -p database < /dev/stdin << EOF
SHOW TABLES;
DESCRIBE containers_t;
EOF
```

**Recovery:**
```bash
# Rollback (keep rollback scripts alongside migrations)
python -m scripts.database.apply_migration \
    --config config/config.yaml \
    --migration database/migrations/001_create_schema_foundation.sql.rollback \
    --direction DOWN
```

### Extract Pages Script Fails

**Symptom:** `extract_pages.py` crashes when processing a container

**Common Causes:**

| Error | Cause | Solution |
|-------|-------|----------|
| `FileNotFoundError: No JP2 files found` | IA identifier wrong or container not downloaded | Verify IA ID, check raw layer |
| `PIL ImportError` | Pillow not installed | `pip install pillow` |
| `Permission denied (NAS path)` | No write access to page pack directory | Verify NAS permissions |
| `OutOfMemoryError` | Large JP2 converting to JPEG | Process in batches, increase memory |
| `Timeout downloading OCR` | IA slow or down | Retry, check IA status |

**Debug Script:**
```python
# scripts/ops/debug_container.py
python -m scripts.ops.debug_container \
    --config config/config.yaml \
    --container-id 1 \
    --verbose
```

This will:
- Check if container exists in database
- List raw files on NAS
- Test JP2 discovery
- Test OCR file discovery
- Test image conversion on 1 sample page

### NAS Path Construction Issues

**Symptom:** "Path not found" errors even though file exists

**Debug:**
```python
# Test path construction
from scripts.common import spec_nas

container_id = 1
raw_path = spec_nas.get_raw_path(container_id)
work_path = spec_nas.get_work_path(container_id)
logs_path = spec_nas.get_logs_path()

print(f"Raw: {raw_path}")
print(f"Work: {work_path}")
print(f"Logs: {logs_path}")

# Verify paths are accessible
import os
assert os.path.exists(raw_path), f"Raw path not found: {raw_path}"
assert os.path.exists(work_path), f"Work path not found: {work_path}"
```

### Console Won't Load

**Symptom:** `console.raneyworld.com` returns 500 error or blank page

**Diagnosis:**
```bash
# Check PHP error logs (on HostGator)
tail -f /var/log/php-errors.log

# Check database connection
php web_console/console_root/mysql_test.php
```

**Common Causes:**
1. **Database credentials in config wrong** — update `web_console/console_root/config/config.php`
2. **Database doesn't exist** — create via HostGator cPanel
3. **PHP version mismatch** — check PHP version compatibility

### Performance Degradation

**Symptom:** Watcher gets slower over time, or database queries timeout

**Diagnosis:**
```sql
-- Check database size
SELECT 
  table_name,
  ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
FROM information_schema.TABLES
WHERE table_schema = 'raneywor_csa_state'
ORDER BY size_mb DESC;

-- Check for missing indexes
EXPLAIN SELECT * FROM pages_t WHERE container_id = 1;
```

**Solutions:**
1. **Add indexes** if query plans show full table scans
2. **Archive old logs** from `05_LOGS` to cold storage
3. **Partition large tables** (pages_t, work_occurrences_t)
4. **Increase MySQL buffer pool** in HostGator cPanel

---

## XIV. Maintenance & Operations Schedule

### Daily
- [ ] Check console for failed tasks
- [ ] Review watcher logs for errors
- [ ] Verify NAS connectivity

### Weekly
- [ ] Run `health_check.py`
- [ ] Review database size
- [ ] Test backup/restore procedure

### Monthly
- [ ] Audit access logs (console usage)
- [ ] Check cold storage status
- [ ] Performance review (task completion times)

### Quarterly
- [ ] Database maintenance (optimize, defrag)
- [ ] Schema review (are tables normalized properly?)
- [ ] Update documentation

---

## XV. Disaster Recovery

### Backup Strategy

**What to Back Up:**
- Database (full backup weekly, incremental daily)
- NAS working layer (weekly snapshots)
- Configuration files (config.yaml, secrets)

**What NOT to Back Up:**
- Raw layer (authoritative in IA)
- Logs older than 90 days
- Temporary scratch files

**Backup Schedule:**
```
Daily:     Incremental database backup (automated by HostGator)
Weekly:    Full database backup + NAS snapshot (Synology scheduled task)
Monthly:   Export to cold storage
```

### Recovery Procedures

**Recover from Database Corruption:**
1. Stop watcher
2. Restore database from last known-good backup
3. Check NAS for completed tasks
4. Re-register any tasks that were in-flight
5. Restart watcher

**Recover from Lost NAS Volume:**
1. Restore from Synology backup (if available)
2. Re-run Stage 1 for affected containers (data re-downloads from IA)
3. Re-run Stage 2 (re-extract pages)
4. Verify database consistency with actual files

**Recover from Corrupted Task Queue:**
1. Check `failed/` directory for clues
2. Manually inspect `pending/` and `processing/` flags
3. Move bad flags to quarantine directory
4. Restart watcher
5. Manually re-create failed tasks

---

## XVI. Security Considerations

### Access Control

**Console Authentication:**
- Username/password required for all operations
- Consider IP allowlist if possible (lock to your network)
- Session timeout: 30 minutes of inactivity

**Database Access:**
- Two-user model: admin (you) + application (watcher)
- Application user has INSERT/UPDATE/SELECT only (no DROP/ALTER)
- All credentials in environment variables, not config files

**NAS Access:**
- Windows user account for watcher process
- Permissions: read/write to working layer, read-only to intake layer
- Audit log enabled for sensitive operations

### Data Protection

**In Transit:**
- HTTPS for web console (HostGator provides SSL)
- SMB signing enabled for NAS (Windows feature)

**At Rest:**
- Database: no special encryption (HostGator provides security)
- NAS: Synology built-in encryption if enabled
- Backups: encrypted before sending to cold storage

### Secret Management

**Do NOT commit to git:**
- Database passwords
- API keys
- Wiki admin passwords

**Store in:**
- Environment variables (`$DB_PASSWORD`, etc.)
- `.env` file (local only, .gitignored)
- HostGator cPanel environment settings
- Windows Registry (for local scripts)

---

## XVII. Integration Points & Future Extensions

### MediaWiki Integration

**Current:** Manual publishing to wiki by you  
**Future:** Automated via `publish_to_wiki.py` handler

```python
# Handler that auto-publishes completed works
def stage4_publish_to_wiki(task):
    work_id = task['params']['work_id']
    work = db.get_work(work_id)
    
    # Format as wikitext
    wikitext = format_work_as_wikitext(work)
    
    # Create/update page
    wiki.create_page(
        title=work['title'],
        content=wikitext,
        summary=f"Auto-published from {task['task_id']}"
    )
    
    return {"pages_created": 1}
```

### Internet Archive Integration

**Current:** One-way pull (download from IA)  
**Future Possibilities:**
- Sync back corrected OCR
- Report deduplication results
- Contribute structured metadata

### External Data Sources

**Possible integrations:**
- HathiTrust (another journal source)
- Library of Congress (for cross-referencing)
- WorldCat (bibliographic lookup)
- Project Gutenberg (contextual texts)

---

### Phase 1 Complete (End of Week 1)
- [ ] Dev and prod infrastructure live on HostGator
- [ ] GitHub repo created and populated
- [ ] Database migrations applied to dev database

### Phase 2 Complete (End of Week 4)
- [ ] Watcher running on OrionMX (production)
- [ ] Console accessible at console.raneyworld.com
- [ ] Can manually create and execute tasks

### Phase 3 Complete (End of Week 6)
- [ ] Stage 1 (acquire_source) working end-to-end in dev
- [ ] Stage 2 (extract_pages) working end-to-end in dev with 1 container
- [ ] All unit and integration tests passing

### Phase 4 Complete (End of Week 9)
- [ ] Full pipeline tested with 5 containers in dev
- [ ] All documentation complete
- [ ] Production ready for Stage 1 launch

---

## XVIII. Key Differences from Previous Attempts

### Problem: No Dev Environment
**Solution:** Complete dev infrastructure on HostGator (separate databases, subdomains). All code tested in dev before production deployment.

### Problem: Large Refactors Broke Other Code
**Solution:** Small, testable changes (50-100 LOC per PR). Tests written first. Review process before merge.

### Problem: Gaps Between Specs & Implementation
**Solution:** Combine Project A's governance (policies, nomenclature) with Project B's pragmatic code. Write tests to bridge gaps.

### Problem: Unclear What Worked & What Didn't
**Solution:** Clear script origins (renamed from Project B with documented ports). Separate governance (Project A policies). Clear testing strategy upfront.

---

## XIX. Next Steps

1. **Confirm** this plan aligns with your vision
2. **Set up** dev infrastructure on HostGator (subdomains + databases)
3. **Create** new GitHub repository
4. **Begin** Week 1 tasks (port database migrations, set up testing)
5. **Schedule** review checkpoints (end of each week)

---

**Prepared by:** Claude  
**Date:** February 3, 2026  
**Status:** Ready for implementation  
**Owner:** Michael Raney
