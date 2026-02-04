"""Parse and validate Internet Archive API metadata.

Extracts standardized metadata from IA API responses and validates
for database ingestion.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class MetadataParseError(Exception):
    """Exception raised during metadata parsing."""

    pass


class MetadataValidationError(Exception):
    """Exception raised during metadata validation."""

    pass


def parse_ia_metadata(ia_json: dict) -> dict:
    """Parse and normalize metadata from IA API response.

    Args:
        ia_json: JSON response from IA metadata API

    Returns:
        Standardized metadata dictionary

    Raises:
        MetadataParseError: If parsing fails
    """
    try:
        metadata = ia_json.get("metadata", {})
        files = ia_json.get("files", [])

        # Extract standard fields
        parsed = {
            "ia_id": ia_json.get("id", ""),
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "extent_pages": _parse_extent_pages(metadata, files),
            "publication_date": _parse_publication_date(metadata),
            "publication_year": _parse_publication_year(metadata),
            "language": metadata.get("language", "English"),
            "creator": metadata.get("creator", ""),
            "publisher": metadata.get("publisher", ""),
            "subject": metadata.get("subject", ""),
            "rights": metadata.get("rights", ""),
            "collection": metadata.get("collection", []),
            "files_count": len(files),
            "jp2_count": len([f for f in files if f.get("name", "").endswith(".jp2")]),
            "ocr_available": any(f.get("name", "").endswith("_hocr.xml") for f in files),
        }

        # Validate parsed data
        validate_ia_metadata(parsed)

        return parsed

    except MetadataValidationError:
        raise
    except Exception as e:
        raise MetadataParseError(f"Failed to parse IA metadata: {e}") from e


def _parse_extent_pages(metadata: dict, files: list) -> int:
    """Parse extent (page count) from metadata or files.

    Args:
        metadata: Metadata dict from IA API
        files: Files list from IA API

    Returns:
        Estimated page count
    """
    # Try explicit pages field
    if "pages" in metadata:
        pages = metadata["pages"]
        if isinstance(pages, int):
            return pages
        elif isinstance(pages, str) and pages.isdigit():
            return int(pages)

    # Try scanningcenter notes
    if "scanningcenter" in metadata:
        notes = metadata.get("description", "")
        match = re.search(r"(\d+)\s+pages", notes, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Fall back to counting JP2 files
    jp2_count = len([f for f in files if f.get("name", "").endswith(".jp2")])
    if jp2_count > 0:
        return jp2_count

    return 0


def _parse_publication_date(metadata: dict) -> Optional[str]:
    """Parse publication date from various metadata fields.

    Args:
        metadata: Metadata dict

    Returns:
        ISO date string (YYYY-MM-DD) or None if unparseable
    """
    # Try direct date field
    if "date" in metadata:
        date_str = metadata["date"]
        return _normalize_date(date_str)

    # Try publicdate field
    if "publicdate" in metadata:
        date_str = metadata["publicdate"]
        return _normalize_date(date_str)

    return None


def _parse_publication_year(metadata: dict) -> Optional[int]:
    """Parse publication year.

    Args:
        metadata: Metadata dict

    Returns:
        Year as integer or None
    """
    # Try year field
    if "year" in metadata:
        year_str = metadata["year"]
        if isinstance(year_str, int):
            return year_str
        if isinstance(year_str, str) and year_str.isdigit():
            return int(year_str)

    # Try to extract from date
    date_str = _parse_publication_date(metadata)
    if date_str and len(date_str) >= 4:
        try:
            return int(date_str[:4])
        except ValueError:
            pass

    return None


def _normalize_date(date_str: str) -> Optional[str]:
    """Normalize date string to ISO format (YYYY-MM-DD).

    Args:
        date_str: Date string in various formats

    Returns:
        ISO date string or None if unparseable
    """
    if not date_str:
        return None

    # Try common formats
    formats = [
        "%Y-%m-%d",          # 2020-01-15
        "%Y/%m/%d",          # 2020/01/15
        "%m/%d/%Y",          # 01/15/2020
        "%B %d, %Y",         # January 15, 2020
        "%b %d, %Y",         # Jan 15, 2020
        "%Y%m%d",            # 20200115
        "%d %B %Y",          # 15 January 2020
        "%Y",                # 2020
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def validate_ia_metadata(metadata: dict) -> None:
    """Validate parsed IA metadata.

    Args:
        metadata: Parsed metadata dict

    Raises:
        MetadataValidationError: If validation fails
    """
    # Check required fields
    if not metadata.get("ia_id"):
        raise MetadataValidationError("Missing IA ID")

    if not metadata.get("title"):
        raise MetadataValidationError("Missing title")

    # Check extent pages
    extent_pages = metadata.get("extent_pages", 0)
    if extent_pages <= 0:
        raise MetadataValidationError(f"Invalid extent_pages: {extent_pages}")

    # Check publication year if available
    pub_year = metadata.get("publication_year")
    if pub_year is not None:
        if pub_year < 1800 or pub_year > datetime.now().year + 1:
            raise MetadataValidationError(f"Invalid publication year: {pub_year}")

    # Check JP2 files available
    if metadata.get("jp2_count", 0) == 0:
        raise MetadataValidationError("No JP2 files available")

    logger.debug(f"Metadata validation passed for {metadata.get('ia_id')}")


def map_to_instance_key(ia_metadata: dict, family_code: str = "test") -> str:
    """Generate stable instance key for deduplication.

    Args:
        ia_metadata: Parsed IA metadata
        family_code: Family code (e.g., "AA" for American Architect)

    Returns:
        Instance key in format: {FAMILY_CODE}_is_{YEAR}{MONTH}{DAY}_{VOLUME}_{ISSUE}

    Example:
        "AA_is_18760105_001_005"  (American Architect, Jan 5, 1876, vol 1, issue 5)
    """
    # Parse publication date
    pub_date = ia_metadata.get("publication_date") or "19000101"
    try:
        year = pub_date[:4]
        month = pub_date[5:7] if len(pub_date) >= 7 else "01"
        day = pub_date[8:10] if len(pub_date) >= 10 else "01"
    except (IndexError, ValueError):
        year, month, day = "1900", "01", "01"

    date_part = f"{year}{month}{day}"

    # Parse volume and issue from IA identifier or metadata
    # This is a simplified version - full implementation would parse complex IA identifiers
    ia_id = ia_metadata.get("ia_id", "")

    # Extract volume and issue from IA identifier
    # Example: sim_american-architect_1876_05 -> volume=1876 (year), issue=05
    parts = ia_id.split("_")
    volume = "001"  # Default
    issue = "001"   # Default

    if len(parts) >= 3:
        # Try to extract from identifier
        try:
            # Last part might be issue
            issue_part = parts[-1].lstrip("0")
            if issue_part.isdigit():
                issue = issue_part.zfill(3)

            # Second to last might be volume/year
            if len(parts) >= 4:
                vol_part = parts[-2]
                if vol_part.isdigit() and len(vol_part) == 4:
                    volume = vol_part[-2:].zfill(3)  # Use last 2 digits of year
        except (IndexError, ValueError, AttributeError):
            pass

    instance_key = f"{family_code}_is_{date_part}_{volume}_{issue}"
    return instance_key
