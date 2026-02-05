<?php
/**
 * NAS Monitor - Reads and parses watcher heartbeat files
 * Handles multi-watcher heartbeat data from JSON files on the NAS
 */
class NasMonitor {
    private $nas_state_path;

    public function __construct($nas_state_path) {
        $this->nas_state_path = $nas_state_path;
    }

    /**
     * Read a single watcher's heartbeat file
     *
     * @param string $watcher_id Watcher identifier (e.g., 'orionmx')
     * @return array Parsed heartbeat data or null if file not found
     */
    public function readHeartbeat($watcher_id) {
        $filename = "watcher_heartbeat_{$watcher_id}.json";
        $filepath = $this->nas_state_path . '\\' . $filename;

        if (!file_exists($filepath)) {
            return null;
        }

        try {
            $content = file_get_contents($filepath);
            if ($content === false) {
                error_log("Failed to read heartbeat file: $filepath");
                return null;
            }

            $data = json_decode($content, true);
            if ($data === null) {
                error_log("Invalid JSON in heartbeat file: $filepath");
                return null;
            }

            return $data;
        } catch (Exception $e) {
            error_log("Error reading heartbeat file: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Read all watcher heartbeat files
     *
     * @return array Keyed by watcher_id, with heartbeat data or null
     */
    public function readAllHeartbeats() {
        $heartbeats = [];

        if (!is_dir($this->nas_state_path)) {
            error_log("NAS state path not accessible: {$this->nas_state_path}");
            return $heartbeats;
        }

        try {
            $files = glob($this->nas_state_path . '\\watcher_heartbeat_*.json');
            if ($files === false) {
                error_log("Failed to glob heartbeat files in: {$this->nas_state_path}");
                return $heartbeats;
            }

            foreach ($files as $filepath) {
                // Extract watcher_id from filename
                $filename = basename($filepath);
                if (preg_match('/^watcher_heartbeat_(.+)\.json$/', $filename, $matches)) {
                    $watcher_id = $matches[1];
                    $heartbeats[$watcher_id] = $this->readHeartbeat($watcher_id);
                }
            }
        } catch (Exception $e) {
            error_log("Error reading heartbeat directory: " . $e->getMessage());
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
     * @param string $timestamp ISO 8601 timestamp
     * @return int|null Unix timestamp or null if parsing fails
     */
    private function parseTimestamp($timestamp) {
        try {
            // Handle ISO 8601 format (e.g., "2026-02-05T00:15:30Z")
            $dt = new DateTime($timestamp, new DateTimeZone('UTC'));
            return $dt->getTimestamp();
        } catch (Exception $e) {
            error_log("Failed to parse timestamp: $timestamp - " . $e->getMessage());
            return null;
        }
    }
}
