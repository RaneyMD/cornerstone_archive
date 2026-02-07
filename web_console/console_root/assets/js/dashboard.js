/**
 * Cornerstone Archive Console - Dashboard
 * Real-time multi-watcher monitoring with AJAX polling
 */

$(document).ready(function() {
    // Load available prompts
    loadPromptsDropdown();

    // Auto-refresh on page load
    refreshDashboard();

    // Set up auto-refresh interval (5 seconds)
    const refreshInterval = setInterval(refreshDashboard, AUTO_REFRESH_INTERVAL);

    // Manual refresh button
    $(document).on('click', '.btn-refresh', function() {
        refreshDashboard();
    });

    // Control flag buttons
    $(document).on('click', '#control-flag-form button[data-action]', function(e) {
        e.preventDefault();
        const $btn = $(this);
        const action = $btn.data('action');
        const worker_id = $('#control-worker').val();
        const label = $('#control-label').val() || null;
        const commits = $('#control-commits').val() || 1;
        const promptId = $('#control-prompt').val() || null;

        createSupervisorFlag(action, worker_id, label, commits, promptId, $btn);
    });

    // Show/hide model selector when prompt selected
    $(document).on('change', '#control-prompt', function() {
        const promptId = $(this).val();
        if (promptId) {
            $('#prompt-model-container').show();
        } else {
            $('#prompt-model-container').hide();
        }
    });

    // Watcher control buttons
    $(document).on('click', '.btn-restart-watcher', function() {
        const $btn = $(this);
        const watcherId = $btn.data('watcher-id');
        restartWatcher(watcherId, $btn);
    });

    $(document).on('click', '.btn-watcher-detail', function() {
        const watcherId = $(this).data('watcher-id');
        showWatcherDetail(watcherId);
    });

    $(document).on('click', '.btn-watcher-logs', function() {
        const watcherId = $(this).data('watcher-id');
        showWatcherLogs(watcherId);
    });

    // Allow manual stop of auto-refresh
    $(window).on('beforeunload', function() {
        clearInterval(refreshInterval);
    });
});

/**
 * Refresh entire dashboard
 */
function refreshDashboard() {
    refreshSupervisorStatus();
    refreshWatcherStatus();
    refreshTaskCounts();
    processResults();  // Process any pending result files from console_inbox
}

/**
 * Fetch and update supervisor heartbeats
 */
function refreshSupervisorStatus() {
    $.ajax({
        url: '/api/supervisor_heartbeat.php',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            updateSupervisorCards(data.supervisors);
            updateLastRefresh();
        },
        error: function(xhr, status, error) {
            console.error('Supervisor heartbeat API error:', status, error);
            // Don't show error alert - graceful degradation if supervisor endpoint not available
        }
    });
}

/**
 * Update supervisor status cards on the page
 */
function updateSupervisorCards(supervisors) {
    const container = $('#supervisors-container');

    // Clear existing cards
    container.empty();

    if (supervisors.length === 0) {
        container.html(
            '<div class="alert alert-info">No supervisors configured.</div>'
        );
        return;
    }

    supervisors.forEach(function(supervisor) {
        const card = buildSupervisorCard(supervisor);
        container.append(card);
    });
}

/**
 * Build HTML for a single supervisor status card
 */
function buildSupervisorCard(supervisor) {
    const statusBadgeClass = getSupervisorStatusBadgeClass(supervisor.status);
    const statusIcon = getSupervisorStatusIcon(supervisor.status);
    const ageDisplay = supervisor.age_seconds !== null ?
        formatDuration(supervisor.age_seconds) + ' ago' : 'Never';

    // Parse status summary for display
    let statusText = supervisor.status_summary;
    if (statusText.length > 100) {
        statusText = statusText.substring(0, 100) + '...';
    }

    const html = `
        <div class="card supervisor-card ${supervisor.status} mb-3">
            <div class="card-body">
                <div class="supervisor-header">
                    <h5 class="supervisor-title">
                        ${escapeHtml(supervisor.watcher_id)} Supervisor
                        <span class="badge ${statusBadgeClass}">${statusIcon} ${supervisor.status.toUpperCase()}</span>
                    </h5>
                </div>

                <div class="supervisor-info">
                    <div class="supervisor-info-item">
                        <div class="supervisor-info-label">Status</div>
                        <div class="supervisor-info-value">
                            ${statusText}
                        </div>
                    </div>
                    <div class="supervisor-info-item">
                        <div class="supervisor-info-label">Last Run</div>
                        <div class="supervisor-info-value">
                            ${ageDisplay}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    return html;
}

/**
 * Get badge CSS class for supervisor status
 */
function getSupervisorStatusBadgeClass(status) {
    switch (status) {
        case 'ok':
            return 'bg-success';
        case 'error':
            return 'bg-danger';
        case 'stale':
            return 'bg-warning';
        case 'offline':
            return 'bg-secondary';
        default:
            return 'bg-muted';
    }
}

/**
 * Get icon for supervisor status
 */
function getSupervisorStatusIcon(status) {
    switch (status) {
        case 'ok':
            return '✓';
        case 'error':
            return '✗';
        case 'stale':
            return '⚠';
        case 'offline':
            return '○';
        default:
            return '?';
    }
}

/**
 * Fetch and update all watcher statuses
 */
function refreshWatcherStatus() {
    $.ajax({
        url: '/api/heartbeat.php',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            updateWatcherCards(data.watchers);
            updateHealthSummary(data.summary);
            updateLastRefresh();
        },
        error: function(xhr, status, error) {
            console.error('Heartbeat API error:', status, error);
            showError('Failed to fetch watcher status');
        }
    });
}

/**
 * Update watcher status cards on the page
 */
function updateWatcherCards(watchers) {
    const container = $('#watchers-container');

    // Clear existing cards
    container.empty();

    if (watchers.length === 0) {
        container.html(
            '<div class="alert alert-info">No watchers configured.</div>'
        );
        return;
    }

    watchers.forEach(function(watcher) {
        const card = buildWatcherCard(watcher);
        container.append(card);
    });
}

/**
 * Build HTML for a single watcher status card
 */
function buildWatcherCard(watcher) {
    const statusBadgeClass = getStatusBadgeClass(watcher.status);
    const statusIcon = getStatusIcon(watcher.status);
    const ageDisplay = watcher.age_seconds !== null ?
        formatDuration(watcher.age_seconds) + ' ago' : 'Unknown';

    const html = `
        <div class="card watcher-card ${watcher.status} mb-3">
            <div class="card-body">
                <div class="watcher-header">
                    <h5 class="watcher-title">
                        ${escapeHtml(watcher.watcher_id)}
                        <span class="badge ${statusBadgeClass}">${statusIcon} ${watcher.status.toUpperCase()}</span>
                    </h5>
                    <div class="watcher-status">
                        <small class="text-muted">${escapeHtml(watcher.hostname || 'Unknown')}</small>
                        <small class="badge bg-secondary">${escapeHtml(watcher.status_role)}</small>
                    </div>
                </div>

                <div class="watcher-info">
                    <div class="watcher-info-item">
                        <div class="watcher-info-label">Status</div>
                        <div class="watcher-info-value">
                            ${watcher.status === 'running' ? '✓ Running' : '✗ ' + watcher.status.charAt(0).toUpperCase() + watcher.status.slice(1)}
                        </div>
                    </div>
                    <div class="watcher-info-item">
                        <div class="watcher-info-label">Last Heartbeat</div>
                        <div class="watcher-info-value">
                            ${ageDisplay}
                        </div>
                    </div>
                    <div class="watcher-info-item">
                        <div class="watcher-info-label">PID</div>
                        <div class="watcher-info-value">
                            ${watcher.pid ? watcher.pid : 'N/A'}
                        </div>
                    </div>
                    <div class="watcher-info-item">
                        <div class="watcher-info-label">Poll Interval</div>
                        <div class="watcher-info-value">
                            ${watcher.poll_seconds ? watcher.poll_seconds + 's' : 'Unknown'}
                        </div>
                    </div>
                </div>

                <div class="watcher-controls">
                    <button class="btn btn-sm btn-primary btn-restart-watcher"
                            data-watcher-id="${escapeHtml(watcher.watcher_id)}"
                            ${watcher.status === 'offline' ? '' : ''}>
                        ↻ Restart
                    </button>
                    <button class="btn btn-sm btn-outline-secondary btn-watcher-logs"
                            data-watcher-id="${escapeHtml(watcher.watcher_id)}">
                        📋 Logs
                    </button>
                    <button class="btn btn-sm btn-outline-secondary btn-watcher-detail"
                            data-watcher-id="${escapeHtml(watcher.watcher_id)}">
                        ⓘ Detail
                    </button>
                </div>
            </div>
        </div>
    `;

    return html;
}

/**
 * Get status icon emoji/symbol
 */
function getStatusIcon(status) {
    const icons = {
        'running': '✓',
        'stale': '⚠',
        'offline': '✗',
        'unknown': '?'
    };
    return icons[status] || '?';
}

/**
 * Update health summary section
 */
function updateHealthSummary(summary) {
    const html = `
        <div class="row mt-4">
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="stat-value text-success">${summary.running_count}</div>
                    <div class="stat-label">Running</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="stat-value text-warning">${summary.stale_count}</div>
                    <div class="stat-label">Stale</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="stat-value text-danger">${summary.offline_count}</div>
                    <div class="stat-label">Offline</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="stat-value">${summary.total}</div>
                    <div class="stat-label">Total</div>
                </div>
            </div>
        </div>
    `;

    $('#health-summary').html(html);
}

/**
 * Fetch and display task counts
 */
function refreshTaskCounts() {
    $.ajax({
        url: '/api/tasks.php?type=pending&limit=1',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            $('#pending-task-count').text(data.count || 0);
        },
        error: function() {
            console.error('Failed to fetch task count');
        }
    });
}

/**
 * Process pending result files from console_inbox
 * Updates job statuses (started_at, finished_at, success/failure)
 */
function processResults() {
    $.ajax({
        url: '/api/process_results.php',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success && data.processed_count > 0) {
                console.log(`Processed ${data.processed_count} result file(s)`);
            }
        },
        error: function(xhr, status, error) {
            console.warn('Failed to process results:', status, error);
            // Non-critical error - don't disrupt dashboard
        }
    });
}

/**
 * Create a supervisor control flag
 */
function createSupervisorFlag(action, worker_id, label, commits, promptId, $btn) {
    disableButton($btn);

    // Build params based on action
    const params = {};
    if (action === 'rollback_code') {
        params.commits = parseInt(commits);
    }

    // Build prompt_spec if a prompt is selected
    let promptSpec = null;
    if (promptId) {
        promptSpec = {
            prompt_id: parseInt(promptId),
            model: $('#control-prompt-model').val(),
            timeout_seconds: 300
        };
    }

    const payload = {
        flag_type: 'supervisor_control',
        handler: action,
        worker_id: worker_id,
        label: label,
        params: params
    };

    // Include prompt_spec if present
    if (promptSpec) {
        payload.prompt_spec = promptSpec;
    }

    $.ajax({
        url: '/api/create_flag.php',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success) {
                showSuccess(`Control flag created: ${action} for ${worker_id}` +
                    (label ? ` (${label})` : '') +
                    ` [Task: ${data.task_id}]`);
                // Clear label after successful creation
                $('#control-label').val('');
                // Refresh dashboard
                setTimeout(refreshDashboard, 500);
            } else {
                showError(data.error || 'Failed to create flag');
            }
        },
        error: function(xhr, status, error) {
            console.error('Create flag API error:', status, error);
            let errorMsg = 'Failed to create control flag';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            showError(errorMsg);
        },
        complete: function() {
            enableButton($btn);
        }
    });
}

/**
 * Restart a watcher
 */
function restartWatcher(watcherId, $btn) {
    if (!confirm(`Are you sure you want to restart ${watcherId}?`)) {
        return;
    }

    disableButton($btn);

    $.ajax({
        url: '/api/control.php',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            action: 'restart_watcher',
            watcher_id: watcherId
        }),
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success) {
                showSuccess(data.message);
                // Refresh immediately
                setTimeout(refreshDashboard, 500);
            } else {
                showError(data.message || 'Failed to restart watcher');
            }
        },
        error: function(xhr, status, error) {
            console.error('Control API error:', status, error);
            showError('Failed to send restart signal');
        },
        complete: function() {
            enableButton($btn);
        }
    });
}

/**
 * Show watcher detail modal
 */
function showWatcherDetail(watcherId) {
    // Create modal
    const modalId = 'watcher-detail-modal-' + watcherId;
    const existingModal = document.getElementById(modalId);
    if (existingModal) {
        const modal = new bootstrap.Modal(existingModal);
        modal.show();
        return;
    }

    // Fetch watcher details
    $.ajax({
        url: '/api/watcher.php?id=' + encodeURIComponent(watcherId),
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            showWatcherDetailModal(data);
        },
        error: function(xhr, status, error) {
            console.error('Watcher detail API error:', status, error);
            showError('Failed to load watcher details');
        }
    });
}

/**
 * Render watcher detail modal
 */
function showWatcherDetailModal(data) {
    const watcher = data.watcher;
    const statusBadgeClass = getStatusBadgeClass(watcher.status);

    const html = `
        <div class="modal fade" id="watcher-detail-modal-${watcher.watcher_id}" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            ${escapeHtml(watcher.watcher_id)}
                            <span class="badge ${statusBadgeClass}">${watcher.status.toUpperCase()}</span>
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <h6>Status Information</h6>
                        <dl class="row">
                            <dt class="col-sm-4">Hostname</dt>
                            <dd class="col-sm-8">${escapeHtml(watcher.hostname || 'Unknown')}</dd>

                            <dt class="col-sm-4">Status</dt>
                            <dd class="col-sm-8">${escapeHtml(watcher.status)}</dd>

                            <dt class="col-sm-4">Last Heartbeat</dt>
                            <dd class="col-sm-8">${escapeHtml(watcher.last_heartbeat_formatted)}</dd>

                            <dt class="col-sm-4">Age</dt>
                            <dd class="col-sm-8">${watcher.age_seconds !== null ? formatDuration(watcher.age_seconds) : 'Unknown'}</dd>

                            <dt class="col-sm-4">PID</dt>
                            <dd class="col-sm-8">${watcher.pid || 'N/A'}</dd>

                            <dt class="col-sm-4">Executable</dt>
                            <dd class="col-sm-8"><code>${escapeHtml(watcher.executable || 'N/A')}</code></dd>

                            <dt class="col-sm-4">Lock Path</dt>
                            <dd class="col-sm-8"><code style="font-size: 11px;">${escapeHtml(watcher.lock_path || 'N/A')}</code></dd>
                        </dl>

                        <h6 class="mt-4">Pending Tasks (${data.pending_tasks.length})</h6>
                        ${data.pending_tasks.length > 0 ?
                            '<ul><li>' + data.pending_tasks.map(t => escapeHtml(t.handler)).join('</li><li>') + '</li></ul>' :
                            '<p class="text-muted">No pending tasks</p>'
                        }

                        <h6>Recent Results (${data.recent_results.length})</h6>
                        ${data.recent_results.length > 0 ?
                            '<table class="table table-sm"><thead><tr><th>Task</th><th>Status</th><th>Duration</th></tr></thead><tbody>' +
                            data.recent_results.map(r =>
                                '<tr><td>' + escapeHtml(r.task_id) + '</td>' +
                                '<td><span class="badge ' + (r.status === 'success' ? 'bg-success' : 'bg-danger') + '">' + escapeHtml(r.status) + '</span></td>' +
                                '<td>' + (r.duration_seconds ? formatDuration(r.duration_seconds) : 'N/A') + '</td></tr>'
                            ).join('') +
                            '</tbody></table>' :
                            '<p class="text-muted">No recent results</p>'
                        }
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    $('body').append(html);
    const modal = new bootstrap.Modal(document.getElementById('watcher-detail-modal-' + data.watcher.watcher_id));
    modal.show();
}

/**
 * Show watcher logs modal
 */
function showWatcherLogs(watcherId) {
    const modalId = 'watcher-logs-modal-' + watcherId;
    const existingModal = document.getElementById(modalId);

    const logsModal = `
        <div class="modal fade" id="${modalId}" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Logs - ${escapeHtml(watcherId)}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div id="logs-container-${watcherId}" style="max-height: 500px; overflow-y: auto; background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px;">
                            <div class="spinner-border spinner-border-sm" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    $('body').append(logsModal);

    // Fetch logs
    $.ajax({
        url: '/api/logs.php?watcher_id=' + encodeURIComponent(watcherId) + '&lines=100',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            let logsHtml = '';
            if (data.logs && data.logs.length > 0) {
                logsHtml = data.logs.map(function(log) {
                    // Escape and format log line
                    const line = log.message || log;
                    return '<div>' + escapeHtml(line) + '</div>';
                }).join('');
            } else {
                logsHtml = '<p class="text-muted">No logs available</p>';
            }

            $('#logs-container-' + watcherId).html(logsHtml);
        },
        error: function(xhr, status, error) {
            console.error('Logs API error:', status, error);
            $('#logs-container-' + watcherId).html(
                '<p class="text-danger">Failed to load logs</p>'
            );
        }
    });

    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
}

/**
 * Disable button and show spinner
 */
function disableButton($btn) {
    $btn.prop('disabled', true);
    $btn.data('original-html', $btn.html());
    $btn.html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...');
}

/**
 * Enable button and hide spinner
 */
function enableButton($btn) {
    $btn.prop('disabled', false);
    if ($btn.data('original-html')) {
        $btn.html($btn.data('original-html'));
    }
}

/**
 * Update last refresh timestamp
 */
function updateLastRefresh() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
    $('#last-refresh-time').text(timeStr);
}

/**
 * Load available prompts into the control panel dropdown
 */
function loadPromptsDropdown() {
    $.ajax({
        url: '/api/list_prompts.php',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success && data.prompts && data.prompts.length > 0) {
                const $select = $('#control-prompt');
                const currentValue = $select.val();

                $select.empty().append('<option value="">None</option>');
                data.prompts.forEach(function(prompt) {
                    const seqNum = String(prompt.sequence_number).padStart(4, '0');
                    $select.append(`<option value="${prompt.prompt_id}">[${seqNum}] ${escapeHtml(prompt.prompt_name)}</option>`);
                });

                // Restore previous selection if still available
                if (currentValue) {
                    $select.val(currentValue);
                }
            }
        },
        error: function() {
            console.warn('Failed to load prompts dropdown');
        }
    });
}
