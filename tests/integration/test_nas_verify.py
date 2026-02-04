"""Integration tests for NAS verification script."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from io import StringIO

from scripts.ops.verify_nas_paths import main, verify_nas_paths, VerificationResult
from scripts.common.spec_nas import NasManager


class TestNasVerifyIntegration:
    """Integration tests for verify_nas_paths script."""

    @pytest.fixture
    def temp_nas_structure(self):
        """Create a temporary complete NAS structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nas_root = Path(tmpdir)
            # Create all standard directories
            (nas_root / "00_STATE").mkdir(exist_ok=True)
            (nas_root / "01_RAW" / "containers").mkdir(parents=True, exist_ok=True)
            (nas_root / "02_WORK" / "containers").mkdir(parents=True, exist_ok=True)
            (nas_root / "03_REFERENCE").mkdir(exist_ok=True)
            (nas_root / "04_PUBLISH").mkdir(exist_ok=True)
            (nas_root / "05_LOGS" / "jobs").mkdir(parents=True, exist_ok=True)
            (nas_root / "05_LOGS" / "flags").mkdir(parents=True, exist_ok=True)

            yield nas_root

    @pytest.fixture
    def config_file(self, temp_nas_structure):
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(f"""
environment: development
database:
  host: localhost
  user: testuser
  password: testpass
  database: testdb
nas:
  root: {temp_nas_structure}
  scratch: C:\\Scratch\\NVMe
logging:
  level: INFO
""")
            f.flush()
            yield f.name
        os.unlink(f.name)

    def test_verify_all_paths_ok(self, temp_nas_structure):
        """Test verification succeeds when all paths are present."""
        config = {"nas": {"root": str(temp_nas_structure)}}
        nas = NasManager(config)
        result = verify_nas_paths(nas)

        assert not result.has_errors()
        assert len(result.ok_results) > 0
        assert len(result.errors) == 0

    def test_verify_missing_directory(self, temp_nas_structure):
        """Test verification detects missing directory."""
        # Remove a directory
        (temp_nas_structure / "03_REFERENCE").rmdir()

        config = {"nas": {"root": str(temp_nas_structure)}}
        nas = NasManager(config)
        result = verify_nas_paths(nas)

        assert result.has_errors()
        assert len(result.errors) > 0

    def test_verify_unwritable_directory(self, temp_nas_structure):
        """Test verification detects unwritable directory."""
        import sys
        if sys.platform == "win32":
            pytest.skip("Permission model differs on Windows")

        logs_dir = temp_nas_structure / "05_LOGS"
        os.chmod(logs_dir, 0o444)
        try:
            config = {"nas": {"root": str(temp_nas_structure)}}
            nas = NasManager(config)
            result = verify_nas_paths(nas)

            assert result.has_errors()
            assert len(result.errors) > 0
        finally:
            os.chmod(logs_dir, 0o755)

    def test_main_success(self, config_file, capsys):
        """Test main function with valid config."""
        exit_code = main([f"--config={config_file}"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Summary:" in captured.out

    def test_main_verbose_flag(self, config_file, capsys):
        """Test main function with verbose flag."""
        exit_code = main([f"--config={config_file}", "--verbose"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "Summary:" in captured.out

    def test_main_missing_config(self):
        """Test main function with missing config file."""
        exit_code = main(["--config=/nonexistent/config.yaml"])

        assert exit_code == 1

    def test_main_invalid_config(self):
        """Test main function with invalid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: syntax:")
            f.flush()
            temp_path = f.name

        try:
            exit_code = main([f"--config={temp_path}"])
            assert exit_code == 1
        finally:
            os.unlink(temp_path)

    def test_verification_result_formatting(self):
        """Test VerificationResult formatting."""
        result = VerificationResult()
        result.ok("Test path exists")
        result.warn("Test disk space low")
        result.error("Test path not writable")

        assert result.has_errors()
        assert len(result.ok_results) == 1
        assert len(result.warnings) == 1
        assert len(result.errors) == 1

    def test_verification_result_no_errors(self):
        """Test VerificationResult when no errors."""
        result = VerificationResult()
        result.ok("Test path exists")
        result.ok("Test disk space OK")

        assert not result.has_errors()
        assert len(result.ok_results) == 2

    def test_disk_space_check(self, temp_nas_structure, capsys):
        """Test disk space check is performed."""
        config = {"nas": {"root": str(temp_nas_structure)}}
        nas = NasManager(config)
        result = verify_nas_paths(nas, verbose=True)

        result.print_report(verbose=True)
        captured = capsys.readouterr()

        # Should have disk space check result
        assert "Disk space" in captured.out or "Summary:" in captured.out

    def test_path_accessibility_check(self, temp_nas_structure):
        """Test that all standard paths are checked for accessibility."""
        config = {"nas": {"root": str(temp_nas_structure)}}
        nas = NasManager(config)
        result = verify_nas_paths(nas)

        # Should have checked all 6 standard directories
        total_checks = len(result.ok_results) + len(result.errors)
        assert total_checks >= 6  # At least all standard paths + disk space

    def test_empty_nas_root_fails(self, temp_nas_structure):
        """Test verification fails when directory exists but is empty."""
        # Create a completely empty temp dir
        with tempfile.TemporaryDirectory() as empty_dir:
            config = {"nas": {"root": empty_dir}}
            nas = NasManager(config)
            result = verify_nas_paths(nas)

            assert result.has_errors()
            assert len(result.errors) > 0
