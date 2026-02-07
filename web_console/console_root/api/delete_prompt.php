<?php
/**
 * API Endpoint: POST /api/delete_prompt.php
 * Soft-deletes a prompt by setting is_active = 0.
 *
 * Accepts:
 *   - prompt_id (int): ID of the prompt to delete
 *
 * Returns:
 *   - Success/failure message
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

$input = json_decode(file_get_contents('php://input'), true);
if (!$input) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid JSON payload']);
    exit;
}

$prompt_id = $input['prompt_id'] ?? 0;
if (!$prompt_id) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Missing prompt_id']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Verify prompt exists
    $prompt = $db->fetchOne(
        'SELECT prompt_id FROM prompts_t WHERE prompt_id = ? AND is_active = 1',
        [$prompt_id]
    );

    if (!$prompt) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Prompt not found']);
        exit;
    }

    // Soft delete
    $db->execute(
        'UPDATE prompts_t SET is_active = 0 WHERE prompt_id = ?',
        [$prompt_id]
    );

    // Audit log
    $db->insert('audit_log_t', [
        'actor' => 'console',
        'action' => 'DELETE_PROMPT',
        'target_type' => 'prompt',
        'target_id' => (string)$prompt_id,
        'details_json' => json_encode([
            'prompt_id' => $prompt_id,
            'deleted_by' => $_SESSION['username']
        ])
    ]);

    echo json_encode([
        'success' => true,
        'message' => 'Prompt deleted successfully'
    ]);

} catch (Exception $e) {
    error_log('Delete prompt error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to delete prompt']);
}
