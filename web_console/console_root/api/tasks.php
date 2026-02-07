<?php
/**
 * AJAX Endpoint: GET /api/tasks.php?type=pending|recent&limit=10
 * Returns pending or recent task lists
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
    $type = $_GET['type'] ?? 'pending';  // 'pending' or 'recent'
    $limit = (int)($_GET['limit'] ?? 10);
    $limit = max(1, min($limit, 100));  // Clamp between 1-100

    // Sanitize type
    if (!in_array($type, ['pending', 'recent'])) {
        http_response_code(400);
        echo json_encode(['error' => "Invalid type: $type"]);
        exit;
    }

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

    $response = [
        'timestamp' => date('c'),
        'type' => $type
    ];

    if ($type === 'pending') {
        // Get pending jobs
        $sql = "SELECT
                    job_id,
                    job_type,
                    label,
                    state,
                    created_at,
                    attempts
                FROM jobs_t
                WHERE state = 'queued'
                ORDER BY created_at ASC
                LIMIT ?";

        $tasks = $db->fetchAll($sql, [$limit]);
        $response['count'] = count($tasks);
        $response['tasks'] = $tasks;

    } else {  // recent
        // Get recently completed tasks
        $tasks = $manager->getRecentResults($limit);
        $response['count'] = count($tasks);
        $response['tasks'] = $tasks;
    }

    http_response_code(200);
    echo json_encode($response);

} catch (Exception $e) {
    error_log("Tasks API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'error' => 'Failed to fetch tasks',
        'timestamp' => date('c')
    ]);
}
