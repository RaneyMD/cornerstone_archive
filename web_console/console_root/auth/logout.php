<?php
/**
 * Logout handler
 * Destroys session and redirects to login
 */

session_start();

// Include config for audit logging
require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../app/Database.php';

$username = $_SESSION['username'] ?? 'unknown';

// Log logout action to database
try {
    $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $db->connect();
    $db->execute(
        "INSERT INTO audit_log_t (actor, action, target_type, target_id, details_json) VALUES (?, ?, ?, ?, ?)",
        [
            $username,
            'LOGOUT',
            'user_session',
            session_id(),
            json_encode([
                'ip_address' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
                'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown',
            ])
        ]
    );
} catch (Exception $e) {
    error_log("Audit log failed: " . $e->getMessage());
    // Continue anyway - don't block logout
}

// Destroy session
session_destroy();

// Redirect to login
header('Location: /auth/login.php');
exit;
