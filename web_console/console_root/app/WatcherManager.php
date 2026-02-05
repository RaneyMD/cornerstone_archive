<?php
/**
 * Watcher Manager - Manage multiple watcher instances
 * Aggregates status, health, and operations across all configured watchers
 */
class WatcherManager {
    private $db;
    private $nas_monitor;
    private $watchers_config;
    private $watchers = [];
    private $stale_threshold;
    private $dead_threshold;

    public function __construct($db, $nas_monitor, $watchers_config, $stale_threshold = null, $dead_threshold = 600) {
        $this->db = $db;
        $this->nas_monitor = $nas_monitor;
        $this->watchers_config = $watchers_config;
        $this->stale_threshold = $stale_threshold;
        $this->dead_threshold = $dead_threshold;

        // Initialize Watcher instances
        $this->initializeWatchers();
    }

    /**
     * Initialize all configured Watcher instances
     */
    private function initializeWatchers() {
        foreach ($this->watchers_config as $key => $config) {
            $watcher_id = $config['id'];
            $this->watchers[$watcher_id] = new Watcher($this->db, $this->nas_monitor, $config);
        }
    }

    /**
     * Get all configured watcher IDs
     */
    public function getWatcherIds() {
        return array_keys($this->watchers);
    }

    /**
     * Get a specific watcher instance
     *
     * @param string $watcher_id Watcher identifier
     * @return Watcher|null
     */
    public function getWatcher($watcher_id) {
        return $this->watchers[$watcher_id] ?? null;
    }

    /**
     * Get all watchers
     *
     * @return array Watcher instances keyed by ID
     */
    public function getAllWatchers() {
        return $this->watchers;
    }

    /**
     * Get status of all watchers
     *
     * @return array Status information for each watcher
     */
    public function getAllWatchersStatus() {
        $statuses = [];

        foreach ($this->watchers as $watcher_id => $watcher) {
            $statuses[$watcher_id] = $watcher->getStatus($this->stale_threshold, $this->dead_threshold);
        }

        return $statuses;
    }

    /**
     * Get summary statistics across all watchers
     *
     * @return array Summary counts
     */
    public function getHealthSummary() {
        $statuses = $this->getAllWatchersStatus();

        $summary = [
            'total' => count($statuses),
            'running_count' => 0,
            'stale_count' => 0,
            'offline_count' => 0,
            'unknown_count' => 0,
            'timestamp' => date('c')
        ];

        foreach ($statuses as $status) {
            match ($status['status']) {
                'running' => $summary['running_count']++,
                'stale' => $summary['stale_count']++,
                'offline' => $summary['offline_count']++,
                default => $summary['unknown_count']++
            };
        }

        return $summary;
    }

    /**
     * Get total pending tasks across all watchers
     *
     * @return int Count of pending tasks
     */
    public function getPendingTaskCount() {
        try {
            $result = $this->db->fetchOne(
                "SELECT COUNT(*) as count FROM tasks_t WHERE status = 'pending'"
            );
            return (int)($result['count'] ?? 0);
        } catch (Exception $e) {
            error_log("Failed to get pending task count: " . $e->getMessage());
            return 0;
        }
    }

    /**
     * Get recent task results across all watchers
     *
     * @param int $limit Number of results to return
     * @return array Recent task results
     */
    public function getRecentResults($limit = 10) {
        try {
            $sql = "SELECT
                        task_id,
                        watcher_id,
                        handler,
                        status,
                        completed_at,
                        duration_seconds
                    FROM tasks_t
                    WHERE status IN ('success', 'failed')
                    ORDER BY completed_at DESC
                    LIMIT ?";

            return $this->db->fetchAll($sql, [$limit]);
        } catch (Exception $e) {
            error_log("Failed to get recent results: " . $e->getMessage());
            return [];
        }
    }

    /**
     * Get database connection status
     *
     * @return array Connection status info
     */
    public function getDatabaseStatus() {
        $status = [
            'connected' => $this->db->isConnected(),
            'tables' => 0,
            'last_audit' => null
        ];

        try {
            // Count tables in database
            $result = $this->db->fetchOne(
                "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = DATABASE()"
            );
            $status['tables'] = (int)($result['count'] ?? 0);

            // Get last audit log entry
            $audit = $this->db->fetchOne(
                "SELECT timestamp FROM audit_log_t ORDER BY timestamp DESC LIMIT 1"
            );
            if ($audit) {
                $status['last_audit'] = $audit['timestamp'];
            }
        } catch (Exception $e) {
            error_log("Failed to get database status: " . $e->getMessage());
        }

        return $status;
    }

    /**
     * Get NAS health status
     *
     * @return array NAS connectivity and paths
     */
    public function getNasStatus() {
        $status = [
            'accessible' => false,
            'state_path' => NAS_STATE,
            'paths' => []
        ];

        // Check if NAS state path is accessible
        if (is_dir(NAS_STATE)) {
            $status['accessible'] = true;
            $status['paths'][] = [
                'name' => 'State',
                'path' => NAS_STATE,
                'writable' => is_writable(NAS_STATE)
            ];
        }

        if (is_dir(NAS_LOGS)) {
            $status['paths'][] = [
                'name' => 'Logs',
                'path' => NAS_LOGS,
                'writable' => is_writable(NAS_LOGS)
            ];
        }

        if (is_dir(NAS_WORKER_INBOX)) {
            $status['paths'][] = [
                'name' => 'Worker Inbox',
                'path' => NAS_WORKER_INBOX,
                'writable' => is_writable(NAS_WORKER_INBOX)
            ];
        }

        if (is_dir(NAS_WORKER_OUTBOX)) {
            $status['paths'][] = [
                'name' => 'Worker Outbox',
                'path' => NAS_WORKER_OUTBOX,
                'readable' => is_readable(NAS_WORKER_OUTBOX)
            ];
        }

        return $status;
    }

    /**
     * Get comprehensive system health dashboard data
     *
     * @return array Complete health snapshot
     */
    public function getSystemHealth() {
        return [
            'timestamp' => date('c'),
            'watchers_status' => $this->getAllWatchersStatus(),
            'summary' => $this->getHealthSummary(),
            'pending_tasks' => $this->getPendingTaskCount(),
            'recent_results' => $this->getRecentResults(5),
            'database' => $this->getDatabaseStatus(),
            'nas' => $this->getNasStatus()
        ];
    }

    /**
     * Broadcast control action to a watcher
     * (Creates task or signal file for watcher to pick up)
     *
     * @param string $watcher_id Target watcher
     * @param string $action Action to perform ('restart', 'refresh', etc.)
     * @return array Result of action
     */
    public function broadcastControlAction($watcher_id, $action) {
        $watcher = $this->getWatcher($watcher_id);
        if (!$watcher) {
            return [
                'success' => false,
                'message' => "Watcher not found: $watcher_id"
            ];
        }

        try {
            // Log the action
            $this->db->insert('audit_log_t', [
                'action' => "CONTROL_$action",
                'username' => $_SESSION['username'] ?? 'system',
                'ip_address' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
                'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown',
                'details' => "Watcher: $watcher_id",
                'timestamp' => date('Y-m-d H:i:s')
            ]);

            return [
                'success' => true,
                'message' => ucfirst($action) . " signal sent to $watcher_id",
                'action' => $action,
                'watcher_id' => $watcher_id,
                'timestamp' => date('c')
            ];
        } catch (Exception $e) {
            error_log("Failed to broadcast control action: " . $e->getMessage());
            return [
                'success' => false,
                'message' => 'Failed to send control action'
            ];
        }
    }
}
