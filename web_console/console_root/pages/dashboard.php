<?php
/**
 * Dashboard page - main view for multi-watcher monitoring
 * Displays status of all watchers, pending tasks, system health
 */
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Cornerstone Archive Console</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/style.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <strong>Cornerstone Archive Console</strong>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <span class="nav-link">User: <strong><?php echo htmlspecialchars($_SESSION['username'], ENT_QUOTES, 'UTF-8'); ?></strong></span>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/?action=logout">Logout</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid mt-4">
        <div class="row mb-4">
            <div class="col">
                <h1>Dashboard</h1>
                <p class="text-muted">Multi-watcher status and system monitoring</p>
            </div>
            <div class="col-auto">
                <button class="btn btn-primary btn-refresh">↻ Refresh Now</button>
            </div>
        </div>

        <!-- Placeholder Content -->
        <div class="alert alert-info">
            <strong>Authentication Successful!</strong><br>
            Dashboard foundation is in place. Watcher status display, API endpoints, and real-time monitoring to follow.
        </div>

        <!-- Watchers Status Section -->
        <div class="card mb-4">
            <div class="card-header bg-light">
                <h5 class="mb-0">Watcher Status (Real-time monitoring coming soon)</h5>
            </div>
            <div class="card-body">
                <p class="text-muted">Watcher cards will display here once NAS monitoring is configured.</p>
            </div>
        </div>

        <!-- System Overview -->
        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Pending Tasks</h5>
                    </div>
                    <div class="card-body">
                        <p class="text-muted">Task list will appear here.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">System Health</h5>
                    </div>
                    <div class="card-body">
                        <p class="text-muted">Database and NAS status to follow.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="/assets/js/utils.js"></script>
</body>
</html>
