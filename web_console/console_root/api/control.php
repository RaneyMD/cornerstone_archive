<?php
/**
 * AJAX Endpoint: POST /api/control.php
 * Handles control actions (restart, refresh, etc.) for watchers
 *
 * Expected JSON body:
 * {
 *   "action": "restart_watcher",
 *   "watcher_id": "OrionMX"
 * }
 */

session_start();
header('Content-Type: application/json');

// Check authentication
if (!isset($_SESSION['username'])) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

// Only allow POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../app/Database.php';
require_once __DIR__ . '/../app/NasMonitor.php';
require_once __DIR__ . '/../app/Watcher.php';
require_once __DIR__ . '/../app/WatcherManager.php';

try {
    // Parse JSON body
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid JSON']);
        exit;
    }

    $action = $input['action'] ?? null;
    $watcher_id = $input['watcher_id'] ?? null;

    if (!$action || !$watcher_id) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing required fields: action, watcher_id']);
        exit;
    }

    // Sanitize inputs
    $action = preg_replace('/[^a-z_]/', '', strtolower($action));
    $watcher_id = preg_replace('/[^a-z0-9_-]/i', '', $watcher_id);

    // Validate action
    $allowed_actions = ['restart_watcher', 'refresh_status', 'create_test_task'];
    if (!in_array($action, $allowed_actions)) {
        http_response_code(400);
        echo json_encode(['error' => "Invalid action: $action"]);
        exit;
    }

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

    // Execute control action
    $result = $manager->broadcastControlAction($watcher_id, str_replace('_watcher', '', $action));

    http_response_code($result['success'] ? 200 : 400);
    echo json_encode($result);

} catch (Exception $e) {
    error_log("Control API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to execute control action',
        'timestamp' => date('c')
    ]);
}
