# Claude Code Prompt: Supervisor System for Cornerstone Archive
## Implementation based on revised flag architecture and operational feedback

---

## PROJECT CONTEXT

**Repository:** cornerstone_archive (GitHub, RaneyMD)  
**Purpose:** Implement supervisor process that monitors watcher health and processes control flags  
**Current Status:** Supervisor architecture designed; ready for implementation  
**Environment:** Development (dev)  
**Integration:** Supervisor runs continuously on OrionMX via Windows Task Scheduler; communicates with watcher through NAS and database using dev configuration

---

## SUPERVISOR ARCHITECTURE OVERVIEW

### How Supervisor Operates
```
Task Scheduler (every 2-3 minutes)
  → Run supervisor.py --worker-id OrionMX --config config.dev.yaml
  → Check watcher health
  → Process control flags from Worker_Inbox
  → Record heartbeat to database
  → Exit and wait for next cycle

Control Flags (placed by operator):
  Worker_Inbox/ ← Supervisor checks here for flag files
    supervisor_pause_OrionMX.flag
    supervisor_resume_OrionMX.flag
    supervisor_update_code_OrionMX.flag
    supervisor_rollback_code_OrionMX.flag
    supervisor_diagnostics_OrionMX.flag
    supervisor_restart_watcher_OrionMX.flag
    supervisor_verify_db_OrionMX.flag

Results/Feedback:
  Worker_Outbox/ ← Some handlers write results here
  watcher_heartbeat_OrionMX.json ← Watcher status
  supervisor_heartbeat_*.json ← Supervisor status (file-based, atomic writes)
  05_LOGS/diagnostics/ ← Diagnostic reports
```

---

## DELIVERABLES

### 1. Main Supervisor Script
**File:** `scripts/supervisor/supervisor.py`

**Responsibilities:**
- Initialize supervisor with worker ID and dev config
- Implement main event loop (run once per Task Scheduler cycle)
- Check for control flags from Worker_Inbox
- Execute handlers based on flags
- Record supervisor heartbeat to database
- Record supervisor heartbeat to filesystem (atomic write)
- Graceful signal handling (SIGTERM, SIGINT)
- Comprehensive logging

**Key Classes/Functions:**
```python
class Supervisor:
    def __init__(self, config_path: str, worker_id: str = "OrionMX")
    def run_once(self) -> int
    def check_watcher_health(self) -> dict
    def report_heartbeat_to_database(self) -> None
    def write_heartbeat_file(self) -> None

def main(args=None) -> int
```

**Key Features:**
- Load dev config (YAML + environment variable substitution)
- Initialize NasManager and Database using dev environment settings
- Single-pass execution model (run once, exit, let Task Scheduler reschedule)
- Process control flags in priority order:
  1. Emergency/high-priority flags first
  2. Code update flags
  3. Operational flags (pause, restart, etc.)
- Exit code: 0 (success), 1 (error)

---

### 2. Control Flag Handlers
**File:** `scripts/supervisor/handlers.py`

**Implement these handlers:**

#### Handler: pause_watcher
```python
def pause_watcher(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Check if pause flag exists
- If not: create pause flag at `00_STATE/supervisor_pause_{worker_id}.flag`
- Stop watcher gracefully (allow in-flight tasks to complete)
- Log action (include optional label if provided)
- Record in audit_log_t (including label)

#### Handler: resume_watcher
```python
def resume_watcher(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Delete pause flag
- Start watcher (create new process via Python)
- Log action (include optional label if provided)
- Record in audit_log_t (including label)

#### Handler: update_code
```python
def update_code(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Stop watcher gracefully
- Change to repo directory: `C:\cornerstone_archive`
- Run: `git pull origin main`
- On success: start watcher
- Log all output (include optional label if provided)
- Record in audit_log_t (including label)

#### Handler: update_code_deps
```python
def update_code_deps(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Stop watcher gracefully
- Change to repo directory
- Run: `git pull origin main`
- Run: `pip install -r requirements.txt --break-system-packages`
- On success: start watcher
- Log all output (include optional label if provided)
- Record in audit_log_t (including label)

#### Handler: restart_watcher
```python
def restart_watcher(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Stop watcher gracefully
- Wait 2 seconds
- Start watcher
- If pause flag is set, leave it (watcher will start paused)
- Log action (include optional label if provided)
- Record in audit_log_t (including label)

#### Handler: rollback_code
```python
def rollback_code(task: dict, nas: NasManager, db: Database, worker_id: str) -> dict
```
- Extract `commits_back` parameter from task (int, 1-10, default 1)
- Validate parameter range
- Stop watcher gracefully
- Change to repo directory
- Get current commit (git rev-parse --short HEAD)
- Get log of commits to revert (git log --oneline -n{commits_back})
- For each commit:
  - Run: `git revert --no-edit HEAD`
  - If fails: stop trying, report which one failed
  - If succeeds: continue to next
- Get final commit (git rev-parse --short HEAD)
- Start watcher (regardless of revert success)
- Record detailed results in audit_log_t (including optional label if provided):
  - commits_reverted (integer)
  - reverted_commits (list)
  - final_commit (string)
  - success (boolean)
  - error (if failed)
  - label (if provided)

#### Handler: diagnostics
```python
def generate_diagnostics(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Collect system state:
  - Watcher process status (running, PID, memory, CPU, uptime)
  - Watcher heartbeat (fresh? healthy? paused?)
  - Database connectivity test (SELECT NOW())
  - NAS path accessibility (all 6 standard paths)
  - Disk space (total, used, free, % free)
  - Recent logs (last 50 lines from watcher.log)
  - Pending tasks (files in Worker_Inbox)
  - Recent audit log entries (last 10)
- Write to: `05_LOGS/diagnostics/diagnostics_{worker_id}_{timestamp}.json`
- Return result dict with path to report (include optional label if provided in filename or report)

#### Handler: verify_db
```python
def verify_database(nas: NasManager, db: Database, worker_id: str, task: dict) -> dict
```
- Test 1: Connection
  - Try to create and close connection
  - Report success/failure
- Test 2: Query
  - Run: SELECT NOW() as db_time, DATABASE() as db_name
  - Report success/failure/data
- Test 3: Table accessibility
  - For each critical table (containers_t, jobs_t, workers_t, segments_t):
    - Run: SELECT COUNT(*) FROM {table}
    - Report success/failure
- Test 4: Timezone
  - Run: SELECT @@session.time_zone as tz
  - Verify is +00:00 (UTC)
- Write report to: `05_LOGS/diagnostics/db_verification_{worker_id}_{timestamp}.json`
- Return dict with all test results (include optional label if provided in report)

---

### 3. Utility Functions
**File:** `scripts/supervisor/utils.py`

**Implement these utilities:**

```python
def check_watcher_process(worker_id: str) -> bool:
    """Check if watcher process is currently running."""
    # psutil.Process lookup by name
    # Return True if running, False otherwise

def is_watcher_healthy(heartbeat: dict) -> bool:
    """Determine if watcher heartbeat indicates healthy state."""
    # Check: heartbeat age < 5 minutes
    # Check: status field == "healthy" or similar
    # Check: no recent error messages
    # Return True if all OK

def is_watcher_paused(nas: NasManager, worker_id: str) -> bool:
    """Check if pause flag exists."""
    # Check: 00_STATE/supervisor_pause_{worker_id}.flag exists
    # Return True if exists

def read_heartbeat_file(path: Path) -> dict:
    """Read and parse heartbeat JSON file."""
    # Load JSON
    # Return dict
    # Handle missing/invalid file gracefully

def stop_watcher_gracefully(worker_id: str, timeout_seconds: int = 30) -> bool:
    """Stop watcher process gracefully."""
    # Find watcher process by name
    # Send SIGTERM (graceful shutdown)
    # Wait up to timeout_seconds for process to exit
    # If still running: SIGKILL
    # Return True if stopped, False if timeout

def start_watcher(worker_id: str = "OrionMX", config_path: str = "config.dev.yaml") -> bool:
    """Start watcher process with dev config."""
    # Change to repo directory
    # Run: python -m scripts.watcher.spec_watcher --config {config_path} --worker-id {worker_id}
    # Run in background (subprocess.Popen)
    # Return True if process started, False if failure

def get_heartbeat_age_seconds(heartbeat_file: Path) -> float:
    """Get age of heartbeat file in seconds."""
    # Compare file mtime to now
    # Return seconds elapsed

def run_command(cmd: List[str], cwd: Path = None, timeout_seconds: int = 30) -> dict:
    """Run shell command and capture output."""
    # Return: {"returncode": int, "stdout": str, "stderr": str}
    # Handle timeout, return codes, exceptions

def validate_label(label: str) -> tuple[bool, str]:
    """
    Validate optional task label.
    
    Rules:
    - Max 100 characters (VARCHAR 100)
    - Alphanumeric, spaces, hyphens, underscores allowed
    - No special characters
    
    Returns: (is_valid: bool, error_msg: str or empty)
    """
```

---

### 4. Control Flow
**File:** `scripts/supervisor/control_flow.py`

**Implement:**

```python
def check_control_flags(inbox_path: Path, nas: NasManager, worker_id: str, db: Database) -> List[str]:
    """
    Scan Worker_Inbox for flag files and process in priority order.
    
    Flag processing order:
    1. Emergency stops (none currently, but placeholder for future)
    2. Code updates (update_code, update_code_deps, rollback_code)
    3. Operational (pause, resume, restart_watcher)
    4. Diagnostics (diagnostics, verify_db)
    
    Returns list of actions taken (for logging/heartbeat).
    """
    actions_taken = []
    
    # Check for each flag type in priority order
    # Load flag JSON
    # Extract handler and params
    # Execute handler
    # Clean up flag file
    # Record action
    
    return actions_taken
```

---

### 5. Heartbeat & Monitoring
**File:** `scripts/supervisor/heartbeat.py`

**Implement:**

```python
def write_supervisor_heartbeat_file(
    nas: NasManager,
    worker_id: str,
    success: bool,
    error: str = None,
    actions_taken: List[str] = None
) -> Path:
    """
    Write atomic heartbeat JSON to 00_STATE/.
    
    File: 00_STATE/supervisor_heartbeat_{worker_id}.json
    
    Uses tmp-then-replace for atomicity (no partial reads).
    """
    # Build heartbeat dict
    # Write to tmp file
    # Atomic replace of target file
    # Return path

def report_supervisor_heartbeat_to_database(
    db: Database,
    worker_id: str,
    success: bool,
    error: str = None,
    actions_taken: List[str] = None,
    watcher_state: str = "unknown"
) -> None:
    """
    Record supervisor check results in workers_t table.
    
    Inserts or updates row with:
    - worker_id
    - last_heartbeat_at (NOW())
    - status_summary (human-readable)
    """
    # Build status_summary from actions and watcher_state
    # INSERT ... ON DUPLICATE KEY UPDATE
    # Handle database errors gracefully

def read_watcher_heartbeat(nas: NasManager, worker_id: str) -> dict:
    """Read watcher's latest heartbeat file."""
    # Path: 00_STATE/watcher_heartbeat_{worker_id}.json
    # Return parsed dict
    # Handle missing/invalid file
```

---

### 6. Configuration & Initialization
**File:** `scripts/supervisor/config.py`

**Implement:**

```python
def load_supervisor_config(config_path: str = "config.dev.yaml") -> dict:
    """
    Load supervisor config from dev YAML.
    
    Uses scripts.common.spec_config.load_config()
    but adds supervisor-specific validation.
    
    Default to dev config if not specified.
    """
    # Load base config from dev.yaml or specified path
    # Validate supervisor section (if present)
    # Return config dict

def validate_supervisor_environment(nas: NasManager, worker_id: str) -> dict:
    """
    Validate supervisor can access all needed resources.
    
    Checks:
    - NAS accessible
    - Worker_Inbox exists
    - Worker_Outbox exists
    - Logs directory writable
    - 00_STATE accessible
    
    Returns: {"valid": bool, "issues": List[str]}
    """
```

---

### 7. Tests
**Files:** `tests/unit/test_supervisor.py`, `tests/integration/test_supervisor_handlers.py`

**Unit Tests (test_supervisor.py):**
```python
def test_supervisor_init_success()
def test_supervisor_init_missing_config()
def test_supervisor_init_bad_config()
def test_check_watcher_health_running()
def test_check_watcher_health_not_running()
def test_read_heartbeat_file_valid()
def test_read_heartbeat_file_missing()
def test_is_watcher_paused_true()
def test_is_watcher_paused_false()
def test_get_heartbeat_age_seconds()
def test_validate_label_valid()
def test_validate_label_too_long()
def test_validate_label_invalid_characters()
```

**Integration Tests (test_supervisor_handlers.py):**
```python
def test_pause_watcher_flag_created()
def test_pause_watcher_with_label()
def test_resume_watcher_flag_deleted()
def test_resume_watcher_with_label()
def test_update_code_runs_git_pull()
def test_update_code_with_label()
def test_rollback_code_single_commit()
def test_rollback_code_multiple_commits()
def test_rollback_code_failed_revert()
def test_rollback_code_invalid_parameter()
def test_rollback_code_with_label()
def test_restart_watcher_respects_pause_flag()
def test_restart_watcher_with_label()
def test_diagnostics_report_generated()
def test_diagnostics_with_label()
def test_verify_db_all_tests_pass()
def test_verify_db_connection_fails()
def test_verify_db_with_label()
def test_heartbeat_file_atomic_write()
def test_heartbeat_database_insert()
```

---

## IMPLEMENTATION NOTES

### Architecture Decisions

1. **Single-pass execution model**: Supervisor runs once per Task Scheduler cycle, checks flags, reports heartbeat, exits. No infinite loop.

2. **Flag-based control**: Operators create flag files in Worker_Inbox; supervisor detects and processes. Enables remote control without SSH.

3. **Priority-based processing**: Code updates before operational flags; prevents watcher from restarting while update is pending.

4. **Graceful shutdown**: All flag handlers stop watcher via SIGTERM (wait 30s), then SIGKILL if needed. Allows in-flight tasks to complete.

5. **Atomic heartbeat writes**: Use tmp-then-replace for JSON heartbeat files (no partial reads). Database heartbeat also recorded.

6. **Comprehensive error handling**: All handlers return result dict (success, error, details); errors logged but don't crash supervisor.

7. **Audit trail**: All significant actions recorded in database audit_log_t table, including optional label.

8. **Optional labels**: Operators can provide short (up to 100 chars) labels on any flag/task for quick identification and audit tracking.

### Flag Files Format

All flag files in Worker_Inbox/ are JSON:

```json
{
  "task_id": "unique_task_id",
  "handler": "handler_name",
  "label": "optional_label_up_to_100_chars",
  "params": {
    "key": "value"
  }
}
```

The `label` field is optional (can be null or omitted). If provided, it will be:
- Logged in supervisor logs
- Recorded in audit_log_t for audit trail
- Included in diagnostic/verification reports
- Used in filenames where applicable (e.g., diagnostic reports)

Examples:
```json
{
  "task_id": "task_20260205_001",
  "handler": "update_code_deps",
  "label": "impl HT acquire",
  "params": {}
}
```

```json
{
  "task_id": "task_20260205_002",
  "handler": "update_code",
  "label": "AA v1-2",
  "params": {}
}
```

Supervisor deletes flag after processing (success or failure).

### Command-Line Interface

```bash
python supervisor.py --worker-id OrionMX --config config.dev.yaml

Options:
  --worker-id: Worker identifier (default: OrionMX)
  --config: Path to config file (default: config.dev.yaml)

Exit codes:
  0: Success (all checks passed, no errors)
  1: Error (watcher unhealthy, handler failed, etc.)
```

### Logging

- Log to file: `05_LOGS/supervisor.log` (rotating, 10MB max)
- Log to console: stderr (for Task Scheduler visibility)
- Format: `[2026-02-05T14:30:15.234Z] [SUPERVISOR] [LEVEL] message`
- Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include task labels in log messages for easy cross-reference: `[task_20260205_001 - impl HT acquire] Action completed`

---

## CONSTRAINTS & SAFEGUARDS

1. **Label validation**: Max 100 characters; alphanumeric, spaces, hyphens, underscores only
2. **commits_back parameter**: 1-10 only (enforced)
3. **Timeout**: All operations have timeouts:
   - Watcher graceful shutdown: 30 seconds
   - Git operations: 30 seconds
   - Database queries: 10 seconds
4. **Conflict detection**: If git revert encounters conflict, stop and report
5. **Partial rollback handling**: Report which commits succeeded, which failed
6. **No auto-recovery loops**: If watcher restart fails, report and exit (don't loop)
7. **Pause flag respect**: If pause flag set, don't restart watcher after code update

---

## DELIVERABLES CHECKLIST

- [ ] `scripts/supervisor/supervisor.py` (main entry point, Supervisor class)
- [ ] `scripts/supervisor/handlers.py` (flag handlers: pause, resume, update, rollback, restart, diagnostics, verify_db)
- [ ] `scripts/supervisor/utils.py` (utility functions for processes, heartbeat, commands, label validation)
- [ ] `scripts/supervisor/control_flow.py` (check_control_flags orchestration)
- [ ] `scripts/supervisor/heartbeat.py` (database and file-based heartbeat recording)
- [ ] `scripts/supervisor/config.py` (configuration loading and validation)
- [ ] `tests/unit/test_supervisor.py` (unit tests for core functions, including label validation)
- [ ] `tests/integration/test_supervisor_handlers.py` (integration tests for handlers with label support)
- [ ] `__init__.py` in all directories
- [ ] All imports working, all tests passing

---

## WORKFLOW AFTER IMPLEMENTATION

1. **Create feature branch**: `git checkout -b feature/supervisor-system`
2. **Implement handlers one at a time** (pause/resume first, then complex ones)
3. **Test locally** with `pytest tests/unit/` and `pytest tests/integration/`
4. **Commit with descriptive messages**:
   ```
   feat(supervisor): implement pause/resume handlers with optional labels
   feat(supervisor): implement update_code handler with label support
   feat(supervisor): implement rollback_code with multi-commit support and labels
   feat(supervisor): implement diagnostics and db_verify handlers with labels
   ```
5. **Push to GitHub** and create PR
6. **Review PR** for correctness and coverage
7. **Merge to main** when approved
8. **Deploy to OrionMX using dev config**:
   ```bash
   cd C:\cornerstone_archive
   git pull origin main
   pip install -r requirements.txt --break-system-packages
   python supervisor.py --worker-id OrionMX --config config.dev.yaml
   ```

---

## INTEGRATION WITH WATCHER

**Not part of this implementation**, but for context:

- Supervisor monitors watcher via heartbeat files
- Watcher writes `00_STATE/watcher_heartbeat_OrionMX.json` periodically
- Supervisor checks heartbeat age (should be < 5 min)
- If stale: watcher may be hung, supervisor logs warning
- Supervisor can restart watcher via handlers

---

## PRODUCTION READINESS CHECKLIST

Before deploying to production (OrionMX):

- [ ] All tests passing locally
- [ ] Code review via GitHub PR
- [ ] Config files (config.dev.yaml, .env) populated with dev database credentials
- [ ] Manual test of pause flag with label (create flag, verify watcher pauses, verify label in logs)
- [ ] Manual test of resume flag with label (create flag, verify watcher resumes, verify label in logs)
- [ ] Manual test of restart flag with label (create flag, verify watcher restarts cleanly, verify label in logs)
- [ ] Verify heartbeat files written to NAS
- [ ] Verify heartbeat recorded in database
- [ ] Verify labels recorded in audit_log_t
- [ ] Task Scheduler configured to run supervisor every 2-3 minutes with `--config config.dev.yaml`
- [ ] Test rollback with real git history (1 commit, then 3 commits, with labels)
- [ ] Test label validation (test 101-char label rejection, special character rejection)
- [ ] Document operator procedures for each flag with label examples
- [ ] Create runbook in docs/SUPERVISOR_RUNBOOK.md with label usage examples

---

## References

- Database schema: `database/migrations/001_CREATE_CORNERSTONE_ARCHIVE_FOUNDATION_SCHEMA.sql`
- NAS layout: `docs/NAS_LAYOUT.md`
- Supervisor design: `supervisor_flags_revised.md` (in chat history)
- Rollback details: `rollback_multi_commit_detailed.md` (in chat history)
- Watcher implementation: `scripts/watcher/spec_watcher.py`
- Dev configuration: `config.dev.yaml`
