<?php
/**
 * AJAX Endpoint: GET /api/watcher.php?id={watcher_id}
 * Returns detailed status for a single watcher
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
    // Get watcher_id from query string
    $watcher_id = $_GET['id'] ?? null;
    if (!$watcher_id) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing required parameter: id']);
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

    // Get detailed status
    $status = $watcher->getStatus(HEARTBEAT_STALE_THRESHOLD, HEARTBEAT_DEAD_THRESHOLD);
    $pending_tasks = $watcher->getPendingTasks();
    $recent_results = $watcher->getRecentResults(10);
    $recent_logs = $watcher->getRecentLogs(50);

    $response = [
        'timestamp' => date('c'),
        'watcher' => $status,
        'pending_tasks' => $pending_tasks,
        'recent_results' => $recent_results,
        'recent_logs' => $recent_logs
    ];

    http_response_code(200);
    echo json_encode($response);

} catch (Exception $e) {
    error_log("Watcher detail API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'error' => 'Failed to fetch watcher details',
        'timestamp' => date('c')
    ]);
}
