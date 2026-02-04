"""Stage 1 handler: acquire_source

Fetches publication containers from Internet Archive and registers them
in the database.
"""

import json
import logging
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urljoin

from scripts.common.spec_nas import NasManager, NasError
from scripts.common.spec_db import Database, DatabaseError


logger = logging.getLogger(__name__)


class IAError(Exception):
    """Exception raised for Internet Archive API errors."""

    pass


class DownloadError(Exception):
    """Exception raised for download errors."""

    pass


class DownloadValidationError(Exception):
    """Exception raised when download validation fails."""

    pass


def acquire_source(task: dict, nas: NasManager, db: Database) -> dict:
    """Main handler for acquire_source task.

    Args:
        task: Task dictionary with container_id and ia_identifier
        nas: NasManager instance
        db: Database instance

    Returns:
        Result dictionary with download statistics

    Raises:
        Various exceptions on failure (converted to error dict by watcher)
    """
    container_id = task.get("container_id")
    ia_identifier = task.get("params", {}).get("ia_identifier")
    task_id = task.get("task_id", "unknown")

    if not container_id or not ia_identifier:
        raise ValueError("Missing container_id or ia_identifier in task")

    logger.info(f"[TASK:{task_id}] Acquiring {ia_identifier} for container {container_id}")

    start_time = time.time()

    try:
        # Fetch metadata from IA
        ia_metadata = fetch_ia_metadata(ia_identifier)
        logger.debug(f"[TASK:{task_id}] IA metadata: {ia_metadata.get('title')}, "
                    f"{ia_metadata.get('extent_pages')} pages")

        # Download container from IA
        download_stats = download_ia_container(ia_identifier, str(container_id), nas)
        logger.info(f"[TASK:{task_id}] Downloaded {download_stats['pages_downloaded']} pages "
                   f"({download_stats['size_bytes'] / 1e9:.2f} GB)")

        # Validate downloads
        raw_path = nas.get_raw_path(container_id)
        validate_downloads(container_id, raw_path, ia_metadata)
        logger.info(f"[TASK:{task_id}] Validation passed")

        # Register in database
        register_container_in_db(container_id, ia_identifier, db, ia_metadata, download_stats)
        logger.info(f"[TASK:{task_id}] Registered in database")

        duration_seconds = time.time() - start_time

        result = {
            "status": "success",
            "container_id": container_id,
            "ia_identifier": ia_identifier,
            "pages_downloaded": download_stats["pages_downloaded"],
            "size_bytes": download_stats["size_bytes"],
            "jp2_files": download_stats["jp2_files"],
            "ocr_files": download_stats["ocr_files"],
            "duration_seconds": round(duration_seconds, 2),
            "raw_path": str(raw_path),
        }

        logger.info(f"[TASK:{task_id}] Acquisition completed in {duration_seconds:.1f}s")
        return result

    except Exception as e:
        logger.error(f"[TASK:{task_id}] Acquisition failed: {e}", exc_info=True)
        raise


def fetch_ia_metadata(ia_identifier: str, max_retries: int = 3) -> dict:
    """Fetch metadata from Internet Archive API.

    Args:
        ia_identifier: Internet Archive identifier (e.g., sim_american-architect_1876_05)
        max_retries: Number of retry attempts

    Returns:
        Metadata dictionary with title, extent_pages, files list, etc.

    Raises:
        IAError: If metadata cannot be fetched
    """
    base_url = "https://archive.org/metadata"
    url = f"{base_url}/{ia_identifier}"

    for attempt in range(max_retries):
        try:
            logger.debug(f"Fetching IA metadata: {ia_identifier} (attempt {attempt + 1})")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract key metadata
            metadata = {
                "ia_id": ia_identifier,
                "title": data.get("metadata", {}).get("title", ia_identifier),
                "description": data.get("metadata", {}).get("description", ""),
                "extent_pages": data.get("metadata", {}).get("pages", 0),
                "date": data.get("metadata", {}).get("date", ""),
                "language": data.get("metadata", {}).get("language", "English"),
                "files": [],
            }

            # Extract file list
            for file_info in data.get("files", []):
                if file_info.get("name", "").endswith(".jp2"):
                    metadata["files"].append({
                        "name": file_info["name"],
                        "size": int(file_info.get("size", 0)),
                        "md5": file_info.get("md5", ""),
                    })

            if metadata.get("extent_pages", 0) == 0:
                metadata["extent_pages"] = len(metadata["files"])

            logger.debug(f"IA metadata fetched: {len(metadata['files'])} JP2 files")
            return metadata

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"IA API timeout, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise IAError(f"IA API timeout after {max_retries} attempts")
        except requests.exceptions.RequestException as e:
            raise IAError(f"IA API error: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise IAError(f"Failed to parse IA metadata: {e}") from e

    raise IAError(f"Failed to fetch metadata after {max_retries} attempts")


def download_ia_container(
    ia_identifier: str, container_id: str, nas: NasManager, max_retries: int = 3
) -> dict:
    """Download container files from Internet Archive.

    Args:
        ia_identifier: IA identifier
        container_id: Container ID for NAS path
        nas: NasManager instance
        max_retries: Retry attempts per file

    Returns:
        Dictionary with download statistics

    Raises:
        DownloadError: If download fails
    """
    # Create raw directory
    raw_path = nas.get_raw_path(container_id)
    try:
        raw_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created raw directory: {raw_path}")
    except Exception as e:
        raise DownloadError(f"Cannot create raw directory: {e}") from e

    # Fetch metadata to get file list
    try:
        ia_metadata = fetch_ia_metadata(ia_identifier)
        files = ia_metadata.get("files", [])
    except IAError as e:
        raise DownloadError(f"Cannot fetch file list: {e}") from e

    # Download each JP2 file
    base_url = f"https://archive.org/download/{ia_identifier}"
    downloaded_files = []
    total_size = 0
    rate_limit_delay = 0.5  # Seconds between requests

    for file_info in files:
        filename = file_info["name"]
        file_url = urljoin(base_url, filename)
        file_path = raw_path / filename

        # Skip if already exists and size matches
        if file_path.exists():
            if file_path.stat().st_size == file_info.get("size", 0):
                logger.debug(f"File already exists: {filename}")
                downloaded_files.append(filename)
                total_size += file_info.get("size", 0)
                continue

        # Download file
        for attempt in range(max_retries):
            try:
                logger.debug(f"Downloading {filename} (attempt {attempt + 1})")
                response = requests.get(file_url, timeout=60, stream=True)
                response.raise_for_status()

                # Write to temporary file first
                temp_path = file_path.with_suffix(".tmp")
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Verify size if available
                expected_size = file_info.get("size", 0)
                if expected_size > 0 and temp_path.stat().st_size != expected_size:
                    logger.warning(f"Size mismatch for {filename}: "
                                 f"{temp_path.stat().st_size} vs {expected_size}")
                    temp_path.unlink()
                    raise DownloadError("File size mismatch")

                # Rename temp to final
                temp_path.rename(file_path)
                downloaded_files.append(filename)
                total_size += file_path.stat().st_size
                logger.debug(f"Downloaded: {filename} ({file_path.stat().st_size / 1e6:.1f} MB)")

                # Rate limiting
                time.sleep(rate_limit_delay)
                break

            except requests.exceptions.RequestException as e:
                logger.warning(f"Download failed for {filename}: {e}")
                if attempt == max_retries - 1:
                    raise DownloadError(f"Cannot download {filename} after {max_retries} attempts") from e
                time.sleep(2 ** attempt)

    logger.info(f"Downloaded {len(downloaded_files)} files ({total_size / 1e9:.2f} GB)")

    return {
        "pages_downloaded": len(downloaded_files),
        "jp2_files": len(downloaded_files),
        "ocr_files": 0,  # TODO: Handle OCR payloads
        "size_bytes": total_size,
    }


def validate_downloads(container_id: str, raw_path: Path, ia_metadata: dict) -> None:
    """Validate downloaded files.

    Args:
        container_id: Container ID
        raw_path: Path to raw directory
        ia_metadata: IA metadata dict with expected file list

    Raises:
        DownloadValidationError: If validation fails
    """
    expected_files = len(ia_metadata.get("files", []))
    actual_files = len(list(raw_path.glob("*.jp2")))

    if actual_files != expected_files:
        raise DownloadValidationError(
            f"File count mismatch: expected {expected_files}, got {actual_files}"
        )

    logger.info(f"Validation passed: {actual_files} files for container {container_id}")


def register_container_in_db(
    container_id: str, ia_identifier: str, db: Database, ia_metadata: dict,
    download_stats: dict
) -> None:
    """Register container and pages in database.

    Args:
        container_id: Container ID
        ia_identifier: IA identifier
        db: Database instance
        ia_metadata: IA metadata dict
        download_stats: Download statistics

    Raises:
        DatabaseError: If database operation fails
    """
    try:
        # Insert container
        container_sql = """
            INSERT INTO containers_t
            (container_id, source_system, source_identifier, source_url,
             container_type, extent_pages, download_status, downloaded_at,
             raw_path, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
            ON DUPLICATE KEY UPDATE
                download_status = 'complete',
                extent_pages = VALUES(extent_pages),
                downloaded_at = NOW()
        """

        extent_pages = ia_metadata.get("extent_pages", download_stats["pages_downloaded"])
        raw_path = Path(f"\\RaneyHQ\\Michael\\02_Projects\\Cornerstone_Archive\\01_RAW\\containers\\{container_id}")

        db.execute(
            container_sql,
            (
                str(container_id),
                "internet_archive",
                ia_identifier,
                f"https://archive.org/details/{ia_identifier}",
                "bound_volume",
                extent_pages,
                "complete",
                str(raw_path),
                "watcher",
            ),
        )

        # Insert pages
        pages_sql = """
            INSERT INTO pages_t
            (container_id, page_index, page_type, created_by)
            VALUES (%s, %s, %s, %s)
        """

        pages_data = [
            (str(container_id), i, "content", "watcher")
            for i in range(extent_pages)
        ]

        db.execute_many(pages_sql, pages_data)

        logger.info(f"Registered container {container_id} with {extent_pages} pages")

    except DatabaseError as e:
        raise DatabaseError(f"Failed to register container in database: {e}") from e
