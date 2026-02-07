<?php
/**
 * API Endpoint: POST /api/upload_prompt.php
 * Handles Claude Code prompt file uploads and stores metadata.
 *
 * Accepts:
 *   - prompt_name (string, max 100 chars)
 *   - prompt_file (file, .md or .txt, max 100KB)
 *
 * Returns:
 *   - prompt_id, sequence_number, filename on success
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

// Validate input
$prompt_name = $_POST['prompt_name'] ?? '';
if (!$prompt_name || strlen($prompt_name) > 100) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid or missing prompt_name']);
    exit;
}

if (!preg_match('/^[a-zA-Z0-9\s\-_]+$/', $prompt_name)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Prompt name contains invalid characters']);
    exit;
}

// Validate file upload
if (!isset($_FILES['prompt_file'])) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'No file uploaded']);
    exit;
}

$file = $_FILES['prompt_file'];
$max_size = 100 * 1024;  // 100KB

if ($file['error'] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'File upload error']);
    exit;
}

if ($file['size'] > $max_size) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'File exceeds 100KB limit']);
    exit;
}

// Validate MIME type
$mime_type = mime_content_type($file['tmp_name']);
$allowed_mimes = ['text/plain', 'text/markdown', 'text/x-markdown'];
if (!in_array($mime_type, $allowed_mimes, true)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid file type. Only .txt and .md files allowed']);
    exit;
}

// Validate file extension
$extension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
if (!in_array($extension, ['md', 'txt'], true)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid file extension. Only .md and .txt allowed']);
    exit;
}

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Get next sequence number
    $result = $db->fetchOne('SELECT MAX(sequence_number) as max_seq FROM prompts_t WHERE is_active = 1');
    $next_seq = ($result && $result['max_seq']) ? $result['max_seq'] + 1 : 1;
    $sequence_str = str_pad($next_seq, 4, '0', STR_PAD_LEFT);

    // Sanitize original filename
    $original_name = pathinfo($file['name'], PATHINFO_FILENAME);
    $sanitized_name = preg_replace('/[^a-zA-Z0-9_-]/', '_', $original_name);
    $final_filename = $sequence_str . '_' . $sanitized_name . '.' . $extension;

    // Ensure PROMPTS_PATH directory exists
    $prompts_dir = rtrim(PROMPTS_PATH, '/');
    if (!is_dir($prompts_dir)) {
        if (!mkdir($prompts_dir, 0775, true) && !is_dir($prompts_dir)) {
            throw new Exception('Failed to create prompts directory');
        }
    }

    // Move file to prompts directory
    $prompt_path = $prompts_dir . '/' . $final_filename;
    if (!move_uploaded_file($file['tmp_name'], $prompt_path)) {
        throw new Exception('Failed to save prompt file');
    }

    // Record metadata in database
    $prompt_id = $db->insert('prompts_t', [
        'sequence_number' => $next_seq,
        'prompt_name' => $prompt_name,
        'prompt_filename' => $final_filename,
        'file_size' => $file['size'],
        'uploaded_by' => $_SESSION['username'],
        'uploaded_at' => gmdate('Y-m-d H:i:s')
    ]);

    // Audit log
    $db->insert('audit_log_t', [
        'actor' => 'console',
        'action' => 'UPLOAD_PROMPT',
        'target_type' => 'prompt',
        'target_id' => (string)$prompt_id,
        'details_json' => json_encode([
            'prompt_id' => $prompt_id,
            'sequence_number' => $next_seq,
            'prompt_name' => $prompt_name,
            'filename' => $final_filename,
            'file_size' => $file['size'],
            'uploader' => $_SESSION['username']
        ])
    ]);

    echo json_encode([
        'success' => true,
        'message' => 'Prompt uploaded successfully',
        'prompt_id' => $prompt_id,
        'sequence_number' => $next_seq,
        'filename' => $final_filename
    ]);

} catch (Exception $e) {
    error_log('Upload prompt error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to upload prompt']);
}
