/**
 * Cornerstone Archive Console - Shared Utilities
 * AJAX helpers, formatting, and common functions
 */

/**
 * Format a timestamp to relative time (e.g., "5 minutes ago")
 */
function formatRelativeTime(isoString) {
    if (!isoString) return 'Never';

    const date = new Date(isoString);
    const now = new Date();
    const secondsAgo = Math.floor((now - date) / 1000);

    if (secondsAgo < 60) return secondsAgo + 's ago';
    if (secondsAgo < 3600) return Math.floor(secondsAgo / 60) + 'm ago';
    if (secondsAgo < 86400) return Math.floor(secondsAgo / 3600) + 'h ago';
    return Math.floor(secondsAgo / 86400) + 'd ago';
}

/**
 * Format seconds to human-readable duration
 */
function formatDuration(seconds) {
    if (!seconds) return '0s';
    if (seconds < 60) return seconds + 's';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h';
    return Math.floor(seconds / 86400) + 'd';
}

/**
 * Get status badge color class
 */
function getStatusBadgeClass(status) {
    const statusMap = {
        'running': 'badge-running',
        'stale': 'badge-stale',
        'offline': 'badge-offline',
        'unknown': 'badge-unknown'
    };
    return statusMap[status] || 'badge-unknown';
}

/**
 * Show success notification
 */
function showSuccess(message) {
    const alertHtml = `
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            ${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    prependAlert(alertHtml);
}

/**
 * Show error notification
 */
function showError(message) {
    const alertHtml = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            ${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    prependAlert(alertHtml);
}

/**
 * Show info notification
 */
function showInfo(message) {
    const alertHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert">
            ${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    prependAlert(alertHtml);
}

/**
 * Prepend alert to the page
 */
function prependAlert(alertHtml) {
    const alertContainer = $('<div class="container-fluid mt-2"></div>')
        .html(alertHtml)
        .prependTo('body');

    // Auto-dismiss after 5 seconds
    setTimeout(function() {
        alertContainer.fadeOut(function() {
            $(this).remove();
        });
    }, 5000);
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

/**
 * Make AJAX request with error handling
 */
function ajaxRequest(url, method, data = null, successCallback = null) {
    const options = {
        url: url,
        method: method || 'GET',
        dataType: 'json',
        success: function(response) {
            if (successCallback) {
                successCallback(response);
            }
        },
        error: function(xhr, status, error) {
            let errorMsg = 'Request failed';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            showError(errorMsg);
            console.error('AJAX Error:', status, error);
        }
    };

    if (data) {
        options.data = JSON.stringify(data);
        options.contentType = 'application/json';
    }

    $.ajax(options);
}

/**
 * Disable buttons during operation
 */
function disableButton($btn, originalText = null) {
    $btn.prop('disabled', true);
    $btn.html('<span class="spinner-border spinner-border-sm" role="status"></span>');
    $btn.data('original-text', originalText || $btn.html());
}

/**
 * Re-enable buttons after operation
 */
function enableButton($btn) {
    const originalText = $btn.data('original-text') || $btn.html();
    $btn.prop('disabled', false);
    $btn.html(originalText);
}
