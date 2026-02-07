<?php
/**
 * API Endpoint: GET /api/list_prompts.php
 * Returns list of all active prompts for browsing and selection.
 *
 * Returns:
 *   - Array of prompts with metadata, ordered by sequence_number DESC (newest first)
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

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    $prompts = $db->fetchAll(
        'SELECT prompt_id, sequence_number, prompt_name, prompt_filename, file_size, uploaded_by, uploaded_at
         FROM prompts_t
         WHERE is_active = 1
         ORDER BY sequence_number DESC'
    );

    echo json_encode([
        'success' => true,
        'prompts' => $prompts ?: []
    ]);

} catch (Exception $e) {
    error_log('List prompts error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to list prompts']);
}
