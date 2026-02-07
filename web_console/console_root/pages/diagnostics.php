<?php
/**
 * Diagnostics Viewer Page
 * View recent diagnostic reports from supervisor
 */
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diagnostics - Cornerstone Archive Console</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/style.css">
    <style>
        .status-badge {
            font-weight: 600;
            padding: 0.35rem 0.65rem;
        }
        .status-healthy { background-color: #28a745; color: white; }
        .status-unhealthy { background-color: #dc3545; color: white; }
        .status-unknown { background-color: #6c757d; color: white; }

        .report-section {
            border-left: 4px solid #0d6efd;
            padding: 1rem;
            margin-bottom: 1rem;
            background-color: #f8f9fa;
            border-radius: 0.25rem;
        }

        .report-section h6 {
            margin-top: 0;
            color: #0d6efd;
            font-weight: 600;
        }

        pre {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 0.25rem;
            max-height: 400px;
            overflow-y: auto;
        }
    </style>
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
                        <a class="nav-link" href="/?page=dashboard">Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="/?page=diagnostics">Diagnostics</a>
                    </li>
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
                <h1>Diagnostics Reports</h1>
                <p class="text-muted">View system health reports from supervisor diagnostics runs</p>
            </div>
            <div class="col-auto">
                <a href="/?page=dashboard" class="btn btn-secondary">← Back to Dashboard</a>
            </div>
        </div>

        <!-- Diagnostics List Card -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Recent Diagnostics Reports</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Worker</th>
                                        <th>Label</th>
                                        <th>Reported At</th>
                                        <th style="width: 200px;">Status</th>
                                        <th>Disk Free</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="diagnostics-table-body">
                                    <tr><td colspan="7" class="text-center text-muted">Loading...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Diagnostic Details Modal -->
    <div class="modal fade" id="diagnosticModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Diagnostic Report</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="diagnostic-content">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

    <!-- Load shared utilities and diagnostics logic -->
    <script src="/assets/js/utils.js"></script>
    <script src="/assets/js/diagnostics.js"></script>
</body>
</html>
