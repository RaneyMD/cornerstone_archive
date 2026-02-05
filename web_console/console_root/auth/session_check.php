<?php
/**
 * Session validation - include in all protected pages
 * Redirects to login if no valid session exists
 */

// Prevent session fixation
if (!isset($_SESSION['user_id'])) {
    $_SESSION['user_id'] = session_id();
}

// Check session timeout
if (isset($_SESSION['last_activity'])) {
    $inactive = time() - $_SESSION['last_activity'];
    if ($inactive > SESSION_TIMEOUT) {
        session_destroy();
        header('Location: /login.php?expired=1');
        exit;
    }
}

// Update last activity time
$_SESSION['last_activity'] = time();

// Verify username is set
if (!isset($_SESSION['username'])) {
    header('Location: /login.php');
    exit;
}

// All checks passed - user is authenticated
$authenticated_user = $_SESSION['username'];
