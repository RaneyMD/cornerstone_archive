<?php
/**
 * AJAX Endpoint: GET /api/supervisor_heartbeat.php
 * Returns supervisor heartbeat status for all configured watchers
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

try {
    // Initialize database
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Get supervisor heartbeats for all configured watchers
    $supervisors = [];

    foreach (WATCHERS as $watcher_config) {
        $watcher_id = $watcher_config['id'];
        $supervisor_id = "supervisor_{$watcher_id}";

        // Query workers_t for supervisor entry
        $sql = "SELECT worker_id, last_heartbeat_at, status_summary FROM workers_t WHERE worker_id = ?";
        $result = $db->fetchAll($sql, [$supervisor_id]);

        if (!empty($result)) {
            $row = $result[0];

            // Parse status from status_summary
            $status_summary = $row['status_summary'] ?? '';
            $is_success = strpos($status_summary, 'Supervisor OK') === 0;
            $age_seconds = null;

            if ($row['last_heartbeat_at']) {
                $last_time = strtotime($row['last_heartbeat_at']);
                $now = time();
                $age_seconds = $now - $last_time;
            }

            // Determine supervisor status
            if ($age_seconds === null) {
                $supervisor_status = 'offline';
            } elseif ($age_seconds > 300) { // 5 minutes
                $supervisor_status = 'stale';
            } elseif (!$is_success) {
                $supervisor_status = 'error';
            } else {
                $supervisor_status = 'ok';
            }

            $supervisors[] = [
                'watcher_id' => $watcher_id,
                'supervisor_id' => $supervisor_id,
                'status' => $supervisor_status,
                'status_summary' => $status_summary,
                'last_heartbeat_at' => $row['last_heartbeat_at'],
                'age_seconds' => $age_seconds
            ];
        } else {
            // No supervisor heartbeat yet
            $supervisors[] = [
                'watcher_id' => $watcher_id,
                'supervisor_id' => $supervisor_id,
                'status' => 'offline',
                'status_summary' => 'No supervisor heartbeat',
                'last_heartbeat_at' => null,
                'age_seconds' => null
            ];
        }
    }

    // Build response
    $response = [
        'timestamp' => date('c'),
        'supervisors' => $supervisors
    ];

    http_response_code(200);
    echo json_encode($response);

} catch (Exception $e) {
    error_log("Supervisor heartbeat API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'error' => 'Failed to fetch supervisor status',
        'timestamp' => date('c')
    ]);
}
