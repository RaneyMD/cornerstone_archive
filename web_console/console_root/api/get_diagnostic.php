<?php
/**
 * API Endpoint: GET /api/get_diagnostic.php?diagnostic_id=XXX
 * Returns full diagnostic report with parsed JSON
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

$diagnostic_id = isset($_GET['diagnostic_id']) ? (int)$_GET['diagnostic_id'] : 0;
if (!$diagnostic_id) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Missing diagnostic_id parameter']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $diagnostic = $db->fetchOne(
        'SELECT * FROM diagnostics_t WHERE diagnostic_id = ?',
        [$diagnostic_id]
    );

    if (!$diagnostic) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Diagnostic not found']);
        exit;
    }

    // Parse JSON report
    $report = json_decode($diagnostic['report_json'], true);

    echo json_encode([
        'success' => true,
        'diagnostic' => [
            'diagnostic_id' => $diagnostic['diagnostic_id'],
            'task_id' => $diagnostic['task_id'],
            'worker_id' => $diagnostic['worker_id'],
            'label' => $diagnostic['label'],
            'created_at' => $diagnostic['created_at'],
            'watcher_running' => (bool)$diagnostic['watcher_running'],
            'watcher_healthy' => (bool)$diagnostic['watcher_healthy'],
            'database_connected' => (bool)$diagnostic['database_connected'],
            'disk_percent_free' => (float)$diagnostic['disk_percent_free'],
            'report' => $report
        ]
    ]);

} catch (Exception $e) {
    error_log('Get diagnostic error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to retrieve diagnostic']);
}
