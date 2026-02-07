/**
 * Diagnostics Viewer JavaScript
 * Loads and displays diagnostic reports
 */

// Initialize on page load
$(document).ready(function() {
    loadDiagnostics();
});

/**
 * Load and display diagnostics list
 */
function loadDiagnostics() {
    $.ajax({
        url: '/api/list_diagnostics.php?limit=50',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success) {
                renderDiagnosticsTable(data.diagnostics);
            } else {
                showError('Failed to load diagnostics');
            }
        },
        error: function(xhr, status, error) {
            console.error('Load diagnostics error:', status, error);
            showError('Failed to load diagnostics');
        }
    });
}

/**
 * Render diagnostics table
 */
function renderDiagnosticsTable(diagnostics) {
    const $tbody = $('#diagnostics-table-body');

    if (!diagnostics || diagnostics.length === 0) {
        $tbody.html('<tr><td colspan="7" class="text-muted text-center">No diagnostics found. Run a diagnostics control flag to generate reports.</td></tr>');
        return;
    }

    $tbody.empty();
    diagnostics.forEach(function(diag) {
        // Build status display
        let statusHtml = '';
        if (diag.watcher_running && diag.watcher_healthy && diag.database_connected) {
            statusHtml = '<span class="badge status-badge status-healthy">All Healthy</span>';
        } else {
            const issues = [];
            if (!diag.watcher_running) issues.push('Watcher Down');
            if (!diag.watcher_healthy) issues.push('Watcher Unhealthy');
            if (!diag.database_connected) issues.push('DB Error');
            statusHtml = `<span class="badge status-badge status-unhealthy">${issues.join(', ')}</span>`;
        }

        const row = `
            <tr>
                <td><strong>${diag.diagnostic_id}</strong></td>
                <td>${escapeHtml(diag.worker_id)}</td>
                <td>${diag.label ? escapeHtml(diag.label) : '<em>--</em>'}</td>
                <td><small>${formatTimestamp(diag.created_at)}</small></td>
                <td>${statusHtml}</td>
                <td>
                    <span class="badge ${diag.disk_percent_free > 20 ? 'bg-success' : 'bg-warning'}">
                        ${diag.disk_percent_free}% free
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="viewDiagnostic(${diag.diagnostic_id})">View</button>
                </td>
            </tr>
        `;
        $tbody.append(row);
    });
}

/**
 * View diagnostic details in modal
 */
function viewDiagnostic(diagnosticId) {
    $.ajax({
        url: '/api/get_diagnostic.php?diagnostic_id=' + diagnosticId,
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success) {
                renderDiagnosticModal(data.diagnostic);
                new bootstrap.Modal(document.getElementById('diagnosticModal')).show();
            } else {
                showError('Failed to load diagnostic details');
            }
        },
        error: function() {
            showError('Failed to load diagnostic details');
        }
    });
}

/**
 * Render diagnostic report in modal
 */
function renderDiagnosticModal(diagnostic) {
    const report = diagnostic.report;

    let html = `
        <div class="row mb-4">
            <div class="col-md-6">
                <h6>Diagnostic Info</h6>
                <ul class="list-unstyled small">
                    <li><strong>ID:</strong> ${diagnostic.diagnostic_id}</li>
                    <li><strong>Task:</strong> <code>${escapeHtml(diagnostic.task_id)}</code></li>
                    <li><strong>Worker:</strong> ${escapeHtml(diagnostic.worker_id)}</li>
                    <li><strong>Label:</strong> ${diagnostic.label ? escapeHtml(diagnostic.label) : '(none)'}</li>
                    <li><strong>Report Time:</strong> ${formatTimestamp(diagnostic.created_at)}</li>
                </ul>
            </div>
            <div class="col-md-6">
                <h6>Status Summary</h6>
                <ul class="list-unstyled small">
                    <li><strong>Watcher Running:</strong> <span class="badge ${diagnostic.watcher_running ? 'bg-success' : 'bg-danger'}">${diagnostic.watcher_running ? 'Yes' : 'No'}</span></li>
                    <li><strong>Watcher Healthy:</strong> <span class="badge ${diagnostic.watcher_healthy ? 'bg-success' : 'bg-danger'}">${diagnostic.watcher_healthy ? 'Yes' : 'No'}</span></li>
                    <li><strong>Database Connected:</strong> <span class="badge ${diagnostic.database_connected ? 'bg-success' : 'bg-danger'}">${diagnostic.database_connected ? 'Yes' : 'No'}</span></li>
                    <li><strong>Disk Free:</strong> <span class="badge bg-info">${diagnostic.disk_percent_free}%</span></li>
                </ul>
            </div>
        </div>
    `;

    // Watcher section
    if (report.watcher) {
        html += `
            <div class="report-section">
                <h6>Watcher Status</h6>
                <dl class="row small">
                    <dt class="col-sm-3">Running:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.watcher.running ? 'bg-success' : 'bg-danger'}">${report.watcher.running ? 'Yes' : 'No'}</span></dd>
                    <dt class="col-sm-3">Healthy:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.watcher.healthy ? 'bg-success' : 'bg-danger'}">${report.watcher.healthy ? 'Yes' : 'No'}</span></dd>
        `;
        if (report.watcher.heartbeat) {
            const hb = report.watcher.heartbeat;
            html += `
                    <dt class="col-sm-3">Process ID:</dt>
                    <dd class="col-sm-9"><code>${hb.pid || 'N/A'}</code></dd>
                    <dt class="col-sm-3">Last Heartbeat:</dt>
                    <dd class="col-sm-9">${formatTimestamp(hb.utc)}</dd>
                    <dt class="col-sm-3">Poll Interval:</dt>
                    <dd class="col-sm-9">${hb.poll_seconds}s</dd>
            `;
        }
        html += `</dl></div>`;
    }

    // Database section
    if (report.database) {
        html += `
            <div class="report-section">
                <h6>Database Status</h6>
                <dl class="row small">
                    <dt class="col-sm-3">Connected:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.database.connected ? 'bg-success' : 'bg-danger'}">${report.database.connected ? 'Yes' : 'No'}</span></dd>
        `;
        if (report.database.error) {
            html += `
                    <dt class="col-sm-3">Error:</dt>
                    <dd class="col-sm-9"><code class="text-danger">${escapeHtml(report.database.error)}</code></dd>
            `;
        }
        html += `</dl></div>`;
    }

    // NAS section
    if (report.nas) {
        html += `
            <div class="report-section">
                <h6>NAS Accessibility</h6>
                <dl class="row small">
                    <dt class="col-sm-3">State Path:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.nas.state ? 'bg-success' : 'bg-danger'}">${report.nas.state ? 'OK' : 'Missing'}</span></dd>
                    <dt class="col-sm-3">Logs Path:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.nas.logs ? 'bg-success' : 'bg-danger'}">${report.nas.logs ? 'OK' : 'Missing'}</span></dd>
                    <dt class="col-sm-3">Worker Inbox:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.nas.worker_inbox ? 'bg-success' : 'bg-danger'}">${report.nas.worker_inbox ? 'OK' : 'Missing'}</span></dd>
                    <dt class="col-sm-3">Worker Outbox:</dt>
                    <dd class="col-sm-9"><span class="badge ${report.nas.worker_outbox ? 'bg-success' : 'bg-danger'}">${report.nas.worker_outbox ? 'OK' : 'Missing'}</span></dd>
                </dl>
            </div>
        `;
    }

    // Disk section
    if (report.disk) {
        html += `
            <div class="report-section">
                <h6>Disk Space</h6>
                <dl class="row small">
                    <dt class="col-sm-3">Total:</dt>
                    <dd class="col-sm-9">${report.disk.total_gb.toFixed(2)} GB</dd>
                    <dt class="col-sm-3">Used:</dt>
                    <dd class="col-sm-9">${report.disk.used_gb.toFixed(2)} GB</dd>
                    <dt class="col-sm-3">Free:</dt>
                    <dd class="col-sm-9"><strong>${report.disk.free_gb.toFixed(2)} GB</strong> (${report.disk.percent_free.toFixed(1)}%)</dd>
                </dl>
            </div>
        `;
    }

    // Pending tasks section
    if (report.pending_tasks && report.pending_tasks.length > 0) {
        html += `
            <div class="report-section">
                <h6>Pending Tasks (${report.pending_tasks.length})</h6>
                <ul class="small">
        `;
        report.pending_tasks.forEach(function(task) {
            html += `<li><code>${escapeHtml(task)}</code></li>`;
        });
        html += `</ul></div>`;
    }

    // Full JSON
    html += `
        <div class="report-section">
            <h6>Full Report (JSON)</h6>
            <pre>${escapeHtml(JSON.stringify(report, null, 2))}</pre>
        </div>
    `;

    $('#diagnostic-content').html(html);
}
