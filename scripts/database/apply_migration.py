"""Apply database migrations and record in database_migrations_t."""

import argparse
import hashlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from scripts.common.spec_config import load_config, ConfigError
from scripts.common.spec_db import Database, DatabaseError

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )


def get_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def extract_version_number(filename: str) -> Optional[int]:
    """Extract version number from migration filename.

    Expected format: NNN_description.sql (e.g., 001_create_schema.sql)

    Args:
        filename: Migration filename

    Returns:
        Version number as int, or None if not parseable
    """
    try:
        parts = filename.split('_', 1)
        return int(parts[0])
    except (ValueError, IndexError):
        return None


def is_migration_applied(
    db: Database,
    filename: str
) -> Tuple[bool, Optional[dict]]:
    """Check if migration has already been applied.

    Args:
        db: Database connection
        filename: Migration filename

    Returns:
        Tuple of (is_applied, migration_row)
    """
    try:
        # Use query() which returns list, take first element
        results = db.query(
            "SELECT * FROM database_migrations_t WHERE filename = %s",
            [filename]
        )
        if results:
            return (True, results[0])
        return (False, None)
    except DatabaseError as e:
        logger.warning(f"Could not check migration status: {e}")
        return (False, None)


def parse_sql_statements(sql_content: str) -> list:
    """Parse SQL content into individual statements.

    Handles:
    - Multi-line comments (/* ... */)
    - Single-line comments (-- ...)
    - Statement terminators (;)

    Args:
        sql_content: Raw SQL file content

    Returns:
        List of SQL statements
    """
    statements = []
    current_stmt = ""
    in_comment = False
    i = 0

    while i < len(sql_content):
        # Handle multi-line comments
        if i < len(sql_content) - 1 and sql_content[i:i+2] == '/*':
            in_comment = True
            i += 2
            continue

        if i < len(sql_content) - 1 and sql_content[i:i+2] == '*/' and in_comment:
            in_comment = False
            i += 2
            continue

        if in_comment:
            i += 1
            continue

        # Handle single-line comments
        if i < len(sql_content) - 1 and sql_content[i:i+2] == '--':
            # Skip to end of line
            while i < len(sql_content) and sql_content[i] != '\n':
                i += 1
            i += 1
            continue

        # Handle statement terminator
        if sql_content[i] == ';':
            stmt = current_stmt.strip()
            if stmt:
                statements.append(stmt)
            current_stmt = ""
            i += 1
            continue

        current_stmt += sql_content[i]
        i += 1

    # Add final statement if any
    stmt = current_stmt.strip()
    if stmt:
        statements.append(stmt)

    return statements


def apply_migration(
    db: Database,
    migration_file: Path,
    applied_by: str = "migration_script"
) -> bool:
    """Apply a single migration and record in database.

    Args:
        db: Database connection
        migration_file: Path to migration SQL file
        applied_by: User or system applying the migration

    Returns:
        True if successful, False otherwise
    """
    filename = migration_file.name
    logger.info(f"Applying migration: {filename}")

    try:
        # Check if already applied
        is_applied, prev_record = is_migration_applied(db, filename)
        if is_applied:
            status = prev_record.get('status', 'unknown')
            if status == 'applied':
                logger.info(f"Migration already applied: {filename}")
                return True
            else:
                logger.warning(f"Migration has previous status '{status}': {filename}")

        # Calculate checksum
        checksum = get_file_checksum(migration_file)

        # Extract version number
        version_number = extract_version_number(filename)
        if version_number is None:
            logger.error(f"Could not extract version from filename: {filename}")
            return False

        # Read and parse SQL
        sql_content = migration_file.read_text(encoding='utf-8')
        statements = parse_sql_statements(sql_content)

        if not statements:
            logger.warning(f"No SQL statements found in: {filename}")
            return False

        logger.debug(f"Found {len(statements)} SQL statements")

        # Execute each statement
        for i, statement in enumerate(statements):
            try:
                logger.debug(f"Executing statement {i+1}/{len(statements)}")
                db.execute(statement)
            except DatabaseError as e:
                error_msg = f"SQL statement {i+1} failed: {str(e)}"
                logger.error(error_msg)

                # Record failure in database
                try:
                    utc_now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
                    db.execute(
                        """INSERT INTO database_migrations_t
                           (filename, checksum, version_number, applied_at, applied_by, status, error_message)
                           VALUES (%s, %s, %s, %s, %s, 'error', %s)""",
                        [filename, checksum, version_number, utc_now, applied_by, error_msg]
                    )
                except DatabaseError as e2:
                    logger.error(f"Failed to record error in database: {e2}")

                return False

        # Record success in database
        try:
            utc_now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'

            # Check if we need to insert or update
            if is_applied:
                db.execute(
                    """UPDATE database_migrations_t
                       SET status = 'applied', error_message = NULL, applied_at = %s
                       WHERE filename = %s""",
                    [utc_now, filename]
                )
            else:
                db.execute(
                    """INSERT INTO database_migrations_t
                       (filename, checksum, version_number, applied_at, applied_by, status)
                       VALUES (%s, %s, %s, %s, %s, 'applied')""",
                    [filename, checksum, version_number, utc_now, applied_by]
                )

            logger.info(f"✓ Migration applied successfully: {filename}")
            return True

        except DatabaseError as e:
            logger.error(f"Failed to record migration in database: {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error applying migration: {e}", exc_info=True)
        return False


def apply_migrations(
    config_path: str,
    migrations_dir: Optional[str] = None,
    migration_file: Optional[str] = None,
    applied_by: str = "migration_script"
) -> int:
    """Apply migrations from directory or specific file.

    Args:
        config_path: Path to config YAML file
        migrations_dir: Path to migrations directory (default: database/migrations)
        migration_file: Specific migration filename to apply (optional)
        applied_by: User or system applying migrations

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        import os

        # Load config
        logger.info(f"Loading config from: {config_path}")
        config = load_config(config_path)

        # Override database credentials with admin user if available
        db_config = config.get('database', {})
        env_suffix = '_DEV' if 'dev' in config_path.lower() else ''

        # Check for admin password in environment
        admin_password_var = f'DB_ADMIN_PASSWORD{env_suffix}'
        admin_password = os.getenv(admin_password_var)

        if admin_password:
            # Determine admin username
            admin_user = 'raneywor_csa_dev_admin' if env_suffix == '_DEV' else 'raneywor_csa_admin'
            db_config['user'] = admin_user
            db_config['password'] = admin_password
            logger.info(f"Using admin user for migrations: {admin_user}")
        else:
            logger.warning(f"Admin password not found in {admin_password_var}, using app user")
            logger.warning("Set admin password in .env to enable schema modifications")

        # Determine migrations directory
        if migrations_dir is None:
            repo_root = Path(__file__).parent.parent.parent
            migrations_dir = repo_root / "database" / "migrations"
        else:
            migrations_dir = Path(migrations_dir)

        if not migrations_dir.exists():
            logger.error(f"Migrations directory not found: {migrations_dir}")
            return 1

        logger.info(f"Using migrations directory: {migrations_dir}")

        # Initialize database
        logger.info("Connecting to database...")
        db = Database(config['database'])

        # Get list of migrations
        if migration_file:
            migration_files = [migrations_dir / migration_file]
        else:
            migration_files = sorted(migrations_dir.glob("*.sql"))

        if not migration_files:
            logger.error("No migration files found")
            return 1

        logger.info(f"Found {len(migration_files)} migration file(s)")

        # Apply migrations
        failed = []
        for mig_file in migration_files:
            if not mig_file.exists():
                logger.error(f"Migration file not found: {mig_file}")
                failed.append(mig_file.name)
                continue

            success = apply_migration(db, mig_file, applied_by)
            if not success:
                failed.append(mig_file.name)

        # Summary
        logger.info("=" * 60)
        if failed:
            logger.error(f"Failed to apply {len(failed)} migration(s):")
            for name in failed:
                logger.error(f"  - {name}")
            return 1
        else:
            logger.info("All migrations applied successfully!")
            return 0

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def main(args: Optional[list] = None) -> int:
    """Main entry point.

    Args:
        args: Command-line arguments (for testing)

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Apply database migrations and record in database_migrations_t"
    )
    parser.add_argument(
        '--config',
        default='config/config.dev.yaml',
        help='Path to config YAML file (default: config/config.dev.yaml)'
    )
    parser.add_argument(
        '--migrations-dir',
        help='Path to migrations directory (default: database/migrations)'
    )
    parser.add_argument(
        '--migration',
        help='Specific migration filename to apply (optional, applies all if not specified)'
    )
    parser.add_argument(
        '--applied-by',
        default='migration_script',
        help='User/system applying migrations (default: migration_script)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parsed_args = parser.parse_args(args)

    # Set up logging
    setup_logging(parsed_args.verbose)

    # Run migrations
    return apply_migrations(
        parsed_args.config,
        parsed_args.migrations_dir,
        parsed_args.migration,
        parsed_args.applied_by
    )


if __name__ == '__main__':
    sys.exit(main())
