<?php
/**
 * Cornerstone Archive Console Configuration
 * Copy this file to config.php and fill in actual values
 */

// ============================================================================
// DATABASE CONFIGURATION
// ============================================================================
define('DB_HOST', getenv('DB_HOST') ?: 'localhost');
define('DB_USER', getenv('DB_USER') ?: 'raneywor_csa_app');
define('DB_PASS', getenv('DB_PASS') ?: 'your_password_here');
define('DB_NAME', getenv('DB_NAME') ?: 'raneywor_csa_state');

// ============================================================================
// AUTHENTICATION
// ============================================================================
define('CONSOLE_USERNAME', getenv('CONSOLE_USERNAME') ?: 'admin');
// Generate with: php -r "echo password_hash('password', PASSWORD_BCRYPT);"
define('CONSOLE_PASSWORD_HASH', getenv('CONSOLE_PASSWORD_HASH') ?:
    '$2y$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcg7b3XeKeUxWdeS86E36P4/KFm');

// ============================================================================
// WATCHER CONFIGURATION
// ============================================================================
define('WATCHERS', [
    'orionmx' => [
        'id' => 'OrionMX',
        'hostname' => 'OrionMX',
        'status' => 'primary',
        'heartbeat_file' => 'watcher_heartbeat_orionmx.json'
    ],
    'orionmega' => [
        'id' => 'OrionMega',
        'hostname' => 'OrionMega',
        'status' => 'secondary',
        'heartbeat_file' => 'watcher_heartbeat_orionmega.json'
    ]
]);

// ============================================================================
// NAS PATHS (Windows UNC)
// ============================================================================
define('NAS_ROOT', '\\\\RaneyHQ\\Michael\\02_Projects\\Cornerstone_Archive');
define('NAS_STATE', NAS_ROOT . '\\00_STATE');
define('NAS_LOGS', NAS_ROOT . '\\05_LOGS');
define('NAS_WORKER_INBOX', NAS_LOGS . '\\Worker_Inbox');
define('NAS_WORKER_OUTBOX', NAS_LOGS . '\\Worker_Outbox');

// ============================================================================
// SESSION CONFIGURATION
// ============================================================================
define('SESSION_TIMEOUT', 3600);  // 1 hour in seconds
define('SESSION_NAME', 'CORNERSTONE_SESSID');

// ============================================================================
// UI CONFIGURATION
// ============================================================================
define('AUTO_REFRESH_INTERVAL', 5000);  // milliseconds (5 seconds)
define('HEARTBEAT_STALE_THRESHOLD', 60);  // seconds (2x poll interval for dev)
define('HEARTBEAT_DEAD_THRESHOLD', 600);  // 10 minutes

// ============================================================================
// APPLICATION SETTINGS
// ============================================================================
define('APP_NAME', 'Cornerstone Archive Console');
define('APP_VERSION', '1.0.0');
define('DEBUG_MODE', getenv('DEBUG_MODE') ?: false);
define('LOG_FILE', getenv('LOG_FILE') ?: '/tmp/console.log');
