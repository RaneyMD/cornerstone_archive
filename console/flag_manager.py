"""Console flag creation and job tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from console.flag_utils import (
    generate_task_id,
    validate_label,
    validate_handler,
    write_flag_atomically,
)


class FlagManager:
    """Create and track supervisor control flags and job task flags."""

    def __init__(self, outbox_path: str, db) -> None:
        self.outbox_path = Path(outbox_path)
        self.db = db

    def create_supervisor_flag(
        self,
        handler: str,
        worker_id: str,
        params: Optional[dict] = None,
        label: Optional[str] = None,
    ) -> dict:
        """Create supervisor control flag and record job/audit entries."""

        params = params or {}
        label_valid, label_error = validate_label(label)
        if not label_valid:
            return {"success": False, "error": label_error}

        handler_valid, handler_error = validate_handler(handler, "supervisor_control")
        if not handler_valid:
            return {"success": False, "error": handler_error}

        if not worker_id:
            return {"success": False, "error": "Worker ID is required"}

        task_id = generate_task_id("task")
        job_id = self._insert_job_record(
            job_type="supervisor_control",
            target_ref=f"{handler}:{worker_id}",
            label=label,
            task_id=task_id,
        )
        self._insert_audit_log(
            actor="console",
            action="CREATE_FLAG",
            target_type="supervisor_control",
            target_id=str(job_id),
            details={
                "handler": handler,
                "worker_id": worker_id,
                "label": label,
                "params": params,
                "task_id": task_id,
            },
        )

        flag_data = {
            "task_id": task_id,
            "handler": handler,
            "worker_id": worker_id,
            "label": label,
            "params": params,
        }

        flag_name = f"supervisor_{handler}_{worker_id}_{task_id}.flag"
        flag_path = self.outbox_path / flag_name
        if not self._write_flag_file(flag_path, flag_data):
            return {"success": False, "error": "Failed to write flag file"}

        return {
            "success": True,
            "job_id": job_id,
            "task_id": task_id,
            "flag_file": str(flag_path),
        }

    def create_job_flag(
        self, handler: str, params: dict, label: Optional[str] = None
    ) -> dict:
        """Create watcher job flag and record job/audit entries."""

        label_valid, label_error = validate_label(label)
        if not label_valid:
            return {"success": False, "error": label_error}

        handler_valid, handler_error = validate_handler(handler, "job")
        if not handler_valid:
            return {"success": False, "error": handler_error}

        if not params:
            return {"success": False, "error": "Params are required"}

        task_id = generate_task_id("job")
        target_ref = self._summarize_params(params)
        job_id = self._insert_job_record(
            job_type=handler,
            target_ref=target_ref,
            label=label,
            task_id=task_id,
        )
        self._insert_audit_log(
            actor="console",
            action="CREATE_FLAG",
            target_type="job_task",
            target_id=str(job_id),
            details={
                "handler": handler,
                "label": label,
                "params": params,
                "task_id": task_id,
            },
        )

        flag_data = {
            "task_id": task_id,
            "handler": handler,
            "label": label,
            "params": params,
        }

        flag_name = f"job_{handler}_{task_id}.flag"
        flag_path = self.outbox_path / flag_name
        if not self._write_flag_file(flag_path, flag_data):
            return {"success": False, "error": "Failed to write flag file"}

        return {
            "success": True,
            "job_id": job_id,
            "task_id": task_id,
            "flag_file": str(flag_path),
        }

    def _write_flag_file(self, flag_path: Path, flag_data: dict) -> bool:
        return write_flag_atomically(flag_path, flag_data)

    def _summarize_params(self, params: dict) -> str:
        serialized = json.dumps(params, sort_keys=True)
        if len(serialized) > 512:
            return serialized[:509] + "..."
        return serialized

    def _insert_job_record(
        self,
        job_type: str,
        target_ref: str,
        label: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> int:
        sql = (
            "INSERT INTO jobs_t (job_type, target_ref, label, state, task_id) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        params = (job_type, target_ref, label, "queued", task_id)

        connection = self.db._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            connection.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            connection.close()

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
