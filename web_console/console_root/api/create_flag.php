<?php
/**
 * API Endpoint: POST /api/create_flag.php
 * Creates supervisor control or job task flags.
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

$flag_type = $input['flag_type'] ?? '';
$handler = $input['handler'] ?? '';
$worker_id = $input['worker_id'] ?? '';
$label = $input['label'] ?? null;
$params = $input['params'] ?? [];
$prompt_spec = $input['prompt_spec'] ?? null;

$allowed_supervisor_handlers = [
    'pause_watcher',
    'resume_watcher',
    'restart_watcher',
    'update_code',
    'update_code_deps',
    'rollback_code',
    'diagnostics',
    'verify_db'
];
$allowed_job_handlers = ['acquire_source'];

if (!in_array($flag_type, ['supervisor_control', 'job'], true)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Invalid flag type']);
    exit;
}

$label_validation = validate_label($label);
if (!$label_validation['valid']) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => $label_validation['error']]);
    exit;
}

// Validate prompt_spec if present
if ($prompt_spec !== null) {
    if (!isset($prompt_spec['prompt_id'])) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'prompt_spec missing prompt_id']);
        exit;
    }

    // Will validate prompt exists after db connection
}

if ($flag_type === 'supervisor_control') {
    if (!in_array($handler, $allowed_supervisor_handlers, true)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'Invalid supervisor handler']);
        exit;
    }
    if (!$worker_id) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'worker_id is required']);
        exit;
    }
} else {
    if (!in_array($handler, $allowed_job_handlers, true)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'Invalid job handler']);
        exit;
    }
    if (empty($params)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'params are required']);
        exit;
    }
}

$task_id = generate_task_id($flag_type === 'job' ? 'job' : 'task');

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();

    // Validate prompt if specified
    if ($prompt_spec !== null) {
        $prompt = $db->fetchOne(
            'SELECT prompt_id, prompt_filename FROM prompts_t WHERE prompt_id = ? AND is_active = 1',
            [$prompt_spec['prompt_id']]
        );
        if (!$prompt) {
            http_response_code(400);
            echo json_encode(['success' => false, 'error' => 'Prompt not found or inactive']);
            exit;
        }

        // Validate model if specified
        if (isset($prompt_spec['model'])) {
            $allowed_models = ['opus', 'sonnet', 'haiku'];
            if (!in_array($prompt_spec['model'], $allowed_models, true)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Invalid model']);
                exit;
            }
        }

        // Add prompt filename to spec for watcher
        $prompt_spec['prompt_filename'] = $prompt['prompt_filename'];
    }

    $target_ref = $flag_type === 'supervisor_control'
        ? $handler . ':' . $worker_id
        : summarize_params($params);

    $job_id = $db->insert('jobs_t', [
        'job_type' => $flag_type === 'supervisor_control' ? 'supervisor_control' : $handler,
        'target_ref' => $target_ref,
        'label' => $label,
        'state' => 'queued',
        'task_id' => $task_id
    ]);

    $db->insert('audit_log_t', [
        'actor' => 'console',
        'action' => 'CREATE_FLAG',
        'target_type' => $flag_type === 'supervisor_control' ? 'supervisor_control' : 'job_task',
        'target_id' => (string)$job_id,
        'details_json' => json_encode([
            'handler' => $handler,
            'worker_id' => $worker_id,
            'label' => $label,
            'params' => $params,
            'task_id' => $task_id
        ])
    ]);

    $flag_data = [
        'task_id' => $task_id,
        'job_id' => $job_id,
        'handler' => $handler,
        'label' => $label,
        'params' => $params
    ];

    // Include prompt_spec if present
    if ($prompt_spec !== null) {
        $flag_data['prompt_spec'] = $prompt_spec;
    }

    if ($flag_type === 'supervisor_control') {
        $flag_data['worker_id'] = $worker_id;
        $flag_name = "supervisor_{$handler}_{$worker_id}_{$task_id}.flag";
    } else {
        $flag_name = "job_{$handler}_{$task_id}.flag";
    }

    $flag_path = rtrim(CONSOLE_OUTBOX, '/').'/'.$flag_name;
    if (!write_flag_atomically($flag_path, $flag_data)) {
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => 'Failed to write flag file']);
        exit;
    }

    // Copy prompt file to CONSOLE_OUTBOX if specified
    if ($prompt_spec !== null) {
        $prompt_source = rtrim(PROMPTS_PATH, '/') . '/' . $prompt_spec['prompt_filename'];
        $prompt_dest = rtrim(CONSOLE_OUTBOX, '/') . '/' . $task_id . '_prompt.md';

        if (!copy($prompt_source, $prompt_dest)) {
            error_log("Warning: Failed to copy prompt file: $prompt_source to $prompt_dest");
            // Don't fail the flag creation, just log warning
        }
    }

    echo json_encode([
        'success' => true,
        'job_id' => $job_id,
        'task_id' => $task_id,
        'message' => 'Flag created successfully',
        'flag_file' => $flag_path
    ]);
} catch (Exception $e) {
    error_log('Create flag error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to create flag']);
}

function generate_task_id($prefix) {
    $timestamp = gmdate('Ymd_His');
    $suffix = substr(str_shuffle('abcdefghijklmnopqrstuvwxyz0123456789'), 0, 4);
    return $prefix . '_' . $timestamp . '_' . $suffix;
}

function validate_label($label) {
    if ($label === null || $label === '') {
        return ['valid' => true, 'error' => ''];
    }
    if (strlen($label) > 100) {
        return ['valid' => false, 'error' => 'Label too long'];
    }
    if (!preg_match('/^[A-Za-z0-9 _-]+$/', $label)) {
        return ['valid' => false, 'error' => 'Label contains invalid characters'];
    }
    return ['valid' => true, 'error' => ''];
}

function summarize_params($params) {
    $serialized = json_encode($params);
    if (strlen($serialized) > 512) {
        return substr($serialized, 0, 509) . '...';
    }
    return $serialized;
}

function write_flag_atomically($path, $data) {
    $dir = dirname($path);
    if (!is_dir($dir)) {
        if (!mkdir($dir, 0775, true) && !is_dir($dir)) {
            return false;
        }
    }

    $tmp_path = $path . '.tmp';
    $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    if (file_put_contents($tmp_path, $json) === false) {
        return false;
    }
    return rename($tmp_path, $path);
}
