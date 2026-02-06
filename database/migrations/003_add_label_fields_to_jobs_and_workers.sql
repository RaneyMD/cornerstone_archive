/**
 * Migration: Add label field to jobs_t for audit trail identification
 *
 * Purpose:
 *   - Store user-provided labels on jobs for easier identification in logs
 *   - Enable audit trail tracking with human-readable descriptions
 *   - Support operational labeling (e.g., "AA vol 1-2", "manual_retry")
 *
 * Changes:
 *   - Add label (VARCHAR 100, NULL): Optional user-provided label for job
 *   - Add index on label for query performance
 *
 * Applied: 2026-02-05
 * Database: raneywor_csa_state (production), raneywor_csa_dev_state (development)
 */

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- Add label field to jobs_t (optional, max 100 chars)
-- Used for audit trail identification (e.g., "AA vol 1-2", "manual_retry")
-- Allows operators to tag jobs with meaningful descriptions for logging
ALTER TABLE `jobs_t`
  ADD COLUMN `label` VARCHAR(100) NULL DEFAULT NULL
    COMMENT 'User-provided label for audit trail (e.g., "AA vol 1-2")'
    AFTER `target_ref`,
  ADD KEY `idx_label` (`label`);

COMMIT;
