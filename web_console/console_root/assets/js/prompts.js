/**
 * Prompts Management JavaScript
 * Handles prompt uploads, listing, viewing, and deletion
 */

// Initialize on page load
$(document).ready(function() {
    loadPrompts();
});

/**
 * Load and display prompts list
 */
function loadPrompts() {
    $.ajax({
        url: '/api/list_prompts.php',
        method: 'GET',
        dataType: 'json',
        timeout: 10000,
        success: function(data) {
            if (data.success) {
                renderPromptsTable(data.prompts);
            } else {
                showError('Failed to load prompts');
            }
        },
        error: function(xhr, status, error) {
            console.error('Load prompts error:', status, error);
            showError('Failed to load prompts');
        }
    });
}

/**
 * Render prompts table
 */
function renderPromptsTable(prompts) {
    const $tbody = $('#prompts-table-body');

    if (prompts.length === 0) {
        $tbody.html('<tr><td colspan="7" class="text-center text-muted">No prompts found. Upload one to get started.</td></tr>');
        return;
    }

    $tbody.empty();
    prompts.forEach(function(prompt) {
        const row = `
            <tr>
                <td><span class="badge bg-secondary">${String(prompt.sequence_number).padStart(4, '0')}</span></td>
                <td>${escapeHtml(prompt.prompt_name)}</td>
                <td><code class="small">${escapeHtml(prompt.prompt_filename)}</code></td>
                <td>${formatBytes(prompt.file_size)}</td>
                <td>${escapeHtml(prompt.uploaded_by)}</td>
                <td><small>${formatTimestamp(prompt.uploaded_at)}</small></td>
                <td>
                    <button class="btn btn-sm btn-outline-info" onclick="viewPrompt(${prompt.prompt_id})">View</button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deletePrompt(${prompt.prompt_id})">Delete</button>
                </td>
            </tr>
        `;
        $tbody.append(row);
    });
}

/**
 * Format bytes to human-readable size
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format timestamp to human-readable date
 */
function formatTimestamp(isoString) {
    if (!isoString) return 'Unknown';
    const date = new Date(isoString);
    return date.toLocaleString();
}

/**
 * Handle file upload
 */
$(document).on('submit', '#prompt-upload-form', function(e) {
    e.preventDefault();
    const $btn = $(this).find('button[type="submit"]');
    const formData = new FormData(this);

    // Validate form
    if (!$('#prompt-name').val() || !$('#prompt-file').val()) {
        showError('Please fill in all fields');
        return;
    }

    disableButton($btn);

    $.ajax({
        url: '/api/upload_prompt.php',
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        dataType: 'json',
        timeout: 30000,
        success: function(data) {
            if (data.success) {
                showSuccess('Prompt uploaded successfully: ' + data.filename);
                $('#prompt-upload-form')[0].reset();
                loadPrompts();
            } else {
                showError(data.error || 'Upload failed');
            }
        },
        error: function(xhr, status, error) {
            console.error('Upload error:', status, error);
            let errorMsg = 'Failed to upload prompt';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            showError(errorMsg);
        },
        complete: function() {
            enableButton($btn);
        }
    });
});

/**
 * View prompt content in modal
 */
function viewPrompt(promptId) {
    $.ajax({
        url: '/api/get_prompt.php?prompt_id=' + promptId,
        method: 'GET',
        dataType: 'json',
        success: function(data) {
            if (data.success) {
                const prompt = data.prompt;
                $('#promptModalTitle').text('Prompt: ' + escapeHtml(prompt.prompt_name));
                $('#promptContentPre').text(prompt.content);
                new bootstrap.Modal(document.getElementById('promptContentModal')).show();
            } else {
                showError('Failed to load prompt');
            }
        },
        error: function() {
            showError('Failed to load prompt');
        }
    });
}

/**
 * Delete prompt (with confirmation)
 */
function deletePrompt(promptId) {
    if (!confirm('Are you sure you want to delete this prompt? It will be soft-deleted and can be restored if needed.')) {
        return;
    }

    $.ajax({
        url: '/api/delete_prompt.php',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ prompt_id: promptId }),
        dataType: 'json',
        success: function(data) {
            if (data.success) {
                showSuccess('Prompt deleted successfully');
                loadPrompts();
            } else {
                showError(data.error || 'Delete failed');
            }
        },
        error: function() {
            showError('Failed to delete prompt');
        }
    });
}
