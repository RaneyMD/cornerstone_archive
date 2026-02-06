<?php
/**
 * AJAX Endpoint: GET /api/process_results.php
 * Processes pending result files from console_inbox and updates job status.
 *
 * Result files come from:
 * 1. Supervisor writes to Worker_Outbox
 * 2. Synology Cloud Sync syncs to console_inbox
 * 3. This API processes them and marks jobs as complete
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

function process_pending_results($inbox_path, $db) {
    $results = [];

    if (!is_dir($inbox_path)) {
        return $results;
    }

    $files = array_diff(scandir($inbox_path), ['.', '..']);

    foreach ($files as $filename) {
        $filepath = $inbox_path . '/' . $filename;

        // Only process JSON files
        if (pathinfo($filepath, PATHINFO_EXTENSION) !== 'json') {
            continue;
        }

        $result = process_result_file($filepath, $db);
        if ($result) {
            $results[] = $result;
            // Clean up processed file
            unlink($filepath);
        }
    }

    return $results;
}

function process_result_file($filepath, $db) {
    $content = file_get_contents($filepath);
    if (!$content) {
        return null;
    }

    $data = json_decode($content, true);
    if (!$data) {
        return null;
    }

    $task_id = $data['task_id'] ?? null;
    $job_id = $data['job_id'] ?? null;
    $handler = $data['handler'] ?? null;
    $success = $data['success'] ?? false;
    $error = $data['error'] ?? null;
    $log_path = $data['log_path'] ?? null;
    $details = $data['details'] ?? [];

    // Find job by task_id or job_id
    if ($job_id) {
        $sql = "SELECT job_id FROM jobs_t WHERE job_id = ?";
        $result = $db->fetchAll($sql, [$job_id]);
    } else {
        $sql = "SELECT job_id FROM jobs_t WHERE task_id = ?";
        $result = $db->fetchAll($sql, [$task_id]);
    }

    if (empty($result)) {
        return [
            'task_id' => $task_id,
            'job_id' => $job_id,
            'status' => 'not_found',
            'message' => 'Job not found',
        ];
    }

    $job_id = $result[0]['job_id'];

    // Update job status with all available fields
    $state = $success ? 'succeeded' : 'failed';
    $sql = "UPDATE jobs_t SET state = ?, started_at = COALESCE(started_at, NOW()), finished_at = NOW(), last_error = ?, log_path = ?, attempts = attempts + 1 WHERE job_id = ?";
    $db->execute($sql, [$state, $error, $log_path, $job_id]);

    // Record completion in audit log
    $sql = "INSERT INTO audit_log_t (actor, action, target_type, target_id, details_json)
            VALUES (?, ?, ?, ?, ?)";
    $audit_details = [
        'success' => $success,
        'task_id' => $task_id,
        'job_id' => $job_id,
        'handler' => $handler,
        'error' => $error,
        'log_path' => $log_path,
        'result_file' => basename($filepath),
    ];
    // Include handler-specific details
    if (!empty($details)) {
        $audit_details['handler_details'] = $details;
    }
    $db->execute($sql, [
        'result_processor',
        'JOB_COMPLETED',
        'supervisor_control',
        (string)$job_id,
        json_encode($audit_details)
    ]);

    return [
        'task_id' => $task_id,
        'job_id' => $job_id,
        'handler' => $handler,
        'status' => $state,
        'success' => $success,
        'error' => $error,
    ];
}

try {
    // Get console_inbox path
    if (!defined('NAS_LOGS') || !defined('NAS_WORKER_OUTBOX')) {
        throw new Exception('NAS paths not configured');
    }

    // Console_inbox is on HostGator, not NAS
    // Need to define it in config if not already there
    $console_inbox = defined('CONSOLE_INBOX')
        ? CONSOLE_INBOX
        : dirname(CONSOLE_OUTBOX) . '/console_inbox';

    // Initialize database
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Process pending results
    $processed = process_pending_results($console_inbox, $db);

    http_response_code(200);
    echo json_encode([
        'success' => true,
        'processed_count' => count($processed),
        'results' => $processed,
        'timestamp' => date('c')
    ]);

} catch (Exception $e) {
    error_log("Process results API error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage(),
        'timestamp' => date('c')
    ]);
}
?>
