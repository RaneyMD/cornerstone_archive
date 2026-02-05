<?php
/**
 * Main entry point and router for Cornerstone Archive Console
 * Handles authentication check and routes to appropriate page
 */

// Start session
session_start();

// Include configuration
require_once __DIR__ . '/config/config.php';

// Handle logout action
if (isset($_GET['action']) && $_GET['action'] === 'logout') {
    require_once __DIR__ . '/auth/logout.php';
    exit;
}

// Check authentication
if (!isset($_SESSION['username'])) {
    // Not logged in - redirect to login
    header('Location: /auth/login.php');
    exit;
}

// Session validation (timeout, user_id check, activity update)
require_once __DIR__ . '/auth/session_check.php';

// Authenticated - now route to appropriate page
$page = $_GET['page'] ?? 'dashboard';
$page = preg_replace('/[^a-z_]/', '', $page);  // Sanitize to prevent path traversal

$page_file = __DIR__ . "/pages/{$page}.php";

// Security: verify file exists and is in pages directory
if (!file_exists($page_file) || !is_file($page_file) || realpath($page_file) === false) {
    $page_file = __DIR__ . '/pages/dashboard.php';
}

// Include the page
require_once $page_file;
