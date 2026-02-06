"""Unit tests for console.result_processor."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from console.result_processor import (
    ResultProcessor,
    extract_error_message,
    map_task_id_to_job_id,
    parse_result_file,
)


def test_parse_supervisor_result_file(tmp_path):
    result_file = tmp_path / "supervisor_heartbeat_test.json"
    payload = {
        "supervisor_id": "supervisor_OrionMX",
        "timestamp": "2026-02-05T21:58:37Z",
        "worker_id": "OrionMX",
        "success": True,
        "error": None,
        "actions": ["update_code_deps (impl HT acquire)"]
    }
    result_file.write_text(json.dumps(payload))

    parsed = parse_result_file(result_file)

    assert parsed["worker_id"] == "OrionMX"
    assert parsed["success"] is True


def test_parse_job_result_file_success(tmp_path):
    result_file = tmp_path / "job_20260205_001.result.json"
    payload = {
        "task_id": "job_20260205_001",
        "success": True,
        "completed_at": "2026-02-05T21:59:12Z",
        "result": {"handler": "acquire_source", "items_acquired": 50}
    }
    result_file.write_text(json.dumps(payload))

    parsed = parse_result_file(result_file)

    assert parsed["task_id"] == "job_20260205_001"
    assert extract_error_message(parsed) is None


def test_parse_job_result_file_error(tmp_path):
    result_file = tmp_path / "job_20260205_002.error.json"
    payload = {
        "task_id": "job_20260205_002",
        "success": False,
        "completed_at": "2026-02-05T21:59:12Z",
        "result": {"error": "Connection timeout"}
    }
    result_file.write_text(json.dumps(payload))

    parsed = parse_result_file(result_file)

    assert extract_error_message(parsed) == "Connection timeout"


def test_update_job_result_in_database():
    db = MagicMock()
    processor = ResultProcessor("/tmp", db)

    processor.update_job_result(123, True, {"result_path": "file.json"})

    db.execute.assert_called()
    sql = db.execute.call_args[0][0]
    assert "UPDATE jobs_t" in sql


def test_get_job_status_queued():
    db = MagicMock()
    db.get_one.return_value = {"job_id": 1, "state": "queued"}
    processor = ResultProcessor("/tmp", db)

    result = processor.get_job_status(1)

    assert result["state"] == "queued"


def test_get_job_status_succeeded():
    db = MagicMock()
    db.get_one.return_value = {"job_id": 2, "state": "succeeded"}
    processor = ResultProcessor("/tmp", db)

    result = processor.get_job_status(2)

    assert result["state"] == "succeeded"


def test_get_job_status_failed():
    db = MagicMock()
    db.get_one.return_value = {"job_id": 3, "state": "failed"}
    processor = ResultProcessor("/tmp", db)

    result = processor.get_job_status(3)

    assert result["state"] == "failed"


def test_cleanup_result_file(tmp_path):
    db = MagicMock()
    processor = ResultProcessor(str(tmp_path), db)

    result_file = tmp_path / "job_20260205_003.result.json"
    result_file.write_text("{}");

    assert processor.cleanup_result_file(result_file) is True
    assert not result_file.exists()


def test_process_multiple_results(tmp_path):
    db = MagicMock()
    db.get_one.side_effect = [{"job_id": 10}, {"job_id": 11}]
    processor = ResultProcessor(str(tmp_path), db)

    first = tmp_path / "job_20260205_010.result.json"
    second = tmp_path / "job_20260205_011.result.json"
    first.write_text(json.dumps({"task_id": "job_20260205_010", "success": True}))
    second.write_text(json.dumps({"task_id": "job_20260205_011", "success": False, "result": {"error": "fail"}}))

    results = processor.process_pending_results()

    assert len(results) == 2
    assert results[0]["job_id"] == 10
    assert results[1]["job_id"] == 11


def test_audit_entry_created_for_result(tmp_path):
    db = MagicMock()
    db.get_one.return_value = {"job_id": 20}
    processor = ResultProcessor(str(tmp_path), db)

    result_file = tmp_path / "job_20260205_020.result.json"
    result_file.write_text(json.dumps({"task_id": "job_20260205_020", "success": True}))

    processor.process_pending_results()

    audit_calls = [
        call for call in db.execute.call_args_list if "audit_log_t" in call[0][0]
    ]
    assert audit_calls


def test_map_task_id_to_job_id():
    db = MagicMock()
    db.get_one.return_value = {"job_id": 42}

    result = map_task_id_to_job_id("job_20260205_042", db)

    assert result == 42
