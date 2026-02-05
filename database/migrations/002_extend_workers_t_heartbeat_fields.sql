/**
 * Migration: Extend workers_t table with full heartbeat data
 *
 * Purpose:
 *   - Store operational heartbeat data directly in database
 *   - Eliminate dependency on NAS file access (UNC paths)
 *   - Enable console to read heartbeat from database instead of files
 *   - Improve data reliability and query performance
 *
 * Changes:
 *   - Add pid (INT): Process ID of the running watcher
 *   - Add hostname (VARCHAR): Hostname where watcher is running
 *   - Add status (VARCHAR): Current status (e.g., 'running')
 *   - Add poll_seconds (INT): Scan interval in seconds
 *
 * Applied: 2026-02-05
 * Database: raneywor_csa_state (production), raneywor_csa_dev_state (development)
 */

-- Add new columns to workers_t
ALTER TABLE `workers_t`
  ADD COLUMN `pid` INT NULL COMMENT 'Process ID of the running watcher' AFTER `last_heartbeat_at`,
  ADD COLUMN `hostname` VARCHAR(255) NULL COMMENT 'Hostname where watcher is running' AFTER `pid`,
  ADD COLUMN `status` VARCHAR(50) NULL COMMENT 'Current watcher status (e.g., running, stopped)' AFTER `hostname`,
  ADD COLUMN `poll_seconds` INT NULL COMMENT 'Scan interval in seconds' AFTER `status`;

-- Verify columns were added
-- SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'workers_t' ORDER BY ORDINAL_POSITION;
