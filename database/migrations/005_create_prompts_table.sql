-- ============================================================================
-- PROMPTS TABLE MIGRATION
-- Database: raneywor_csa_state (MySQL 5.7+)
-- Charset: utf8mb4
-- Engine: InnoDB
-- ============================================================================
-- Creates table for Claude Code prompt management system
-- Stores metadata for prompts uploaded via console
-- ============================================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE IF NOT EXISTS `prompts_t` (
  `prompt_id` INT AUTO_INCREMENT PRIMARY KEY,
  `sequence_number` INT NOT NULL COMMENT 'Four-digit prefix for filename (e.g., 0001, 0002)',
  `prompt_name` VARCHAR(100) NOT NULL COMMENT 'User-friendly prompt name',
  `prompt_filename` VARCHAR(150) NOT NULL COMMENT 'Filename on disk with sequence prefix',
  `file_size` INT NOT NULL COMMENT 'File size in bytes',
  `uploaded_by` VARCHAR(50) NOT NULL COMMENT 'Username who uploaded',
  `uploaded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Upload timestamp UTC',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Soft delete flag',

  INDEX idx_prompt_name (prompt_name),
  INDEX idx_uploaded_at (uploaded_at),
  INDEX idx_is_active (is_active),
  INDEX idx_sequence_number (sequence_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Storage for Claude Code prompts uploaded via console';

COMMIT;
