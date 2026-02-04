-- ============================================================================
-- THE CORNERSTONE ARCHIVE - FOUNDATION SCHEMA
-- Database: raneywor_csa_state (MySQL 5.7+)
-- Charset: utf8mb4
-- Engine: InnoDB
-- ============================================================================
-- Complete schema for workflow management, processing, and publishing.
-- This script creates all 17 tables for the state database.
-- Execute entirely to establish the complete schema.
-- ============================================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- ============================================================================
-- TIER 0: OPERATIONAL (4 tables)
-- ============================================================================

CREATE TABLE `jobs_t` (
  `job_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `job_type` VARCHAR(64) NOT NULL,
  `target_ref` VARCHAR(512) NOT NULL,
  `state` ENUM('queued','running','succeeded','failed','blocked','canceled') NOT NULL DEFAULT 'queued',
  `attempts` INT UNSIGNED NOT NULL DEFAULT 0,
  `claimed_by_worker` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `last_error` TEXT NULL,
  `log_path` VARCHAR(512) NULL,
  `result_path` VARCHAR(512) NULL,
  PRIMARY KEY (`job_id`),
  KEY `idx_state` (`state`),
  KEY `idx_updated` (`updated_at`),
  KEY `idx_worker` (`claimed_by_worker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workers_t` (
  `worker_id` VARCHAR(64) NOT NULL,
  `last_heartbeat_at` DATETIME NOT NULL,
  `status_summary` VARCHAR(255) NULL,
  PRIMARY KEY (`worker_id`),
  KEY `idx_heartbeat` (`last_heartbeat_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `audit_log_t` (
  `audit_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `actor` VARCHAR(128) NOT NULL,
  `action` VARCHAR(64) NOT NULL,
  `target_type` VARCHAR(64) NOT NULL,
  `target_id` VARCHAR(64) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `details_json` TEXT NULL,
  PRIMARY KEY (`audit_id`),
  KEY `idx_action` (`action`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `database_migrations_t` (
  `migration_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `filename` VARCHAR(256) NOT NULL UNIQUE,
  `checksum` VARCHAR(64) NOT NULL,
  `version_number` INT UNSIGNED NOT NULL,
  `applied_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_by` VARCHAR(128) NOT NULL,
  `status` ENUM('applied','rolled_back','error') NOT NULL DEFAULT 'applied',
  `error_message` TEXT NULL,
  `rollback_script` VARCHAR(512) NULL,
  `notes` TEXT NULL,
  PRIMARY KEY (`migration_id`),
  UNIQUE KEY `uq_filename` (`filename`),
  KEY `idx_applied_at` (`applied_at`),
  KEY `idx_status` (`status`),
  KEY `idx_version` (`version_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TIER 1: PUBLICATION HIERARCHY (5 tables)
-- ============================================================================

CREATE TABLE `publication_families_t` (
  `family_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `family_root` VARCHAR(255) NOT NULL UNIQUE,
  `family_code` VARCHAR(64) NULL UNIQUE,
  `family_name` VARCHAR(256) NOT NULL,
  `family_type` ENUM('journal','series','monograph') NOT NULL,
  `description` TEXT NULL,
  `first_year_known` SMALLINT UNSIGNED NULL,
  `last_year_known` SMALLINT UNSIGNED NULL,
  `external_identifiers` JSON NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`family_id`),
  UNIQUE KEY `uq_family_root` (`family_root`),
  UNIQUE KEY `uq_family_code` (`family_code`),
  KEY `idx_family_type` (`family_type`),
  KEY `idx_first_year` (`first_year_known`),
  KEY `idx_last_year` (`last_year_known`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `publication_titles_t` (
  `title_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `family_id` BIGINT UNSIGNED NOT NULL,
  `canonical_title` VARCHAR(512) NOT NULL,
  `title_start_date` DATE NULL,
  `title_start_date_estimated` BOOLEAN NOT NULL DEFAULT FALSE,
  `title_end_date` DATE NULL,
  `title_end_date_estimated` BOOLEAN NOT NULL DEFAULT FALSE,
  `subtitle` VARCHAR(512) NULL,
  `abbreviation` VARCHAR(128) NULL,
  `publisher` VARCHAR(256) NULL,
  `publisher_city` VARCHAR(128) NULL,
  `publisher_country` VARCHAR(64) NULL,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`title_id`),
  KEY `idx_family_id` (`family_id`),
  KEY `idx_canonical_title` (`canonical_title`(100)),
  KEY `idx_title_dates` (`title_start_date`, `title_end_date`),
  KEY `idx_publisher` (`publisher`(100)),
  CONSTRAINT `fk_titles_family` FOREIGN KEY (`family_id`) REFERENCES `publication_families_t` (`family_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `publication_instances_t` (
  `instance_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `family_id` BIGINT UNSIGNED NOT NULL,
  `title_id` BIGINT UNSIGNED NOT NULL,
  `instance_key` VARCHAR(512) NOT NULL UNIQUE,
  `instance_type` ENUM('issue','volume','edition','part') NOT NULL DEFAULT 'issue',
  `title` VARCHAR(512) NULL,
  `publication_year` SMALLINT UNSIGNED NOT NULL,
  `publication_date` DATE NULL,
  `publication_date_display` VARCHAR(32) NOT NULL,
  `volume_label` VARCHAR(64) NULL,
  `volume_sort` INT NULL,
  `issue_label` VARCHAR(64) NULL,
  `issue_sort` INT NULL,
  `part_label` VARCHAR(64) NULL,
  `edition_label` VARCHAR(64) NULL,
  `edition_sort` INT NULL,
  `is_special_issue` BOOLEAN NOT NULL DEFAULT FALSE,
  `is_supplement` BOOLEAN NOT NULL DEFAULT FALSE,
  `language` VARCHAR(32) NOT NULL DEFAULT 'English',
  `extent_pages` INT UNSIGNED NULL,
  `extent_articles` INT UNSIGNED NULL,
  `extent_ads` INT UNSIGNED NULL,
  `rights_statement` VARCHAR(512) NULL,
  `is_manually_verified` BOOLEAN NOT NULL DEFAULT FALSE,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`instance_id`),
  UNIQUE KEY `uq_instance_key` (`instance_key`),
  KEY `idx_family_id` (`family_id`),
  KEY `idx_title_id` (`title_id`),
  KEY `idx_instance_type` (`instance_type`),
  KEY `idx_publication_year` (`publication_year`),
  KEY `idx_publication_date` (`publication_date`),
  KEY `idx_volume_sort` (`volume_sort`),
  KEY `idx_issue_sort` (`issue_sort`),
  KEY `idx_manually_verified` (`is_manually_verified`),
  CONSTRAINT `fk_instances_family` FOREIGN KEY (`family_id`) REFERENCES `publication_families_t` (`family_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_instances_title` FOREIGN KEY (`title_id`) REFERENCES `publication_titles_t` (`title_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TIER 2: CONTENT MANAGEMENT (3 tables)
-- ============================================================================

CREATE TABLE `containers_t` (
  `container_id` VARCHAR(128) NOT NULL,
  `source_system` VARCHAR(64) NOT NULL COMMENT 'e.g., "internet_archive", "hathitrust", "local"',
  `source_identifier` VARCHAR(255) NOT NULL,
  `source_url` VARCHAR(512) NULL,
  `container_type` VARCHAR(64) NOT NULL COMMENT 'e.g., "bound_volume", "microfilm", "journal_issue"',
  `extent_pages` INT UNSIGNED NULL,
  `download_status` ENUM('pending','in_progress','complete','failed') NOT NULL DEFAULT 'pending',
  `validation_status` ENUM('pending','passed','failed') NOT NULL DEFAULT 'pending',
  `downloaded_at` DATETIME NULL,
  `validated_at` DATETIME NULL,
  `raw_path` VARCHAR(512) NULL COMMENT 'Path in Raw layer',
  `working_path` VARCHAR(512) NULL COMMENT 'Path in Working layer',
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`container_id`),
  KEY `idx_source_identifier` (`source_identifier`),
  KEY `idx_download_status` (`download_status`),
  KEY `idx_validation_status` (`validation_status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `container_instances_t` (
  `link_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `container_id` VARCHAR(128) NOT NULL,
  `instance_id` BIGINT UNSIGNED NOT NULL,
  `start_page_in_container` INT UNSIGNED NULL,
  `end_page_in_container` INT UNSIGNED NULL,
  `start_page_in_instance` INT UNSIGNED NULL,
  `end_page_in_instance` INT UNSIGNED NULL,
  `is_preferred` BOOLEAN NOT NULL DEFAULT FALSE,
  `is_complete` BOOLEAN NOT NULL DEFAULT TRUE,
  `ocr_quality_score` DECIMAL(3,2) NULL COMMENT '0.00-1.00 confidence',
  `coverage_notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `uq_container_instance` (`container_id`, `instance_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_is_preferred` (`is_preferred`),
  CONSTRAINT `fk_ci_container` FOREIGN KEY (`container_id`) REFERENCES `containers_t` (`container_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ci_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `pages_t` (
  `page_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `container_id` VARCHAR(128) NOT NULL,
  `instance_id` BIGINT UNSIGNED NULL,
  `page_index` INT UNSIGNED NOT NULL COMMENT 'Sequential index within container (0-based)',
  `page_number_printed` VARCHAR(32) NULL,
  `page_label` VARCHAR(64) NULL,
  `page_type` ENUM('content','cover','index','toc','advertisement','plate','blank','other') NOT NULL DEFAULT 'content',
  `is_cover` BOOLEAN NOT NULL DEFAULT FALSE,
  `is_plate` BOOLEAN NOT NULL DEFAULT FALSE,
  `is_blank` BOOLEAN NOT NULL DEFAULT FALSE,
  `is_supplement` BOOLEAN NOT NULL DEFAULT FALSE,
  `has_ocr` BOOLEAN NOT NULL DEFAULT FALSE,
  `ocr_source` VARCHAR(32) NULL COMMENT 'e.g., "ia_hocr", "ia_djvu", "tesseract"',
  `ocr_confidence` DECIMAL(3,2) NULL,
  `ocr_word_count` INT UNSIGNED NULL,
  `ocr_text_snippet` VARCHAR(500) NULL,
  `is_manually_verified` BOOLEAN NOT NULL DEFAULT FALSE,
  `image_width` INT UNSIGNED NULL,
  `image_height` INT UNSIGNED NULL,
  `image_dpi` INT UNSIGNED NULL,
  `image_color_space` VARCHAR(32) NULL,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`page_id`),
  KEY `idx_container_id` (`container_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_page_index` (`container_id`, `page_index`),
  KEY `idx_page_type` (`page_type`),
  KEY `idx_has_ocr` (`has_ocr`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_pages_container` FOREIGN KEY (`container_id`) REFERENCES `containers_t` (`container_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_pages_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TIER 3: PROCESSING PIPELINE (6 tables)
-- ============================================================================

CREATE TABLE `segments_t` (
  `segment_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `instance_id` BIGINT UNSIGNED NOT NULL,
  `container_id` VARCHAR(128) NOT NULL,
  `segment_type` VARCHAR(64) NOT NULL,
  `title` VARCHAR(512) NULL,
  `is_title_ai_generated` BOOLEAN NOT NULL DEFAULT FALSE,
  `page_start_in_container` INT UNSIGNED NOT NULL,
  `page_end_in_container` INT UNSIGNED NOT NULL,
  `page_start_in_instance` INT UNSIGNED NOT NULL,
  `page_end_in_instance` INT UNSIGNED NOT NULL,
  `start_page_id` BIGINT UNSIGNED NOT NULL,
  `end_page_id` BIGINT UNSIGNED NOT NULL,
  `page_spread_stitched` BOOLEAN NOT NULL DEFAULT FALSE,
  `extractors_json` JSON NULL,
  `ocr_text_raw` MEDIUMTEXT NULL,
  `ocr_text_cleaned` MEDIUMTEXT NULL,
  `workflow_state` ENUM('stub_only','draft','qa_ready','verified','pd_cleared','publish_ready','published','needs_revision') NOT NULL DEFAULT 'stub_only',
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`segment_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_container_id` (`container_id`),
  KEY `idx_segment_type` (`segment_type`),
  KEY `idx_workflow_state` (`workflow_state`),
  KEY `idx_start_page_id` (`start_page_id`),
  KEY `idx_end_page_id` (`end_page_id`),
  KEY `idx_created_at` (`created_at`),
  FULLTEXT KEY `ft_segment_text` (`title`, `ocr_text_cleaned`),
  CONSTRAINT `fk_segments_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_segments_container` FOREIGN KEY (`container_id`) REFERENCES `containers_t` (`container_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_segments_start_page` FOREIGN KEY (`start_page_id`) REFERENCES `pages_t` (`page_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_segments_end_page` FOREIGN KEY (`end_page_id`) REFERENCES `pages_t` (`page_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `assets_t` (
  `asset_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `instance_id` BIGINT UNSIGNED NOT NULL,
  `asset_type` VARCHAR(64) NOT NULL,
  `title` VARCHAR(512) NULL,
  `description` TEXT NULL,
  `is_evidentiary` BOOLEAN NOT NULL DEFAULT TRUE,
  `derived_from_asset_id` BIGINT UNSIGNED NULL,
  `source_pages_json` JSON NULL,
  `file_location` VARCHAR(512) NOT NULL,
  `file_format` VARCHAR(32) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NULL,
  `width_pixels` INT UNSIGNED NULL,
  `height_pixels` INT UNSIGNED NULL,
  `resolution_dpi` INT UNSIGNED NULL,
  `workflow_state` ENUM('internal_only','qa_ready','approved','published') NOT NULL DEFAULT 'internal_only',
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`asset_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_asset_type` (`asset_type`),
  KEY `idx_workflow_state` (`workflow_state`),
  KEY `idx_is_evidentiary` (`is_evidentiary`),
  KEY `idx_derived_from` (`derived_from_asset_id`),
  CONSTRAINT `fk_assets_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_assets_derived` FOREIGN KEY (`derived_from_asset_id`) REFERENCES `assets_t` (`asset_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `entities_t` (
  `entity_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `entity_type` VARCHAR(64) NOT NULL,
  `canonical_name` VARCHAR(512) NOT NULL,
  `alternate_names` JSON NULL,
  `description` TEXT NULL,
  `entity_first_mentioned_year` SMALLINT UNSIGNED NULL,
  `entity_last_mentioned_year` SMALLINT UNSIGNED NULL,
  `external_identifiers` JSON NULL,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`entity_id`),
  UNIQUE KEY `uq_entity_name` (`entity_type`(32), `canonical_name`(255)),
  KEY `idx_entity_type` (`entity_type`),
  KEY `idx_first_year` (`entity_first_mentioned_year`),
  KEY `idx_last_year` (`entity_last_mentioned_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `segment_entities_t` (
  `link_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `segment_id` BIGINT UNSIGNED NOT NULL,
  `entity_id` BIGINT UNSIGNED NOT NULL,
  `mention_count` INT UNSIGNED NOT NULL DEFAULT 1,
  `mention_context` JSON NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `uq_segment_entity` (`segment_id`, `entity_id`),
  KEY `idx_entity_id` (`entity_id`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_se_segment` FOREIGN KEY (`segment_id`) REFERENCES `segments_t` (`segment_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_se_entity` FOREIGN KEY (`entity_id`) REFERENCES `entities_t` (`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `segment_assets_t` (
  `link_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `segment_id` BIGINT UNSIGNED NOT NULL,
  `asset_id` BIGINT UNSIGNED NOT NULL,
  `display_order` INT UNSIGNED NULL,
  `is_primary` BOOLEAN NULL DEFAULT FALSE,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `uq_segment_asset` (`segment_id`, `asset_id`),
  KEY `idx_asset_id` (`asset_id`),
  KEY `idx_display_order` (`display_order`),
  CONSTRAINT `fk_sa_segment` FOREIGN KEY (`segment_id`) REFERENCES `segments_t` (`segment_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sa_asset` FOREIGN KEY (`asset_id`) REFERENCES `assets_t` (`asset_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TIER 4: RIGHTS & PUBLISHING (2 tables)
-- ============================================================================

CREATE TABLE `rights_evaluations_t` (
  `evaluation_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `instance_id` BIGINT UNSIGNED NOT NULL,
  `rights_status` ENUM('pd_cleared','restricted','unknown','disputed') NOT NULL,
  `pd_rule_applied` VARCHAR(128) NULL,
  `pd_rule_explanation` TEXT NULL,
  `reviewer` VARCHAR(128) NOT NULL,
  `evaluation_date` DATE NOT NULL,
  `next_review_date` DATE NULL,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`evaluation_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_rights_status` (`rights_status`),
  KEY `idx_next_review_date` (`next_review_date`),
  KEY `idx_evaluation_date` (`evaluation_date`),
  CONSTRAINT `fk_rights_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `publish_bundles_t` (
  `bundle_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `instance_id` BIGINT UNSIGNED NOT NULL,
  `bundle_name` VARCHAR(256) NOT NULL,
  `segments_json` JSON NOT NULL,
  `assets_json` JSON NOT NULL,
  `published_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `published_by` VARCHAR(128) NOT NULL,
  `wiki_status` ENUM('draft','staged','published','failed','superseded') NOT NULL DEFAULT 'draft',
  `wiki_page_urls` JSON NULL,
  `last_error` TEXT NULL,
  `notes` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` VARCHAR(128) NOT NULL,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` VARCHAR(128) NULL,
  PRIMARY KEY (`bundle_id`),
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_published_date` (`published_date`),
  KEY `idx_wiki_status` (`wiki_status`),
  CONSTRAINT `fk_bundle_instance` FOREIGN KEY (`instance_id`) REFERENCES `publication_instances_t` (`instance_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SCHEMA COMPLETE
-- ============================================================================
COMMIT;
