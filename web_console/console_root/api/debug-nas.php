<?php
/**
 * DEBUG ENDPOINT: Check NAS accessibility and heartbeat files
 * Remove this after debugging!
 */

session_start();

// Check authentication
if (!isset($_SESSION['username'])) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

require_once __DIR__ . '/../config/config.php';

header('Content-Type: application/json');

$debug = [
    'timestamp' => date('c'),
    'nas_state_path' => NAS_STATE,
    'path_exists' => is_dir(NAS_STATE),
    'path_readable' => is_readable(NAS_STATE),
    'path_writable' => is_writable(NAS_STATE),
    'files_found' => [],
    'file_contents' => []
];

// Try to read directory
if (is_dir(NAS_STATE)) {
    try {
        $files = glob(NAS_STATE . '\\watcher_heartbeat_*.json');
        if ($files === false) {
            $debug['glob_error'] = 'glob() returned false';
        } else {
            $debug['files_found'] = array_map('basename', $files);

            // Try to read each file
            foreach ($files as $filepath) {
                $filename = basename($filepath);
                $debug['file_contents'][$filename] = [
                    'path' => $filepath,
                    'exists' => file_exists($filepath),
                    'readable' => is_readable($filepath),
                    'size' => file_exists($filepath) ? filesize($filepath) : null,
                    'modified' => file_exists($filepath) ? date('c', filemtime($filepath)) : null,
                    'content' => null,
                    'json_valid' => false
                ];

                // Try to read content
                if (file_exists($filepath) && is_readable($filepath)) {
                    $content = file_get_contents($filepath);
                    if ($content !== false) {
                        $debug['file_contents'][$filename]['content'] = json_decode($content, true);
                        $debug['file_contents'][$filename]['json_valid'] = (json_decode($content) !== null);
                    } else {
                        $debug['file_contents'][$filename]['read_error'] = 'file_get_contents() failed';
                    }
                }
            }
        }
    } catch (Exception $e) {
        $debug['exception'] = $e->getMessage();
    }
} else {
    $debug['path_error'] = 'NAS_STATE path is not accessible';
}

http_response_code(200);
echo json_encode($debug, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
