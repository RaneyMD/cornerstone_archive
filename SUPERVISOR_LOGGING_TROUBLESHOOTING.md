# Supervisor Logging Troubleshooting

## Issue
Supervisor logs are not being created at `05_LOGS/supervisor.log`

## How Supervisor Logging Works

When supervisor runs, it:
1. Calculates log directory from config file path at `supervisor.py:346-348`:
   ```python
   log_dir = (
       repo_root
       / Path(parsed_args.config).parent.parent
       / '05_LOGS'
   )
   ```
2. Creates log file at: `{log_dir}/supervisor.log`
3. Uses rotating handler: 10MB max per file, keeps 5 backups

## Debugging Steps

### 1. Check if 05_LOGS directory exists
```powershell
# On Synology or network share
ls "\\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\05_LOGS\"
```

If it doesn't exist, create it with write permissions.

### 2. Verify Task Scheduler command

Check the exact command in Task Scheduler:
- Right-click the supervisor task
- Properties → Actions tab
- Note the:
  - **Program/script**: Python path
  - **Arguments**: Command-line args (should include `--config`)
  - **Start in**: Working directory

### 3. Check config file location

If the task runs with `--config config/config.dev.yaml`, the log will go to:
```
{repo_root}/05_LOGS/supervisor.log
```

If the task runs from a different working directory, the log path will be different.

### 4. Manual test

Run supervisor manually with the same command:
```powershell
cd C:\cornerstone_archive
python scripts/supervisor/supervisor.py --config config/config.dev.yaml --worker-id OrionMX
```

This will show:
- If supervisor starts successfully
- Where it's trying to write logs
- Any permission errors

### 5. Check file permissions

Ensure the user running Task Scheduler has write access to:
- `05_LOGS/` directory
- The network share `\\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\`

## Expected Log Format

Once working, supervisor.log will contain entries like:
```
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] ============================================================
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] SUPERVISOR RUN START for OrionMX
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] ============================================================
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] Checking watcher health for OrionMX
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] Processing control flags...
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] Found 2 control flag(s)
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] Processing pause_watcher from supervisor_pause_watcher_OrionMX_task_...flag
[2026-02-06T23:16:13] [SUPERVISOR] [INFO] Pause flag created: \\RaneyHQ\Michael\02_Projects\Cornerstone_Archive\00_STATE\supervisor_pause_OrionMX.flag
```

## Logs Should Be Created At

Based on the config path, expected locations are:

| Config Path | Log Location |
|---|---|
| `config/config.dev.yaml` | `{repo_root}/05_LOGS/supervisor.log` |
| `config/config.prod.yaml` | `{repo_root}/05_LOGS/supervisor.log` |
| Absolute path like `/path/to/config.yaml` | `/path/to/../../05_LOGS/supervisor.log` |

If the Task Scheduler working directory is different, the relative path calculation will change.
