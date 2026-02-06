# Changelog

All notable changes to The Cornerstone Archive project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Supervisor Result Writing and Console Processing
- **Supervisor writes control flag results to Worker_Outbox**
  - New function: `write_result_file()` in supervisor/control_flow.py
  - Writes result JSON file for ALL control flag handlers:
    - pause_watcher, resume_watcher, restart_watcher
    - update_code, update_code_deps, rollback_code
    - diagnostics, verify_db
  - Covers both success cases and exception cases
  - Result file format: `supervisor_result_{handler}_{task_id}_{timestamp}.json`
  - Includes: task_id, handler name, success status, error message, timestamp, additional details
  - File written atomically (tmp-then-replace) to Worker_Outbox
  - Synology Cloud Sync monitors Worker_Outbox and syncs results to console_inbox

- **Console API endpoint to process results**
  - New endpoint: `/api/process_results.php`
  - Processes pending result files from console_inbox
  - Matches task_id to job_id in jobs_t table
  - Updates job status: `state` = 'succeeded' or 'failed'
  - Sets `finished_at` and `last_error` on job record
  - Inserts audit log entry with action 'JOB_COMPLETED'
  - Cleans up processed result files

- **Added CONSOLE_INBOX configuration**
  - New config constant: `CONSOLE_INBOX` (HostGator path)
  - Path where Synology Cloud Sync syncs supervisor results from Worker_Outbox
  - Configurable via environment variable: `CONSOLE_INBOX`

### Changed

#### Supervisor Code Update Dependencies Handler
- **pip install failures now fail the entire operation**
  - Previously: pip install errors were logged as warnings and operation continued as success
  - Now: pip install errors cause operation to fail with error message
  - Error message format: `"pip install failed: {stderr}"`
  - Watcher is still attempted to be restarted even on pip failure
  - Ensures console accurately tracks failed dependency updates

### Fixed

#### Supervisor Handler Audit Logging Schema
- **Fixed audit_log_t INSERT statements to use correct column names**
  - Issue: Handlers were using non-existent columns: `username`, `ip_address`, `details`, `timestamp`
  - Correct schema: `actor`, `action`, `target_type`, `target_id`, `details_json`, `created_at` (auto)
  - Fixed all handlers: pause_watcher, resume_watcher, update_code, update_code_deps, restart_watcher, rollback_code
  - Now properly records supervisor actions with target_type='supervisor_control', actor='supervisor'
  - Details stored as JSON in `details_json` column

#### Supervisor and Watcher Logging with Hourly Rotation
- **Fixed supervisor.log to write to NAS with hourly rotation and date-based organization**
  - Issue: Supervisor was writing logs to local `C:\cornerstone_archive\05_LOGS\supervisor.log` instead of NAS
  - Root cause: Path calculation in main() was using repo root instead of NAS path from config
  - Solution: Load config and NasManager early in main() to get correct NAS log path before setting up logging
  - Now logs correctly to: `\\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\supervisor.log`

- **Updated watcher.log to use hourly rotation (matching supervisor)**
  - Changed from size-based rotation (10MB per file, 30 backups) to hourly rotation
  - Log organization:
    - Active log: `watcher.log` (current hour)
    - Archived logs: `YYYY-MM-DD/watcher_HH.log` (past hours, organized by date)
    - Keeps 24 hours of history before cleanup
  - Provides consistent log organization across both processes
  - Easier to find logs for specific hours/days without huge active log files

#### Supervisor Control Handlers - Audit Logging
- **Fixed database method calls in all supervisor handlers**
  - Issue: All control handlers (pause_watcher, resume_watcher, update_code, update_code_deps, restart_watcher, rollback_code) were calling non-existent `db.insert()` method
  - Error message: `'Database' object has no attribute 'insert'`
  - Root cause: Handlers were written for console's Database class but supervisor uses different Database class from scripts.common.spec_db which only has `execute()` method
  - Solution: Replaced `db.insert()` calls with `db.execute()` using SQL INSERT statements with parameter tuples
  - Impact: Supervisor handlers still functioned (pause flag was created and respected), but audit logging was failing
  - Note: Pause mechanism was working despite audit errors - pause flag persisted and supervisor respected it on subsequent runs

### Added

#### Web Console - Authentication Foundation
- **Multi-watcher admin console** (`web_console/console_root/`)
  - Professional session-based authentication system
  - Login/logout with bcrypt password hashing
  - Session timeout validation and audit logging
  - Single entry point router with path traversal prevention

- **Core components:**
  - `index.php` — Main router with session validation
  - `auth/login.php` — Login form with credentials verification
  - `auth/logout.php` — Session cleanup with audit logging
  - `auth/session_check.php` — Reusable session validator
  - `app/Database.php` — PDO abstraction layer with prepared statements
  - `pages/dashboard.php` — Dashboard placeholder for multi-watcher monitoring

- **Frontend assets:**
  - `assets/css/style.css` — Bootstrap 5 customization with status badges
  - `assets/js/utils.js` — AJAX helpers, formatting utilities, alerts

- **Infrastructure:**
  - `.htaccess` — HTTPS enforcement, security headers (CSP, X-Frame-Options, etc.)
  - `config/config.example.php` — Configuration template with env var support
  - `README.md` — Setup guide, quick start, deployment checklist

- **Security features:**
  - SQL injection prevention (PDO prepared statements)
  - XSS prevention (htmlspecialchars output encoding)
  - Session security (HttpOnly, Secure flags, regeneration on login)
  - CSRF token support ready for POST endpoints
  - Audit logging for all authentication actions
  - Sensitive config files excluded from version control (`.gitignore`)

#### Web Console - Heartbeat Monitoring & AJAX APIs
- **Database-first heartbeat monitoring** (`app/NasMonitor.php`)
  - Read watcher heartbeat data from `workers_t` database table (replaces file-based approach)
  - Eliminates UNC path access issues on shared hosting
  - Determine freshness status (running, stale, offline) from database timestamps
  - Configurable thresholds for stale (2x poll interval) and dead (10 minutes)
  - ISO 8601 timestamp parsing and relative age calculation
  - Graceful error handling for missing/inaccessible data

- **Individual watcher management** (`app/Watcher.php`)
  - Query single watcher status from heartbeat + database
  - Fetch pending tasks and recent results per watcher
  - Retrieve watcher logs from database
  - Combine NAS heartbeat data with database state

- **Multi-watcher aggregation** (`app/WatcherManager.php`)
  - Manage 1-N watcher instances with single interface
  - Aggregate health summary (running, stale, offline counts)
  - Get system-wide pending task count
  - Broadcast control actions to watchers
  - Database and NAS connectivity status
  - Comprehensive system health snapshot

- **AJAX REST Endpoints:**
  - `api/heartbeat.php` — GET all watcher statuses (dashboard polling, 5s interval)
  - `api/watcher.php` — GET single watcher detail with tasks and logs
  - `api/tasks.php` — GET pending/recent task lists with filtering
  - `api/control.php` — POST control actions (restart, refresh, test task)
  - `api/logs.php` — GET recent watcher logs from database

#### Web Console - Real-time Dashboard
- **Dashboard JavaScript** (`assets/js/dashboard.js`)
  - AJAX polling: Refresh watcher status every 5 seconds (auto-refresh)
  - Real-time watcher status cards with color-coded badges
  - Status icons: ✓ (running), ⚠ (stale), ✗ (offline)
  - Health summary: Count running/stale/offline watchers
  - Modal dialogs for watcher detail view and logs
  - Control buttons: Restart, View Logs, View Detail per watcher
  - Pending task count display
  - Manual refresh button with last-refresh timestamp
  - Graceful error handling and user notifications

- **Updated Dashboard Page** (`pages/dashboard.php`)
  - Rendered watcher status cards with AJAX-driven updates
  - Health summary stat boxes (running, stale, offline, total)
  - Pending tasks widget with link to task management page
  - System status indicators (database, NAS)
  - Auto-refresh every 5 seconds (configurable)
  - Responsive Bootstrap 5 layout

- **Supervisor heartbeat cards** (`pages/dashboard.php`, `assets/js/dashboard.js`)
  - New "Supervisor Status" section showing status of each watcher's supervisor
  - Real-time updates every 5 seconds via AJAX polling
  - Status indicators: ✓ OK, ✗ Error, ⚠ Stale, ○ Offline
  - Displays last supervisor run time and status summary
  - New API endpoint: `/api/supervisor_heartbeat.php` queries `workers_t` for supervisor entries
  - Color-coded cards with status-based styling (green/red/yellow/gray)

- **Styling Enhancements** (`assets/css/style.css`)
  - Stat box styling for metrics display
  - Modal dialog customization
  - Responsive grid layout for stat boxes
  - Code block styling in modals
  - Supervisor card styling with status-based borders and backgrounds
  - Responsive grid layout for supervisor status details

#### Supervisor System
- **Core supervisor process** (`scripts/supervisor/supervisor.py`)
  - Single-pass execution model (runs once per Task Scheduler cycle)
  - Supervisor class with run_once() method
  - Configuration loading with environment validation
  - Graceful signal handling (SIGTERM, SIGINT)
  - Comprehensive logging (file + console, rotating 10MB max)

- **Control flag handlers** (`scripts/supervisor/handlers.py`)
  - `pause_watcher` — Create pause flag, gracefully stop watcher
  - `resume_watcher` — Delete pause flag, start watcher process
  - `update_code` — Git pull origin main with pre/post commit tracking
  - `update_code_deps` — Git pull + pip install requirements-dev.txt (dev environment)
  - `restart_watcher` — Stop and start watcher (respects pause flag)
  - `rollback_code` — Revert 1-10 commits with error handling and partial rollback support
  - `diagnostics` — Collect system state snapshot (process, heartbeat, DB, NAS, disk, logs)
  - `verify_database` — Test database connectivity, queries, table access, timezone

- **Supervisor utilities** (`scripts/supervisor/utils.py`)
  - Process management: check_watcher_process, stop_watcher_gracefully, start_watcher
  - Heartbeat analysis: is_watcher_healthy, is_watcher_paused, get_heartbeat_age_seconds
  - Command execution: run_command with timeout and output capture
  - Label validation: Alphanumeric, spaces, hyphens, underscores, max 100 chars
  - Pause flag management: create_pause_flag, delete_pause_flag
  - Git operations: get_current_commit, get_commit_log

- **Control flow orchestration** (`scripts/supervisor/control_flow.py`)
  - Scan Worker_Inbox for flag files in priority order
  - Priority-based handler execution (code updates before operational)
  - Flag JSON parsing with handler routing
  - Graceful error handling and flag cleanup

- **Heartbeat recording** (`scripts/supervisor/heartbeat.py`)
  - File-based heartbeat: supervisor_heartbeat_{worker_id}.json (atomic write)
  - Database heartbeat: UPDATE workers_t with status summary
  - Watcher heartbeat reading and validation

- **Configuration & validation** (`scripts/supervisor/config.py`)
  - Load supervisor config from YAML
  - Validate NAS paths, Worker_Inbox, Worker_Outbox accessibility
  - Environment validation with issue reporting

- **Flag-based control architecture:**
  - Flag files in Worker_Inbox as JSON with handler + params + optional label
  - Processing order: Code updates → Operational → Diagnostics
  - Automatic flag cleanup on success or failure
  - Optional labels (100 chars) for audit trail in logs and database

- **Dependencies:**
  - Added psutil>=5.9.0 to requirements.txt (process management)

#### Watcher Updates
- **Enhanced heartbeat reporting** (`scripts/watcher/spec_watcher.py`)
  - Updated `report_heartbeat()` to write full heartbeat fields to database
  - Write `pid`, `hostname`, `status`, `poll_seconds` to `workers_t` table
  - Uses INSERT ... ON DUPLICATE KEY UPDATE for reliable upserting
  - Maintains compatibility with existing heartbeat file writes

- **Supervisor pause flag support** (`scripts/watcher/spec_watcher.py`)
  - Check for `supervisor_pause_{worker_id}.flag` on each event loop iteration
  - Gracefully shut down when pause flag is detected (after current task completes)
  - Stop accepting new tasks until pause flag is removed
  - Pause detection latency: ~1 second (loop tick) + current task duration
  - Enables supervisor control via pause_watcher/resume_watcher handlers

#### Database & Schema

- **Extended workers_t heartbeat storage** (`002_extend_workers_t_heartbeat_fields.sql`)
  - Add `pid` (INT): Process ID of running watcher
  - Add `hostname` (VARCHAR): Hostname where watcher runs
  - Add `status` (VARCHAR): Current watcher status
  - Add `poll_seconds` (INT): Scan interval in seconds
  - Eliminates UNC path dependency on shared hosting
  - Enables database-first heartbeat reading for better reliability

### Changed

- **Console heartbeat source:** Now reads from `workers_t` database table instead of NAS JSON files
  - Solves UNC path access issues on HostGator shared hosting
  - More reliable: Data always in sync with database updates
  - Faster: Single database query vs. file I/O + JSON parsing
  - All AJAX endpoints updated to use database-backed NasMonitor

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

#### Watcher Automation
- **Prompt-driven Claude execution for the spec watcher** (`scripts/watcher/spec_watcher.py`, `prompts/README.md`)
  - Optional `--prompt-file` flow with model allowlist, timeout configuration, and dry-run support
  - Prompt file validation (exists, readable, size cap) with structured error handling
  - Claude invocation with JSON parsing that tolerates non-JSON prefixes
  - Prompt results recorded under `prompt_execution` in task payloads for downstream consumers
  - Unit tests covering prompt runner file validation, JSON parsing, timeouts, and integration behavior

### Added

#### Dashboard Control Panel Functionality
- **Control flag button event handlers** (`assets/js/dashboard.js`)
  - Wire up all control action buttons (Pause, Resume, Restart, Update Code, etc.)
  - Implement `createSupervisorFlag()` function to call `/api/create_flag.php`
  - Auto-refresh dashboard after successful flag creation
  - Clear label field after flag creation
  - Show success message with task_id for audit tracking
  - Proper error handling with user-friendly messages
  - Support for special parameters (e.g., rollback commits count)

#### Console Flag and Result Management System
- **Flag creation and tracking** (`console/flag_manager.py`)
  - `FlagManager` class: Create supervisor control and job task flags
  - Atomic flag writing to Worker_Inbox with JSON validation
  - Automatic task_id generation for console-created jobs
  - Database job record creation with audit trail support
  - Label validation and storage for operational context

- **Result file processing** (`console/result_processor.py`)
  - `ResultProcessor` class: Process result files from workers and supervisor
  - Map console task_id to job records for status updates
  - Handle both job results (success/error) and supervisor heartbeats
  - Archive processed results for audit trail
  - Support cleanup with optional archival

- **Flag utilities and validation** (`console/flag_utils.py`)
  - Task ID generation with console prefix
  - Label validation (100 chars, alphanumeric+hyphens/underscores/spaces)
  - Handler validation against allowed lists
  - Atomic file writing with temp-then-replace pattern
  - Supervisor handler whitelist: pause_watcher, resume_watcher, restart_watcher, update_code, update_code_deps, rollback_code, diagnostics, verify_db
  - Job handler whitelist: acquire_source

- **Web Console APIs for flag/result management**
  - `POST /api/create_flag.php` — Create supervisor control or job task flags
    - Request body: flag_type, handler, worker_id, label (optional), params (optional)
    - Response: success flag with task_id for tracking, or error message
  - `GET /api/get_job_status.php` — Query job/task status by ID
    - Parameters: task_id or job_id
    - Response: job state, created_at, updated_at, status_summary
  - `GET /api/list_jobs.php` — List jobs with filtering
    - Parameters: state (queued/running/succeeded/failed), limit, offset
    - Response: paginated job list with metadata
  - `GET /api/get_audit_log.php` — Retrieve audit trail
    - Parameters: target_id, action, limit, offset
    - Response: audit entries with actor, action, timestamp, details

- **Unit tests for console system**
  - `tests/unit/test_flag_manager.py` — FlagManager flag creation, validation, error handling
  - `tests/unit/test_result_processor.py` — ResultProcessor result processing and job updates

#### Database Schema
- **Add task_id field to jobs_t** (`004_add_task_id_to_jobs.sql`)
  - New `task_id` VARCHAR(128) column for console task tracking
  - Indexed for efficient result processing lookups
  - Enables mapping between console-generated task IDs and job records

#### Database Migration Runner
- **Migration execution and auditing** (`scripts/database/apply_migration.py`)
  - Read and execute SQL migrations from `database/migrations/` directory
  - Parse SQL statements with comment handling (single-line `--` and multi-line `/* */`)
  - Automatically detect admin credentials from environment variables
  - Use admin user for schema modifications (ALTER TABLE, ADD COLUMN)
  - Record migration metadata in `database_migrations_t`:
    - filename, checksum (SHA256), version number
    - applied_at (UTC timestamp), applied_by, status, error_message
  - Support individual migration execution or full batch
  - Idempotent: skip if migration already applied with 'applied' status
  - Record errors for audit trail and debugging

#### Job Task Labels for Audit Trail
- **Label field in jobs_t table** (`003_add_label_fields_to_jobs_and_workers.sql`)
  - Optional VARCHAR(100) label column for user-provided task descriptions
  - Example: "AA vol 1-2" for downloading American Architect volumes 1-2
  - Indexed for efficient filtering and audit queries
  - Stored in database for permanent audit trail

- **Label logging in watcher** (`scripts/watcher/spec_watcher.py`)
  - Extract label from task payload and include in all log messages
  - Format: `[TASK:123] Processing (AA vol 1-2)`
  - Recorded in result files (Worker_Outbox) for traceability
  - Improves log readability and task identification

#### Supervisor Auto-Restart
- **Watcher auto-restart on stopped detection** (`scripts/supervisor/supervisor.py`)
  - Supervisor now automatically restarts stopped watchers on each run
  - Unless watcher has been intentionally paused via `supervisor_pause_{worker_id}.flag`
  - Respects pause flag: won't restart if paused, will restart if paused flag is removed
  - Logs restart action and records in supervisor heartbeat for audit trail
  - Updates watcher_state to 'restarting' when auto-restart is initiated
  - Enables Task Scheduler to run supervisor periodically for automatic recovery

### Fixed

#### Console Control Flag Path Configuration
- **Define CONSOLE_OUTBOX for flag creation** (`config/config.example.php`)
  - CONSOLE_OUTBOX was undefined, causing create_flag.php to fail
  - Flags must be written to NAS_WORKER_INBOX (where supervisor reads them)
  - All supervisor control buttons now functional (Pause, Resume, Restart, etc.)
  - **Manual step required**: Update your local `config.php` to add:
    ```php
    define('CONSOLE_OUTBOX', NAS_WORKER_INBOX);
    ```

#### Web Console - Timezone Handling
- **Supervisor heartbeat timestamp calculation** (`api/supervisor_heartbeat.php`)
  - Fixed: Supervisor heartbeat was showing negative time (in future) due to UTC/local timezone mismatch
  - Root cause: Database stores DATETIME fields in UTC without timezone indicator; `strtotime()` was parsing them as local Central Time
  - Solution: Temporarily set timezone to UTC before parsing database timestamp, then restore original timezone
  - Result: Accurate age_seconds calculation regardless of server timezone or user's local timezone
  - Note: Watcher heartbeat calculation was already correct (uses DateTime with explicit UTC handling)

#### Supervisor Initialization
- **Database initialization** (`scripts/supervisor/supervisor.py`)
  - Fixed: Pass full config dict to Database instead of individual keyword arguments
  - Changed from: `Database(host=..., user=..., password=..., database=...)`
  - Changed to: `Database(db_config)` where db_config is the full database config dict
  - Database pool is initialized in __init__, removed unnecessary connect() call

- **Environment validation** (`scripts/supervisor/config.py`)
  - Fixed: validate_supervisor_environment() was trying to create NasManager with string path
  - Now accepts NasManager instance directly instead of state path
  - Removed directory tree walking logic, uses NasManager methods directly
  - Cleaner API contract, fewer error possibilities

- **NAS Manager initialization** (`scripts/supervisor/supervisor.py`)
  - Fixed: Supervisor was extracting nas_root string and passing to NasManager
  - NasManager expects full config dict, now passes self.config directly

#### Known Fixes
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

- **Task flow nomenclature and timezone handling** — Refactored watcher and Stage 1 scripts
  - Replaced task state directory structure with clear worker-console communication pattern:
    - `Worker_Inbox/` replaces `pending/` directory (incoming tasks from console)
    - `Worker_Outbox/` replaces `completed/` and `failed/` directories (results back to console)
    - Success results stored as `{task_id}.result.json`
    - Failure results stored as `{task_id}.error.json`
  - Added `get_worker_inbox_path()` and `get_worker_outbox_path()` methods to `NasManager`
  - Fixed timezone handling to ensure all timestamps are UTC:
    - `SET SESSION time_zone = '+00:00'` executed on pool initialization and every connection retrieval
    - Database timestamps always stored and retrieved in UTC regardless of system timezone
    - Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`
  - Updated `spec_watcher.py` to use new paths and UTC timestamps for heartbeat reporting
  - Updated `generate_ia_tasks.py` to write task flags to `Worker_Inbox/`
  - All unit tests updated and passing: 112 passed, 3 skipped

- **Watcher event loop and production health monitoring** — Single-instance lock + atomic heartbeat writes
  - **Event loop refactoring:**
    - Replaced blocking scan-then-sleep pattern with 1-second polling tick
    - Implemented time-gated intervals: scans only fire when `scan_interval_seconds` elapses, heartbeats when `heartbeat_interval_seconds` elapses
    - Configurable intervals via `watcher.scan_interval_seconds` (default: 30s) and `watcher.heartbeat_interval_seconds` (default: 300s)
    - Removed `dry_run` parameter from `run()` (moved to `main()` before lock acquisition)
    - Unconditional initial heartbeat fires before loop to ensure immediate visibility on startup
    - Max 1-second shutdown latency via sleep-then-check pattern
  - **Single-instance lock management (atomic filesystem-based):**
    - `acquire_lock()`: Creates lock directory in `00_STATE/locks/watcher_{worker_id}.lock/` using atomic `mkdir()` (fails with `FileExistsError` if held)
    - `release_lock()`: Idempotent cleanup (safe for repeated calls via `finally` block)
    - `write_lock_owner()`: Records process metadata to `owner.json` (pid, hostname, executable path, UTC timestamp)
    - Prevents multiple watcher instances on same worker_id
    - `handle_shutdown()` calls `release_lock()` on SIGTERM/SIGINT
  - **Production health monitoring:**
    - `write_heartbeat_file()`: Atomic tmp-then-replace JSON to `00_STATE/watcher_heartbeat_{worker_id}.json`
    - Heartbeat payload: worker_id, pid, hostname, status, UTC timestamp, poll interval
    - No `.tmp` files leak via atomic replace semantics
    - Combined with database heartbeat (`report_heartbeat()`) for dual monitoring
  - **Dry-run refactoring:**
    - Moved to `main()` before lock acquisition (scans once, prints task list, exits cleanly)
    - Renamed `_process_task()` → `process_task()` (no longer internal, public API)
    - Deleted `_report_heartbeat_if_needed()` (timing now managed by `run()` loop)
  - **Test coverage:** 8 new unit tests | 120 total passed, 3 skipped
    - `test_handle_shutdown_releases_lock`: Verifies shutdown → lock cleanup
    - `TestWatcherLocking` (4 tests): Lock acquisition, collision detection, release, owner.json validation
    - `TestWatcherHeartbeatFile` (1 test): Atomic file writes with proper cleanup
    - `TestWatcherEventLoop` (2 tests): Scan and heartbeat gates firing with mocked time
  - **Configuration updates:**
    - Development: `heartbeat_interval_seconds` set to 30 (faster feedback during testing)
    - Production: `heartbeat_interval_seconds` reduced from 300 to 30 (improved health monitoring visibility)
    - Both environments now report watcher health every 30 seconds via database and filesystem

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
