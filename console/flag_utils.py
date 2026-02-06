"""Shared helpers for console flag creation and parsing."""

from __future__ import annotations

import json
import os
import random
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

SUPERVISOR_HANDLERS = {
    "pause_watcher",
    "resume_watcher",
    "restart_watcher",
    "update_code",
    "update_code_deps",
    "rollback_code",
    "diagnostics",
    "verify_db",
}

JOB_HANDLERS = {
    "acquire_source",
}

LABEL_PATTERN = re.compile(r"^[A-Za-z0-9 _-]+$")


def generate_task_id(flag_type: str = "task") -> str:
    """Generate unique task ID.

    Format: {type}_{YYYYMMDD}_{HHMMSS}_{random_4chars}
    Example: task_20260205_215837_a7k2
    """

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{flag_type}_{timestamp}_{random_suffix}"


def validate_label(label: Optional[str]) -> Tuple[bool, str]:
    """Validate label (max 100 chars, alphanumeric, spaces, hyphens, underscores)."""

    if label is None or label == "":
        return True, ""
    if len(label) > 100:
        return False, f"Label too long ({len(label)} > 100 characters)"
    if not LABEL_PATTERN.match(label):
        return False, "Label contains invalid characters"
    return True, ""


def validate_handler(handler: str, flag_type: str) -> Tuple[bool, str]:
    """Validate handler name against allowed handlers."""

    if not handler:
        return False, "Handler is required"
    if flag_type == "supervisor_control":
        if handler not in SUPERVISOR_HANDLERS:
            return False, f"Unknown supervisor handler: {handler}"
        return True, ""
    if flag_type == "job":
        if handler not in JOB_HANDLERS:
            return False, f"Unknown job handler: {handler}"
        return True, ""
    return False, f"Unknown flag type: {flag_type}"


def write_flag_atomically(flag_path: Path, flag_data: dict) -> bool:
    """Write flag file using tmp-then-replace for atomicity."""

    flag_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = flag_path.with_suffix(flag_path.suffix + ".tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(flag_data, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, flag_path)
        return True
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def parse_task_id(task_id: str) -> dict:
    """Parse task_id to extract type, timestamp, random component."""

    pattern = re.compile(r"^(?P<type>[a-zA-Z]+)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<rand>[a-z0-9]{4})$")
    match = pattern.match(task_id or "")
    if not match:
        return {}

    data = match.groupdict()
    try:
        data["timestamp"] = datetime.strptime(
            f"{data['date']}{data['time']}", "%Y%m%d%H%M%S"
        )
    except ValueError:
        data["timestamp"] = None
    return data
