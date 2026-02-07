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
                        <a class="nav-link" href="/?page=prompts">Prompts</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/?page=diagnostics">Diagnostics</a>
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
                <h1>Dashboard</h1>
                <p class="text-muted">Multi-watcher real-time monitoring and control</p>
            </div>
            <div class="col-auto">
                <button class="btn btn-primary btn-refresh">↻ Refresh</button>
                <small class="text-muted ms-2">Last: <span id="last-refresh-time">--:--:--</span></small>
            </div>
        </div>

        <!-- Supervisor and Watcher Status - Side by Side -->
        <div class="row mb-4">
            <!-- Supervisor Status - Left Column -->
            <div class="col-lg-6 mb-3 mb-lg-0">
                <h4 class="mb-3">Supervisor Status</h4>
                <div id="supervisors-container">
                    <div class="text-center">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Watcher Status - Right Column -->
            <div class="col-lg-6">
                <h4 class="mb-3">Watcher Status</h4>
                <div id="watchers-container">
                    <div class="text-center">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Health Summary -->
        <div id="health-summary" class="mb-4">
            <!-- Populated by JavaScript -->
        </div>

        <!-- Console Control Panel -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Control Panel</h5>
                    </div>
                    <div class="card-body">
                        <form id="control-flag-form" class="row g-3">
                            <div class="col-md-3">
                                <label class="form-label">Worker</label>
                                <select class="form-select" id="control-worker">
                                    <option value="OrionMX">OrionMX</option>
                                    <option value="OrionMega">OrionMega</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Label (optional)</label>
                                <input type="text" class="form-control" id="control-label" maxlength="100">
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Rollback commits</label>
                                <input type="number" class="form-control" id="control-commits" value="1" min="1">
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Claude Prompt (optional)</label>
                                <select class="form-select" id="control-prompt">
                                    <option value="">None</option>
                                </select>
                            </div>
                            <div class="col-md-3" id="prompt-model-container" style="display: none;">
                                <label class="form-label">Model</label>
                                <select class="form-select" id="control-prompt-model">
                                    <option value="sonnet">Sonnet (Recommended)</option>
                                    <option value="opus">Opus</option>
                                    <option value="haiku">Haiku</option>
                                </select>
                            </div>
                            <div class="col-md-3 d-flex align-items-end gap-2 flex-wrap">
                                <button type="button" class="btn btn-outline-secondary" data-action="pause_watcher">Pause</button>
                                <button type="button" class="btn btn-outline-secondary" data-action="resume_watcher">Resume</button>
                                <button type="button" class="btn btn-outline-secondary" data-action="restart_watcher">Restart</button>
                                <button type="button" class="btn btn-outline-primary" data-action="update_code">Update Code</button>
                                <button type="button" class="btn btn-outline-primary" data-action="update_code_deps">Update Deps</button>
                                <button type="button" class="btn btn-outline-warning" data-action="rollback_code">Rollback</button>
                                <button type="button" class="btn btn-outline-info" data-action="diagnostics">Diagnostics</button>
                                <button type="button" class="btn btn-outline-info" data-action="verify_db">Verify DB</button>
                            </div>
                        </form>
                        <small class="text-muted">Control actions create supervisor flags and log to jobs_t/audit_log_t.</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Task Queue -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Task Queue (Queued)</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>Job ID</th>
                                        <th>Type</th>
                                        <th>Label</th>
                                        <th>Created</th>
                                        <th>Attempts</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="queued-jobs-body">
                                    <tr><td colspan="6" class="text-muted text-center">No queued jobs loaded.</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-primary" type="button">Execute Now</button>
                            <button class="btn btn-sm btn-outline-secondary" type="button">Cancel</button>
                            <button class="btn btn-sm btn-outline-danger" type="button">Delete</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Running Jobs</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>Job ID</th>
                                        <th>Type</th>
                                        <th>Label</th>
                                        <th>Worker</th>
                                        <th>Started</th>
                                        <th>Elapsed</th>
                                    </tr>
                                </thead>
                                <tbody id="running-jobs-body">
                                    <tr><td colspan="6" class="text-muted text-center">No running jobs loaded.</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <small class="text-muted">Active tasks reported by watcher status.</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Results -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Recent Results</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>Job ID</th>
                                        <th>Type</th>
                                        <th>Label</th>
                                        <th>State</th>
                                        <th>Finished</th>
                                        <th>Duration</th>
                                    </tr>
                                </thead>
                                <tbody id="recent-results-body">
                                    <tr><td colspan="6" class="text-muted text-center">No results loaded.</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <small class="text-muted">Click a job to open full result details and audit trail.</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Job Details Modal -->
        <div class="modal fade" id="jobDetailsModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Job Details</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row g-3">
                            <div class="col-md-6">
                                <h6>Job Info</h6>
                                <div id="job-details-basic" class="small text-muted">Select a job to view details.</div>
                            </div>
                            <div class="col-md-6">
                                <h6>Audit Trail</h6>
                                <div id="job-details-audit" class="small text-muted">Audit entries will appear here.</div>
                            </div>
                            <div class="col-12">
                                <h6>Result Data</h6>
                                <pre id="job-details-result" class="bg-light p-3 rounded small">No result loaded.</pre>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
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
