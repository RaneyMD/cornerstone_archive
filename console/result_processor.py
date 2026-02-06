"""Console result processing for supervisor and watcher outputs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Optional


class ResultProcessor:
    """Process result files from the console inbox."""

    def __init__(self, inbox_path: str, db) -> None:
        self.inbox_path = Path(inbox_path)
        self.db = db
        self.cleanup_processed_results = False
        self.archive_path: Optional[Path] = None

    def process_pending_results(self) -> List[dict]:
        """Process all result files currently in the inbox."""

        results: List[dict] = []
        if not self.inbox_path.exists():
            return results

        result_files = sorted(self.inbox_path.glob("*.json"))
        for result_file in result_files:
            result = self.process_result_file(result_file)
            if result:
                results.append(result)
        return results

    def process_result_file(self, result_file: Path) -> Optional[dict]:
        """Process a single result file and update job records."""

        result_data = parse_result_file(result_file)
        if not result_data:
            return None

        if "task_id" in result_data:
            return self._process_job_result(result_file, result_data)
        if "supervisor_id" in result_data and "worker_id" in result_data:
            return self._process_supervisor_result(result_file, result_data)

        return None

    def _process_job_result(self, result_file: Path, result_data: dict) -> dict:
        task_id = result_data.get("task_id")
        job_id = map_task_id_to_job_id(task_id, self.db)
        success = bool(result_data.get("success"))
        error = extract_error_message(result_data)
        result_data = {**result_data, "result_path": str(result_file)}

        if job_id is not None:
            self.update_job_result(job_id, success, result_data, error)
            self._insert_audit_log(
                actor="result_processor",
                action="JOB_COMPLETED",
                target_type="job_result",
                target_id=str(job_id),
                details={
                    "success": success,
                    "task_id": task_id,
                    "result_file": str(result_file),
                    "error": error,
                },
            )

        self._insert_audit_log(
            actor="result_processor",
            action="PROCESS_RESULT",
            target_type="job_result",
            target_id=str(job_id) if job_id is not None else "unknown",
            details={
                "task_id": task_id,
                "success": success,
                "result_file": str(result_file),
                "error": error,
            },
        )

        if self.cleanup_processed_results:
            self.cleanup_result_file(result_file)

        return {
            "task_id": task_id,
            "job_id": job_id,
            "success": success,
            "error": error,
            "result_file": str(result_file),
        }

    def _process_supervisor_result(self, result_file: Path, result_data: dict) -> dict:
        worker_id = result_data.get("worker_id")
        actions = result_data.get("actions", []) or []
        success = bool(result_data.get("success"))
        error = result_data.get("error")
        result_data = {**result_data, "result_path": str(result_file)}

        updated_jobs = []
        for action in actions:
            handler = str(action).split(" ")[0]
            job_id = self._find_supervisor_job_id(handler, worker_id)
            if job_id is None:
                continue
            self.update_job_result(job_id, success, result_data, error)
            updated_jobs.append(job_id)
            self._insert_audit_log(
                actor="result_processor",
                action="JOB_COMPLETED",
                target_type="supervisor_control",
                target_id=str(job_id),
                details={
                    "success": success,
                    "handler": handler,
                    "worker_id": worker_id,
                    "result_file": str(result_file),
                    "error": error,
                },
            )

        self._insert_audit_log(
            actor="result_processor",
            action="PROCESS_RESULT",
            target_type="supervisor_control",
            target_id=",".join(str(job_id) for job_id in updated_jobs) or "unknown",
            details={
                "worker_id": worker_id,
                "actions": actions,
                "success": success,
                "result_file": str(result_file),
                "error": error,
            },
        )

        if self.cleanup_processed_results:
            self.cleanup_result_file(result_file)

        return {
            "worker_id": worker_id,
            "actions": actions,
            "success": success,
            "error": error,
            "result_file": str(result_file),
            "job_ids": updated_jobs,
        }

    def _find_supervisor_job_id(self, handler: str, worker_id: str) -> Optional[int]:
        sql = (
            "SELECT job_id FROM jobs_t "
            "WHERE job_type = 'supervisor_control' "
            "AND target_ref = %s "
            "AND state IN ('queued', 'running') "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = self.db.get_one(sql, (f"{handler}:{worker_id}",))
        if not row:
            return None
        return row.get("job_id")

    def update_job_result(
        self, job_id: int, success: bool, result_data: dict, error: Optional[str] = None
    ) -> None:
        state = "succeeded" if success else "failed"
        sql = (
            "UPDATE jobs_t "
            "SET state = %s, finished_at = NOW(), result_path = %s, last_error = %s "
            "WHERE job_id = %s"
        )
        params = (state, str(result_data.get("result_path", "")), error, job_id)
        self.db.execute(sql, params)

    def get_job_status(self, job_id: int) -> dict:
        sql = "SELECT * FROM jobs_t WHERE job_id = %s"
        return self.db.get_one(sql, (job_id,)) or {}

    def cleanup_result_file(self, result_file: Path) -> bool:
        if self.archive_path:
            self.archive_path.mkdir(parents=True, exist_ok=True)
            destination = self.archive_path / result_file.name
            shutil.move(str(result_file), str(destination))
            return True
        try:
            result_file.unlink()
            return True
        except OSError:
            return False

    def _insert_audit_log(
        self,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        details: dict,
    ) -> None:
        sql = (
            "INSERT INTO audit_log_t (actor, action, target_type, target_id, details_json) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        params = (actor, action, target_type, target_id, json.dumps(details))
        self.db.execute(sql, params)


def parse_result_file(file_path: Path) -> Optional[dict]:
    """Parse and validate result JSON."""

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def extract_error_message(result_data: dict) -> Optional[str]:
    """Extract error message from result payload."""

    if result_data.get("success") is True:
        return None
    if result_data.get("error"):
        return str(result_data["error"])
    result_section = result_data.get("result") or {}
    if isinstance(result_section, dict) and result_section.get("error"):
        return str(result_section["error"])
    return None


def map_task_id_to_job_id(task_id: str, db) -> Optional[int]:
    """Map task_id to job_id using jobs_t table."""

    if not task_id:
        return None
    row = db.get_one("SELECT job_id FROM jobs_t WHERE task_id = %s", (task_id,))
    if not row:
        return None
    return row.get("job_id")
