# Changelog

All notable changes to The Cornerstone Archive project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Database & Schema
- **Foundation schema migration** (`001_create_cornerstone_archive_foundation_schema.sql`)
  - Complete 17-table schema organized in 4 operational tiers
  - Tier 0: Operational (jobs_t, workers_t, audit_log_t, database_migrations_t)
  - Tier 1: Publication hierarchy (publication_families_t, publication_titles_t, publication_instances_t)
  - Tier 2: Content management (containers_t, container_instances_t, pages_t)
  - Tier 3: Processing pipeline (segments_t, assets_t, entities_t, segment_entities_t, segment_assets_t)
  - Tier 4: Rights & publishing (rights_evaluations_t, publish_bundles_t)
  - Applied to both development (`raneywor_csa_dev_state`) and production (`raneywor_csa_state`) databases
  - Schema validated for ENUM defaults, foreign keys, and collation (utf8mb4_unicode_ci)

- **Comprehensive migrations documentation** (`database/migrations/README.md`)
  - Complete schema dictionary with all 17 tables
  - Field-by-field explanations for every column
  - Index documentation and usage patterns
  - Instance key naming conventions by type (issue, volume, edition)
  - 4 detailed usage examples (pipeline tracking, entity lookup, QA queries, monitoring)
  - Notes on collation, timezone handling (UTC storage, CAT display conversion planned), foreign keys

#### Documentation
- **IMPLEMENTATION_ROADMAP.md** — Full 9-week project plan including:
  - Infrastructure setup details
  - Repository structure with all script files
  - Database schema overview
  - Watcher architecture and task state machine
  - Configuration management
  - Development workflow guidelines
  - Error handling and logging strategy
  - Troubleshooting procedures
  - Disaster recovery planning
  - Security considerations

- **README.md** — Updated with:
  - Project mission and context
  - Quick links (wiki, console, dev environments)
  - System architecture diagram (data flow)
  - Project status and timeline
  - Contributing guidelines
  - Reference to documentation structure

- **WEEK1_STATUS_UPDATED.md** — Week 1 completion summary
  - 85% completion status (as of Feb 4, 2026, 13:40 UTC)
  - Detailed checklist of completed infrastructure, GitHub setup, database work
  - Clear list of 4 remaining utilities needed
  - Estimated effort for completion

- **WEEK1_REMAINING_STEPS.md** — Actionable guide for completing Week 1
  - Detailed specifications for 4 foundational utilities:
    - `scripts/common/spec_config.py` (load/validate YAML config)
    - `scripts/common/spec_nas.py` (verify NAS accessibility)
    - `scripts/database/apply_migration.py` (apply migrations, record in database)
    - `scripts/ops/health_check.py` (monitor system health)
  - Function signatures and usage examples for each utility
  - Step-by-step implementation guidance
  - Testing commands and strategies
  - Ready-to-use commit message

#### Configuration & Testing
- **Configuration templates** (config/config.*.yaml, config/env.example)
  - Production config with correct HostGator settings (gator2111.hostgator.com, raneywor_csa_* prefixes)
  - Development config with debug logging and test mode enabled
  - Environment variable templates for credential management

- **Testing infrastructure**
  - requirements.txt with core dependencies (PyYAML, mysql-connector-python, pytest, Pillow, etc.)
  - requirements-dev.txt with development tools (black, flake8, mypy)
  - pytest.ini configured for test discovery and coverage reporting
  - tests/conftest.py with shared fixtures (config loader, test data)
  - Placeholder test structure (unit, integration, e2e, fixtures)
  - .github/workflows/tests.yml for CI/CD on push/PR to main and develop branches

#### Scripts & Utilities
- **scripts/common/spec_config.py** — Configuration loading and validation utility
  - `Config` class: Dict-like config object with validation and dot-notation access
  - `load_config()` function: Loads YAML files with recursive environment variable substitution (`${VAR_NAME}` and `${VAR_NAME:default}` syntax)
  - Comprehensive validation: environment (development/production), database credentials, logging levels, watcher intervals
  - Helpful error messages with context for troubleshooting
  - 19 unit tests | 94% code coverage

- **scripts/common/spec_nas.py** — NAS path utilities and validation
  - `NasManager` class: Manages NAS path construction following NAS_LAYOUT.md structure
  - Methods: `get_raw_path()`, `get_work_path()`, `get_logs_path()`, `get_reference_path()`, `get_publish_path()`, `get_state_path()`
  - Accessibility validation: `is_accessible()`, `is_writable()`
  - Directory creation: `create_work_dir()` with permission error handling
  - Verification: `verify_all_paths()` to check all 6 standard directories (00_STATE through 05_LOGS)
  - Windows-compatible path handling
  - 22 unit tests | 83% code coverage

- **scripts/common/spec_db.py** — MySQL database connection and query utilities
  - `Database` class: Connection pooling via mysql-connector-python with configurable pool size
  - Query methods: `query()` (SELECT, returns list of dicts), `get_one()` (single result or None)
  - Execution methods: `execute()` (INSERT/UPDATE/DELETE), `execute_many()` (batch operations)
  - Automatic retry logic: Up to 3 attempts with exponential backoff (1s, 2s, 4s delays)
  - Context manager support for automatic cleanup
  - Graceful error handling and logging
  - 18 unit tests | 90% code coverage

- **scripts/ops/verify_nas_paths.py** — NAS health check and monitoring script
  - Command-line utility: `python -m scripts.ops.verify_nas_paths [--config CONFIG] [--verbose]`
  - `verify_nas_paths()` function: Verifies all 6 standard NAS directories exist and are accessible
  - Disk space monitoring: Warns if <10% free, errors if <5% free
  - Human-readable report output with [OK], [WARN], [ERROR] status indicators
  - Exit codes: 0 (success), 1 (errors detected) for scripting/monitoring integration
  - Can be run manually or via Windows Task Scheduler for continuous health monitoring
  - 12 integration tests | 84% code coverage

#### Test Coverage Summary
- **Unit tests:** 56 tests across spec_config, spec_nas, spec_db (67 total passed, 4 skipped on Windows)
- **Integration tests:** 12 tests for verify_nas_paths (verify path accessibility, config handling, output formatting)
- **Overall coverage:** 88% across all new utility scripts
- **Total test code:** 1,003 lines of comprehensive test coverage (345 + 209 + 267 + 182 lines)
- **Production code:** 940 lines (189 + 185 + 285 + 281 lines)

- **.gitignore** — Project-specific patterns for:
  - Python artifacts (__pycache__, *.pyc, eggs, virtualenvs)
  - IDE/editor files (VS Code, Sublime, PyCharm)
  - Project files (config/*.yaml, .env, logs, scratch, *.bak, *.swp)
  - OS files (.DS_Store, Thumbs.db)

#### Project Structure
- **GitHub repository** created (https://github.com/RaneyMD/cornerstone_archive)
- **Directory structure** with 41 placeholder files organized by function:
  - scripts/ (watcher, common, stage1-4, database, ops, qa)
  - config/ (configuration templates)
  - database/migrations/ (SQL migrations)
  - web_console/ (PHP operations interface)
  - mcps/ (Model Context Protocol servers for Claude Code)
  - policies/ (governance documents)
  - docs/ (architecture and operational documentation)
  - tests/ (test suite organization)
  - templates/ (MediaWiki publishing templates)

### Fixed
- **IMPLEMENTATION_ROADMAP.md** — Corrected all Specification Collection references to Cornerstone Archive
  - Updated local clone path (spec-collection → cornerstone_archive)
  - Updated NAS root path and state machine diagram
  - Updated Week 1 database names in checklist
  - Maintained historical references (Project B origins) for clarity

### Changed
- **Database naming convention** — All databases and users use `raneywor_csa_*` prefix
  - Production: raneywor_csa_state, raneywor_csa_wiki
  - Development: raneywor_csa_dev_state, raneywor_csa_dev_wiki
  - App users: raneywor_csa_app (prod), raneywor_csa_dev (dev)
  - Admin users: raneywor_csa_admin (prod), raneywor_csa_dev_admin (dev)

- **Instance key design** — Changed from auto-generated to manually-assigned with templates
  - Issue template: `{FAMILY_CODE}_is_{YEAR}{MONTH}{DAY}_{VOLUME_SORT}_{ISSUE_SORT}`
  - Volume template: `{FAMILY_CODE}_vo_{VOLUME_SORT}_{YEAR}` (includes year for reprints)
  - Edition template: `{FAMILY_CODE}_ed_{YEAR}` (year only, edition may be unspecified)
  - Rationale: Flexibility for edge cases while maintaining deduplication safety

### Notes
- Timezone handling: All database timestamps stored in UTC. Application-layer conversion to CAT (Central Africa Time) to be implemented when building console and reporting tools.
- Instance key is manually assigned with UI template assistance, not auto-generated, to allow flexibility for edge cases.
- `publication_instances_t.part` instance type reserved for truly distinct parts (e.g., separate published treatise parts), not for supplementary content like advertisements (which should be tracked as page_type in pages_t).

---

## [0.1.0] — 2026-02-04

### Initial Release

**Status:** Week 1 Foundation Complete (85%)

Complete infrastructure and database foundation for digital preservation project digitizing American architecture and engineering publications from 1850–1920.

#### Infrastructure Delivered
- Production and development databases on HostGator with proper user segregation
- SSL-enabled subdomains for wiki and console (production and development)
- Landing page at cornerstonearchive.com
- GitHub repository initialized with directory structure and templates

#### Database Foundation
- 17-table schema designed for multi-stage publication processing pipeline
- Comprehensive documentation with schema dictionary and usage examples
- Migration framework in place for future schema evolution
- Migration recorded in database_migrations_t for auditability

#### Documentation
- Project roadmap (9-week implementation plan)
- Database schema reference with field-level explanations
- Week 1 status and remaining tasks for completion

#### Next Steps
- Build 4 foundational utilities (config loader, NAS checker, migration runner, health monitor)
- Begin Stage 1 implementation (Internet Archive acquisition)
- Establish watcher and processing pipeline

---

## Project Metadata

**Repository:** https://github.com/RaneyMD/cornerstone_archive  
**Project Lead:** Michael Raney  
**Infrastructure:** HostGator (MySQL, subdomains, PHP)  
**Local Processing:** OrionMX, OrionMega (Windows)  
**Network Storage:** RaneyHQ NAS (Cornerstone_Archive project folder)  
**Timeline:** 9 weeks (Week 1 started Feb 4, 2026)
