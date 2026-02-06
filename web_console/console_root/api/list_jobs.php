<?php
/**
 * API Endpoint: GET /api/list_jobs.php?state=queued&limit=50&offset=0
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

$state = $_GET['state'] ?? null;
$limit = (int)($_GET['limit'] ?? 50);
$offset = (int)($_GET['offset'] ?? 0);
$limit = max(1, min($limit, 200));
$offset = max(0, $offset);

$allowed_states = ['queued', 'running', 'succeeded', 'failed', 'blocked', 'canceled'];
if ($state !== null && !in_array($state, $allowed_states, true)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid state']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $where = '';
    $params = [];
    if ($state !== null) {
        $where = 'WHERE state = ?';
        $params[] = $state;
    }

    $count_row = $db->fetchOne("SELECT COUNT(*) AS total FROM jobs_t $where", $params);
    $total = $count_row ? (int)$count_row['total'] : 0;

    $sql = "SELECT job_id, job_type, label, state, created_at, attempts FROM jobs_t $where ORDER BY created_at DESC LIMIT ? OFFSET ?";
    $params[] = $limit;
    $params[] = $offset;

    $jobs = $db->fetchAll($sql, $params);

    echo json_encode([
        'success' => true,
        'jobs' => $jobs,
        'total' => $total,
        'limit' => $limit,
        'offset' => $offset
    ]);
} catch (Exception $e) {
    error_log('List jobs error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to list jobs']);
}
