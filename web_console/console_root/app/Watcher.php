<?php
/**
 * Watcher - Query and monitor individual watcher instance
 * Combines database queries with NAS heartbeat data
 */
class Watcher {
    private $db;
    private $nas_monitor;
    private $config;

    public function __construct($db, $nas_monitor, $watcher_config) {
        $this->db = $db;
        $this->nas_monitor = $nas_monitor;
        $this->config = $watcher_config;
    }

    /**
     * Get watcher ID
     */
    public function getId() {
        return $this->config['id'];
    }

    /**
     * Get watcher hostname
     */
    public function getHostname() {
        return $this->config['hostname'] ?? null;
    }

    /**
     * Get watcher status role (primary, secondary, etc.)
     */
    public function getStatusRole() {
        return $this->config['status'] ?? 'unknown';
    }

    /**
     * Get current heartbeat data from NAS
     */
    public function getHeartbeat() {
        $heartbeat_file = $this->config['heartbeat_file'] ?? null;
        if (!$heartbeat_file) {
            return null;
        }

        // Extract watcher_id from filename (e.g., "watcher_heartbeat_orionmx.json" → "orionmx")
        if (preg_match('/watcher_heartbeat_(.+)\.json/', $heartbeat_file, $matches)) {
            $watcher_id = $matches[1];
            return $this->nas_monitor->readHeartbeat($watcher_id);
        }

        return null;
    }

    /**
     * Get detailed watcher status including freshness and system info
     *
     * @param int $stale_threshold Optional override for stale threshold
     * @param int $dead_threshold Optional override for dead threshold
     * @return array Status information
     */
    public function getStatus($stale_threshold = null, $dead_threshold = 600) {
        $heartbeat = $this->getHeartbeat();
        $watcher_id = $this->getId();

        // Default poll interval from heartbeat or config
        $poll_seconds = 30;  // Default production value
        if ($heartbeat && isset($heartbeat['poll_seconds'])) {
            $poll_seconds = (int)$heartbeat['poll_seconds'];
        }

        // Check freshness
        $freshness = $this->nas_monitor->checkFreshness($heartbeat, $poll_seconds, $stale_threshold, $dead_threshold);

        // Build response
        $status = [
            'watcher_id' => $watcher_id,
            'hostname' => $this->getHostname(),
            'status_role' => $this->getStatusRole(),
            'status' => $freshness['status'],
            'status_badge' => $this->nas_monitor->getStatusBadgeColor($freshness['status']),
            'fresh' => $freshness['fresh'],
            'stale' => $freshness['stale'],
            'dead' => $freshness['dead'],
            'age_seconds' => $freshness['age_seconds'],
            'poll_seconds' => $poll_seconds,
            'last_heartbeat' => $heartbeat['timestamp'] ?? null,
            'last_heartbeat_formatted' => $heartbeat['timestamp'] ?
                $this->nas_monitor->formatTimestamp($heartbeat['timestamp']) : 'Never'
        ];

        // Add heartbeat data if available
        if ($heartbeat) {
            $status['pid'] = $heartbeat['pid'] ?? null;
            $status['executable'] = $heartbeat['executable'] ?? null;
            $status['utc_locked_at'] = $heartbeat['utc_locked_at'] ?? null;
            $status['lock_exists'] = $heartbeat['lock_exists'] ?? false;
            $status['lock_path'] = $heartbeat['lock_path'] ?? null;
        } else {
            $status['pid'] = null;
            $status['executable'] = null;
            $status['utc_locked_at'] = null;
            $status['lock_exists'] = false;
            $status['lock_path'] = null;
        }

        return $status;
    }

    /**
     * Get recent logs from database for this watcher
     *
     * @param int $limit Number of log lines to return
     * @return array Log entries
     */
    public function getRecentLogs($limit = 50) {
        try {
            $sql = "SELECT
                        timestamp,
                        level,
                        message
                    FROM watcher_logs_t
                    WHERE watcher_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?";

            $logs = $this->db->fetchAll($sql, [$this->getId(), $limit]);
            return array_reverse($logs);  // Chronological order
        } catch (Exception $e) {
            error_log("Failed to get watcher logs: " . $e->getMessage());
            return [];
        }
    }

    /**
     * Get pending tasks for this watcher
     *
     * @return array Pending task list
     */
    public function getPendingTasks() {
        try {
            $sql = "SELECT
                        task_id,
                        handler,
                        created_at,
                        priority
                    FROM tasks_t
                    WHERE watcher_id = ? AND status = 'pending'
                    ORDER BY priority DESC, created_at ASC";

            return $this->db->fetchAll($sql, [$this->getId()]);
        } catch (Exception $e) {
            error_log("Failed to get pending tasks: " . $e->getMessage());
            return [];
        }
    }

    /**
     * Get recent task results for this watcher
     *
     * @param int $limit Number of results to return
     * @return array Recent task results
     */
    public function getRecentResults($limit = 10) {
        try {
            $sql = "SELECT
                        task_id,
                        handler,
                        status,
                        completed_at,
                        duration_seconds
                    FROM tasks_t
                    WHERE watcher_id = ? AND status IN ('success', 'failed')
                    ORDER BY completed_at DESC
                    LIMIT ?";

            return $this->db->fetchAll($sql, [$this->getId(), $limit]);
        } catch (Exception $e) {
            error_log("Failed to get recent results: " . $e->getMessage());
            return [];
        }
    }
}
