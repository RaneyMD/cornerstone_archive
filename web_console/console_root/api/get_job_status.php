<?php
/**
 * API Endpoint: GET /api/get_job_status.php?job_id=123
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

$job_id = isset($_GET['job_id']) ? (int)$_GET['job_id'] : 0;
if ($job_id <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid job_id']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $job = $db->fetchOne('SELECT * FROM jobs_t WHERE job_id = ?', [$job_id]);
    if (!$job) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Job not found']);
        exit;
    }

    echo json_encode([
        'success' => true,
        'job_id' => (int)$job['job_id'],
        'job_type' => $job['job_type'],
        'label' => $job['label'],
        'state' => $job['state'],
        'created_at' => $job['created_at'],
        'started_at' => $job['started_at'],
        'finished_at' => $job['finished_at'],
        'result_path' => $job['result_path'],
        'attempts' => (int)$job['attempts']
    ]);
} catch (Exception $e) {
    error_log('Get job status error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to fetch job status']);
}
