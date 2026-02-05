<?php
/**
 * Heartbeat Monitor - Reads watcher heartbeat data from database
 * Handles multi-watcher heartbeat data from workers_t table
 *
 * NOTE: Originally read from NAS JSON files, but now reads from database
 * for better reliability and to avoid UNC path access issues on shared hosting.
 */
class NasMonitor {
    private $db;
    private $nas_state_path;  // Kept for compatibility, not used

    public function __construct($db, $nas_state_path = null) {
        $this->db = $db;
        $this->nas_state_path = $nas_state_path;
    }

    /**
     * Read a single watcher's heartbeat from database
     *
     * @param string $watcher_id Watcher identifier (e.g., 'OrionMX')
     * @return array Parsed heartbeat data or null if not found
     */
    public function readHeartbeat($watcher_id) {
        try {
            $sql = "SELECT
                        worker_id as watcher_id,
                        last_heartbeat_at as timestamp,
                        pid,
                        hostname,
                        status,
                        poll_seconds,
                        status_summary
                    FROM workers_t
                    WHERE worker_id = ?";

            $row = $this->db->fetchOne($sql, [$watcher_id]);
            if (!$row) {
                return null;
            }

            // Convert MySQL datetime to ISO 8601
            if ($row['timestamp']) {
                $row['timestamp'] = $this->toIso8601($row['timestamp']);
            }

            return $row;
        } catch (Exception $e) {
            error_log("Error reading heartbeat from database: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Read all watcher heartbeats from database
     *
     * @return array Keyed by watcher_id, with heartbeat data or null
     */
    public function readAllHeartbeats() {
        $heartbeats = [];

        try {
            $sql = "SELECT
                        worker_id as watcher_id,
                        last_heartbeat_at as timestamp,
                        pid,
                        hostname,
                        status,
                        poll_seconds,
                        status_summary
                    FROM workers_t
                    ORDER BY worker_id";

            $rows = $this->db->fetchAll($sql);

            foreach ($rows as $row) {
                // Convert MySQL datetime to ISO 8601
                if ($row['timestamp']) {
                    $row['timestamp'] = $this->toIso8601($row['timestamp']);
                }
                $heartbeats[$row['watcher_id']] = $row;
            }
        } catch (Exception $e) {
            error_log("Error reading heartbeats from database: " . $e->getMessage());
        }

        return $heartbeats;
    }

    /**
     * Determine if a heartbeat is fresh, stale, or dead
     *
     * @param array $heartbeat Parsed heartbeat data
     * @param int $poll_seconds Expected poll interval in seconds
     * @param int $stale_threshold Threshold for stale (default 2x poll interval)
     * @param int $dead_threshold Threshold for dead (default 600s)
     * @return array ['status' => 'running|stale|offline', 'age_seconds' => int]
     */
    public function checkFreshness($heartbeat, $poll_seconds, $stale_threshold = null, $dead_threshold = 600) {
        if (!$heartbeat || !isset($heartbeat['timestamp'])) {
            return [
                'status' => 'offline',
                'age_seconds' => null,
                'fresh' => false,
                'stale' => true,
                'dead' => true
            ];
        }

        if ($stale_threshold === null) {
            $stale_threshold = $poll_seconds * 2;
        }

        // Parse timestamp - handle both ISO 8601 and other formats
        $timestamp = $this->parseTimestamp($heartbeat['timestamp']);
        if ($timestamp === null) {
            return [
                'status' => 'offline',
                'age_seconds' => null,
                'fresh' => false,
                'stale' => true,
                'dead' => true
            ];
        }

        $now = time();
        $age = $now - $timestamp;

        if ($age > $dead_threshold) {
            $status = 'offline';
            $fresh = false;
            $stale = true;
            $dead = true;
        } elseif ($age > $stale_threshold) {
            $status = 'stale';
            $fresh = false;
            $stale = true;
            $dead = false;
        } else {
            $status = 'running';
            $fresh = true;
            $stale = false;
            $dead = false;
        }

        return [
            'status' => $status,
            'age_seconds' => max(0, $age),
            'fresh' => $fresh,
            'stale' => $stale,
            'dead' => $dead
        ];
    }

    /**
     * Get status badge color for display
     *
     * @param string $status Status string ('running', 'stale', 'offline')
     * @return string Bootstrap badge color ('success', 'warning', 'danger', 'secondary')
     */
    public function getStatusBadgeColor($status) {
        $colors = [
            'running' => 'success',
            'stale' => 'warning',
            'offline' => 'danger'
        ];
        return $colors[$status] ?? 'secondary';
    }

    /**
     * Format a timestamp for display
     *
     * @param string $timestamp ISO 8601 timestamp
     * @return string Formatted timestamp or original if parsing fails
     */
    public function formatTimestamp($timestamp) {
        try {
            $dt = new DateTime($timestamp, new DateTimeZone('UTC'));
            return $dt->format('Y-m-d H:i:s') . ' UTC';
        } catch (Exception $e) {
            return $timestamp;
        }
    }

    /**
     * Parse ISO 8601 timestamp to Unix timestamp
     *
     * @param string $timestamp ISO 8601 or MySQL datetime string
     * @return int|null Unix timestamp or null if parsing fails
     */
    private function parseTimestamp($timestamp) {
        try {
            // Handle both ISO 8601 and MySQL datetime formats
            $dt = new DateTime($timestamp, new DateTimeZone('UTC'));
            return $dt->getTimestamp();
        } catch (Exception $e) {
            error_log("Failed to parse timestamp: $timestamp - " . $e->getMessage());
            return null;
        }
    }

    /**
     * Convert MySQL datetime to ISO 8601 format
     *
     * @param string $mysqlDatetime MySQL datetime string (e.g., "2026-02-05 16:53:00")
     * @return string ISO 8601 format (e.g., "2026-02-05T16:53:00Z")
     */
    private function toIso8601($mysqlDatetime) {
        try {
            $dt = new DateTime($mysqlDatetime, new DateTimeZone('UTC'));
            return $dt->format('c');  // ISO 8601 format
        } catch (Exception $e) {
            error_log("Failed to convert datetime: $mysqlDatetime - " . $e->getMessage());
            return $mysqlDatetime;
        }
    }
}
