<?php
/**
 * AJAX Endpoint: GET /api/heartbeat.php
 * Returns status of all watchers for dashboard real-time polling
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
    // Initialize components
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $nas_monitor = new NasMonitor(NAS_STATE);

    $manager = new WatcherManager(
        $db,
        $nas_monitor,
        WATCHERS,
        HEARTBEAT_STALE_THRESHOLD,
        HEARTBEAT_DEAD_THRESHOLD
    );

    // Get all watcher statuses
    $statuses = $manager->getAllWatchersStatus();
    $summary = $manager->getHealthSummary();

    // Build response
    $response = [
        'timestamp' => date('c'),
        'watchers' => array_values($statuses),
        'summary' => $summary
    ];

    http_response_code(200);
    echo json_encode($response);

} catch (Exception $e) {
    error_log("Heartbeat API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'error' => 'Failed to fetch watcher status',
        'timestamp' => date('c')
    ]);
}
