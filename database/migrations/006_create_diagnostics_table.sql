-- ============================================================================
-- DIAGNOSTICS TABLE MIGRATION
-- Database: raneywor_csa_state (MySQL 5.7+)
-- Charset: utf8mb4
-- Engine: InnoDB
-- ============================================================================
-- Creates table for storing diagnostic reports from supervisor

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE IF NOT EXISTS `diagnostics_t` (
  `diagnostic_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `task_id` VARCHAR(64) NOT NULL COMMENT 'Task ID from supervisor control flag',
  `worker_id` VARCHAR(64) NOT NULL COMMENT 'Worker identifier (e.g., OrionMX)',
  `label` VARCHAR(100) NULL COMMENT 'User label for this diagnostic run',
  `report_json` LONGTEXT NOT NULL COMMENT 'Full diagnostic report as JSON',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Report timestamp',
  `watcher_running` TINYINT(1) NOT NULL COMMENT 'Watcher process status',
  `watcher_healthy` TINYINT(1) NOT NULL COMMENT 'Watcher health status',
  `database_connected` TINYINT(1) NOT NULL COMMENT 'Database connectivity status',
  `disk_percent_free` DECIMAL(5,2) NOT NULL COMMENT 'Disk free percentage',

  PRIMARY KEY (`diagnostic_id`),
  INDEX idx_task_id (task_id),
  INDEX idx_worker_id (worker_id),
  INDEX idx_created_at (created_at),
  INDEX idx_watcher_running (watcher_running),
  INDEX idx_database_connected (database_connected)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Storage for supervisor diagnostic reports from console requests';

COMMIT;
