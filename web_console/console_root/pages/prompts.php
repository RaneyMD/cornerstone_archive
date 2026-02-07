<?php
/**
 * Prompts Management Page
 * Upload, browse, preview, and manage Claude Code prompts
 */
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompts - Cornerstone Archive Console</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="icon" type="image/png" href="/favicon-32x32.png">
    <link rel="icon" href="/favicon.ico">
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
                        <a class="nav-link active" href="/?page=prompts">Prompts</a>
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
                <h1>Prompt Management</h1>
                <p class="text-muted">Upload, browse, and manage Claude Code prompts</p>
            </div>
            <div class="col-auto">
                <a href="/?page=dashboard" class="btn btn-secondary">← Back to Dashboard</a>
            </div>
        </div>

        <!-- Upload Prompt Card -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Upload Prompt</h5>
                    </div>
                    <div class="card-body">
                        <form id="prompt-upload-form" enctype="multipart/form-data">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Prompt Name</label>
                                    <input type="text" class="form-control" id="prompt-name"
                                           name="prompt_name" required maxlength="100"
                                           placeholder="e.g., Refactor API handlers">
                                    <small class="form-text text-muted">Max 100 characters. Use alphanumeric, spaces, hyphens, underscores.</small>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Prompt File (.md or .txt)</label>
                                    <input type="file" class="form-control" id="prompt-file"
                                           name="prompt_file" accept=".md,.txt" required>
                                    <small class="form-text text-muted">Maximum file size: 100KB</small>
                                </div>
                                <div class="col-12">
                                    <button type="submit" class="btn btn-primary">Upload Prompt</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>

        <!-- Existing Prompts Card -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">Existing Prompts</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Seq</th>
                                        <th>Name</th>
                                        <th>Filename</th>
                                        <th>Size</th>
                                        <th>Uploaded By</th>
                                        <th>Uploaded At</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="prompts-table-body">
                                    <tr><td colspan="7" class="text-center text-muted">Loading...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Prompt Content Modal -->
    <div class="modal fade" id="promptContentModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="promptModalTitle">Prompt Content</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <pre id="promptContentPre" class="bg-light p-3 rounded" style="max-height: 500px; overflow-y: auto;"></pre>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

    <!-- Load shared utilities and prompts logic -->
    <script src="/assets/js/utils.js"></script>
    <script src="/assets/js/prompts.js"></script>
</body>
</html>
