<?php
/**
 * API Endpoint: GET /api/get_prompt.php?prompt_id=XXX
 * Retrieves prompt file content and metadata for preview.
 *
 * Parameters:
 *   - prompt_id (int): ID of the prompt to retrieve
 *
 * Returns:
 *   - Prompt metadata and full file content
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

$prompt_id = isset($_GET['prompt_id']) ? (int)$_GET['prompt_id'] : 0;
if (!$prompt_id) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Missing prompt_id parameter']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $prompt = $db->fetchOne(
        'SELECT prompt_id, sequence_number, prompt_name, prompt_filename, file_size, uploaded_by, uploaded_at
         FROM prompts_t
         WHERE prompt_id = ? AND is_active = 1',
        [$prompt_id]
    );

    if (!$prompt) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Prompt not found']);
        exit;
    }

    // Read prompt file content
    $prompt_file = rtrim(PROMPTS_PATH, '/') . '/' . $prompt['prompt_filename'];
    if (!file_exists($prompt_file)) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Prompt file not found on disk']);
        exit;
    }

    $content = file_get_contents($prompt_file);
    if ($content === false) {
        throw new Exception('Failed to read prompt file');
    }

    echo json_encode([
        'success' => true,
        'prompt' => [
            'prompt_id' => $prompt['prompt_id'],
            'sequence_number' => $prompt['sequence_number'],
            'prompt_name' => $prompt['prompt_name'],
            'prompt_filename' => $prompt['prompt_filename'],
            'content' => $content
        ]
    ]);

} catch (Exception $e) {
    error_log('Get prompt error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to retrieve prompt']);
}
