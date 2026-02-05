<?php
/**
 * DEBUG ENDPOINT: Diagnose heartbeat detection issues
 * Shows database connection, workers_t contents, and NasMonitor behavior
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
require_once __DIR__ . '/../app/Database.php';
require_once __DIR__ . '/../app/NasMonitor.php';

header('Content-Type: application/json');

$debug = [
    'timestamp' => date('c'),
    'steps' => []
];

// Step 1: Test database connection
$debug['steps']['database_connection'] = [
    'status' => 'testing...',
    'details' => null,
    'error' => null
];

try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();
    $debug['steps']['database_connection']['status'] = 'connected';
    $debug['steps']['database_connection']['details'] = [
        'host' => DB_HOST,
        'database' => DB_NAME,
        'user' => DB_USER
    ];
} catch (Exception $e) {
    $debug['steps']['database_connection']['status'] = 'failed';
    $debug['steps']['database_connection']['error'] = $e->getMessage();
    http_response_code(500);
    echo json_encode($debug, JSON_PRETTY_PRINT);
    exit;
}

// Step 2: Query workers_t table
$debug['steps']['workers_table'] = [
    'status' => 'querying...',
    'row_count' => null,
    'rows' => [],
    'error' => null
];

try {
    $rows = $db->fetchAll("SELECT * FROM workers_t ORDER BY worker_id");
    $debug['steps']['workers_table']['status'] = 'success';
    $debug['steps']['workers_table']['row_count'] = count($rows);
    $debug['steps']['workers_table']['rows'] = $rows;
} catch (Exception $e) {
    $debug['steps']['workers_table']['status'] = 'failed';
    $debug['steps']['workers_table']['error'] = $e->getMessage();
}

// Step 3: Test NasMonitor with database
$debug['steps']['nas_monitor'] = [
    'status' => 'testing...',
    'all_heartbeats' => [],
    'error' => null
];

try {
    $nas_monitor = new NasMonitor($db, NAS_STATE);
    $heartbeats = $nas_monitor->readAllHeartbeats();
    $debug['steps']['nas_monitor']['status'] = 'success';
    $debug['steps']['nas_monitor']['all_heartbeats'] = $heartbeats;
} catch (Exception $e) {
    $debug['steps']['nas_monitor']['status'] = 'failed';
    $debug['steps']['nas_monitor']['error'] = $e->getMessage();
}

// Step 4: Test individual watcher
$debug['steps']['individual_watcher'] = [
    'status' => 'testing...',
    'watcher_id' => 'OrionMX',
    'data' => null,
    'error' => null
];

try {
    $heartbeat = $nas_monitor->readHeartbeat('OrionMX');
    $debug['steps']['individual_watcher']['status'] = $heartbeat ? 'found' : 'not_found';
    $debug['steps']['individual_watcher']['data'] = $heartbeat;
} catch (Exception $e) {
    $debug['steps']['individual_watcher']['status'] = 'failed';
    $debug['steps']['individual_watcher']['error'] = $e->getMessage();
}

// Step 5: Test /api/heartbeat.php logic
$debug['steps']['heartbeat_api_simulation'] = [
    'status' => 'testing...',
    'watchers' => [],
    'error' => null
];

try {
    $manager_config = WATCHERS;
    $all_statuses = [];
    foreach ($manager_config as $config) {
        $watcher = new \stdClass();
        $watcher->id = $config['id'];
        $heartbeat_file = $config['heartbeat_file'] ?? null;
        if (preg_match('/watcher_heartbeat_(.+)\.json/', $heartbeat_file, $matches)) {
            $watcher_id = $matches[1];
            $hb = $nas_monitor->readHeartbeat($watcher_id);
            $all_statuses[$watcher_id] = $hb;
        }
    }
    $debug['steps']['heartbeat_api_simulation']['status'] = 'success';
    $debug['steps']['heartbeat_api_simulation']['watchers'] = $all_statuses;
} catch (Exception $e) {
    $debug['steps']['heartbeat_api_simulation']['status'] = 'failed';
    $debug['steps']['heartbeat_api_simulation']['error'] = $e->getMessage();
}

http_response_code(200);
echo json_encode($debug, JSON_PRETTY_PRINT);
