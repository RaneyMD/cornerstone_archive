<?php
/**
 * API Endpoint: GET /api/get_audit_log.php?target_id=123&limit=50
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

$target_id = $_GET['target_id'] ?? null;
$limit = (int)($_GET['limit'] ?? 50);
$limit = max(1, min($limit, 200));

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $where = '';
    $params = [];
    if ($target_id !== null) {
        $where = 'WHERE target_id = ?';
        $params[] = $target_id;
    }

    $count_row = $db->fetchOne("SELECT COUNT(*) AS total FROM audit_log_t $where", $params);
    $total = $count_row ? (int)$count_row['total'] : 0;

    $sql = "SELECT audit_id, actor, action, target_type, target_id, created_at, details_json FROM audit_log_t $where ORDER BY created_at DESC LIMIT ?";
    $params[] = $limit;

    $entries = $db->fetchAll($sql, $params);
    $formatted = array_map(function ($entry) {
        $details = json_decode($entry['details_json'], true);
        if ($details === null && $entry['details_json']) {
            $details = $entry['details_json'];
        }
        return [
            'audit_id' => (int)$entry['audit_id'],
            'actor' => $entry['actor'],
            'action' => $entry['action'],
            'target_type' => $entry['target_type'],
            'target_id' => $entry['target_id'],
            'created_at' => $entry['created_at'],
            'details' => $details
        ];
    }, $entries);

    echo json_encode([
        'success' => true,
        'audit_entries' => $formatted,
        'total' => $total,
        'limit' => $limit
    ]);
} catch (Exception $e) {
    error_log('Get audit log error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to fetch audit log']);
}
