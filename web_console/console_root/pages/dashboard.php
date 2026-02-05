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
        <!-- Page Header -->
        <div class="row mb-4">
            <div class="col">
                <h1>Dashboard</h1>
                <p class="text-muted">Multi-watcher real-time monitoring and control</p>
            </div>
            <div class="col-auto">
                <button class="btn btn-primary btn-refresh">↻ Refresh</button>
                <small class="text-muted ms-2">Last: <span id="last-refresh-time">--:--:--</span></small>
            </div>
        </div>

        <!-- Supervisor Status Cards Section -->
        <div class="mb-4">
            <h4 class="mb-3">Supervisor Status</h4>
            <div id="supervisors-container">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Watcher Status Cards Section -->
        <div class="mb-4">
            <h4 class="mb-3">Watcher Status</h4>
            <div id="watchers-container">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Health Summary -->
        <div id="health-summary" class="mb-4">
            <!-- Populated by JavaScript -->
        </div>

        <!-- System Overview Section -->
        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Pending Tasks</h5>
                    </div>
                    <div class="card-body">
                        <div class="stat-large">
                            <span class="stat-value" id="pending-task-count">--</span>
                            <span class="stat-label">Tasks waiting</span>
                        </div>
                        <hr>
                        <a href="/?page=tasks" class="btn btn-sm btn-outline-primary">View All Tasks →</a>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">System Status</h5>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-success mb-2">
                            <strong>✓ Database Connected</strong><br>
                            <small>Ready for operations</small>
                        </div>
                        <div class="alert alert-success mb-0">
                            <strong>✓ NAS Accessible</strong><br>
                            <small>Heartbeat files monitored</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

    <!-- Pass PHP config to JavaScript -->
    <script>
        const AUTO_REFRESH_INTERVAL = <?php echo AUTO_REFRESH_INTERVAL; ?>;
    </script>

    <!-- Load shared utilities and dashboard logic -->
    <script src="/assets/js/utils.js"></script>
    <script src="/assets/js/dashboard.js"></script>
</body>
</html>
