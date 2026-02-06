/**
 * Migration: Add task_id field to jobs_t for console task tracking
 *
 * Purpose:
 *   - Map console task IDs to job records for result processing
 *   - Support supervisor/job result updates by task_id
 *
 * Applied: 2026-02-06
 */

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

ALTER TABLE `jobs_t`
  ADD COLUMN `task_id` VARCHAR(128) NULL DEFAULT NULL
    COMMENT 'Console task identifier for mapping results'
    AFTER `job_id`,
  ADD KEY `idx_task_id` (`task_id`);

COMMIT;
