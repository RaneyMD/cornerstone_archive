<?php
/**
 * API Endpoint: GET /api/list_diagnostics.php?limit=50&offset=0
 * Returns list of diagnostic reports from diagnostics_t table
 */

session_start();
header('Content-Type: application/json');

if (!isset($_SESSION['username'])) {
    http_response_code(401);
    echo json_encode(['success' => false, 'error' => 'Unauthorized']);
    exit;
}

require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../app/Database.php';

$limit = (int)($_GET['limit'] ?? 50);
$offset = (int)($_GET['offset'] ?? 0);
$limit = max(1, min($limit, 200));
$offset = max(0, $offset);

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Get total count
    $count_row = $db->fetchOne('SELECT COUNT(*) AS total FROM diagnostics_t');
    $total = $count_row ? (int)$count_row['total'] : 0;

    // Get diagnostics ordered by newest first
    $sql = "SELECT
                diagnostic_id, task_id, worker_id, label, created_at,
                watcher_running, watcher_healthy, database_connected,
                disk_percent_free
            FROM diagnostics_t
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?";

    $diagnostics = $db->fetchAll($sql, [$limit, $offset]);

    echo json_encode([
        'success' => true,
        'diagnostics' => $diagnostics ?: [],
        'total' => $total,
        'limit' => $limit,
        'offset' => $offset
    ]);

} catch (Exception $e) {
    error_log('List diagnostics error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to list diagnostics']);
}
