"""Unit tests for console.flag_manager."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from console.flag_manager import FlagManager
from console.flag_utils import (
    generate_task_id,
    validate_handler,
    validate_label,
    write_flag_atomically,
)


def build_db():
    db = MagicMock()
    connection = MagicMock()
    cursor = MagicMock()
    cursor.lastrowid = 123
    connection.cursor.return_value = cursor
    db._get_connection.return_value = connection
    db.execute.return_value = 1
    return db, cursor


def test_create_supervisor_flag_pause(tmp_path):
    db, _ = build_db()
    manager = FlagManager(str(tmp_path), db)

    result = manager.create_supervisor_flag("pause_watcher", "OrionMX", label="test")

    assert result["success"] is True
    assert result["job_id"] == 123
    flag_path = Path(result["flag_file"])
    assert flag_path.exists()
    payload = json.loads(flag_path.read_text())
    assert payload["handler"] == "pause_watcher"
    assert payload["worker_id"] == "OrionMX"


def test_create_supervisor_flag_update_deps(tmp_path):
    db, _ = build_db()
    manager = FlagManager(str(tmp_path), db)

    result = manager.create_supervisor_flag("update_code_deps", "OrionMX")

    assert result["success"] is True
    assert "update_code_deps" in result["flag_file"]


def test_create_job_flag_acquire_source(tmp_path):
    db, _ = build_db()
    manager = FlagManager(str(tmp_path), db)

    result = manager.create_job_flag(
        "acquire_source", {"source_id": "archive_american_architect"}, label="AA v1"
    )

    assert result["success"] is True
    flag_path = Path(result["flag_file"])
    assert flag_path.exists()
    payload = json.loads(flag_path.read_text())
    assert payload["handler"] == "acquire_source"


def test_flag_validation_valid_label():
    valid, error = validate_label("AA v1-2")
    assert valid is True
    assert error == ""


def test_flag_validation_label_too_long():
    valid, error = validate_label("a" * 101)
    assert valid is False
    assert "Label too long" in error


def test_flag_validation_invalid_handler():
    valid, error = validate_handler("unknown", "job")
    assert valid is False
    assert "Unknown job handler" in error


def test_flag_file_written_atomically(tmp_path):
    flag_path = tmp_path / "sample.flag"
    flag_data = {"task_id": "task_20260101_000000_abcd"}

    assert write_flag_atomically(flag_path, flag_data) is True
    assert flag_path.exists()


def test_task_id_generation_unique():
    first = generate_task_id("task")
    second = generate_task_id("task")
    assert first != second


def test_job_record_inserted_in_jobs_t(tmp_path):
    db, cursor = build_db()
    manager = FlagManager(str(tmp_path), db)

    manager.create_job_flag("acquire_source", {"source_id": "abc"})

    assert cursor.execute.called
    sql = cursor.execute.call_args[0][0]
    assert "INSERT INTO jobs_t" in sql


def test_audit_entry_created_in_audit_log_t(tmp_path):
    db, _ = build_db()
    manager = FlagManager(str(tmp_path), db)

    manager.create_job_flag("acquire_source", {"source_id": "abc"})

    audit_calls = [
        call for call in db.execute.call_args_list if "audit_log_t" in call[0][0]
    ]
    assert audit_calls
