<?php
/**
 * AJAX Endpoint: GET /api/logs.php?watcher_id={id}&lines=50
 * Returns recent log lines for a specific watcher
 */

session_start();
header('Content-Type: application/json');

// Check authentication
if (!isset($_SESSION['username'])) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../app/Database.php';
require_once __DIR__ . '/../app/NasMonitor.php';
require_once __DIR__ . '/../app/Watcher.php';
require_once __DIR__ . '/../app/WatcherManager.php';

try {
    // Get parameters
    $watcher_id = $_GET['watcher_id'] ?? null;
    $lines = (int)($_GET['lines'] ?? 50);
    $lines = max(1, min($lines, 1000));  // Clamp between 1-1000

    if (!$watcher_id) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing required parameter: watcher_id']);
        exit;
    }

    // Sanitize watcher_id
    $watcher_id = preg_replace('/[^a-z0-9_-]/i', '', $watcher_id);

    // Initialize components
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $nas_monitor = new NasMonitor($db, NAS_STATE);

    $manager = new WatcherManager(
        $db,
        $nas_monitor,
        WATCHERS,
        HEARTBEAT_STALE_THRESHOLD,
        HEARTBEAT_DEAD_THRESHOLD
    );

    // Get watcher
    $watcher = $manager->getWatcher($watcher_id);
    if (!$watcher) {
        http_response_code(404);
        echo json_encode(['error' => "Watcher not found: $watcher_id"]);
        exit;
    }

    // Get logs from database
    $logs = $watcher->getRecentLogs($lines);

    // Count total logs in database
    $total = $db->fetchOne(
        "SELECT COUNT(*) as count FROM watcher_logs_t WHERE watcher_id = ?",
        [$watcher_id]
    );

    $response = [
        'timestamp' => date('c'),
        'watcher_id' => $watcher_id,
        'logs' => $logs,
        'returned_lines' => count($logs),
        'total_lines' => (int)($total['count'] ?? 0)
    ];

    http_response_code(200);
    echo json_encode($response);

} catch (Exception $e) {
    error_log("Logs API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'error' => 'Failed to fetch logs',
        'timestamp' => date('c')
    ]);
}
