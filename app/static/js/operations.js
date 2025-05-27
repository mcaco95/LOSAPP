// Alert Management Functions
let currentAlertId = null;
let alertDetailsModal = null;

// Global variables for editing
let users = [];
let currentEditingCell = null;

// Global variables for sorting
let currentSortBy = 'timestamp';
let currentSortOrder = 'desc';

// Global variables for phone integration
let currentDriverPhone = null;
let currentDriverName = null;
let currentCompanyName = null;
let availableDrivers = [];
let availableVehicles = [];

// Initialize filters and components
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap modal
    const modalElement = document.getElementById('alertDetailsModal');
    if (modalElement) {
        alertDetailsModal = new bootstrap.Modal(modalElement);
    }
    
    // Set up filter event listeners
    document.getElementById('statusFilter')?.addEventListener('change', loadAlerts);
    document.getElementById('assignmentFilter')?.addEventListener('change', loadAlerts);
    document.getElementById('dateFilter')?.addEventListener('change', loadAlerts);
    document.getElementById('searchFilter')?.addEventListener('input', debounce(loadAlerts, 300));
    document.getElementById('clientFilter')?.addEventListener('change', loadAlerts);
    document.getElementById('alertsPerPage')?.addEventListener('change', loadAlerts);
    
    // Add sorting event listeners to table headers
    setupSortableHeaders();
    
    // Load initial alerts
    loadAlerts();
    
    // Load users for assignment dropdown
    loadUsers();
    
    // Load clients for filter dropdown
    loadClients();
    
    // Initialize dashboard
    loadKPIs();
    
    // Set up refresh interval for KPIs (every 5 minutes)
    setInterval(loadKPIs, 5 * 60 * 1000);

    // Add note button handler
    document.getElementById('addNoteBtn')?.addEventListener('click', async function() {
        const noteText = document.getElementById('newNoteText').value.trim();
        
        if (!noteText) {
            showError('Please enter a note');
            return;
        }
        
        if (!currentAlertId) {
            showError('No alert selected');
            return;
        }
        
        try {
            const response = await fetch(`/samsara/alerts/${currentAlertId}/notes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                },
                body: JSON.stringify({ notes: noteText })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                showSuccess('Note added successfully');
                document.getElementById('newNoteText').value = '';
                refreshActivities();
            } else {
                showError(data.message || 'Failed to add note');
            }
        } catch (error) {
            console.error('Error adding note:', error);
            showError('Failed to add note');
        }
    });
});

// Debounce function for search input
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Setup sortable headers
function setupSortableHeaders() {
    const sortableHeaders = document.querySelectorAll('.sortable-header');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const sortBy = this.dataset.sort;
            if (currentSortBy === sortBy) {
                // Toggle sort order
                currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                // New sort field
                currentSortBy = sortBy;
                currentSortOrder = 'desc';
            }
            updateSortIcons();
            loadAlerts();
        });
    });
}

// Update sort icons in headers
function updateSortIcons() {
    const sortableHeaders = document.querySelectorAll('.sortable-header');
    sortableHeaders.forEach(header => {
        const icon = header.querySelector('.sort-icon');
        if (icon) {
            if (header.dataset.sort === currentSortBy) {
                icon.className = `fas fa-sort-${currentSortOrder === 'asc' ? 'up' : 'down'} sort-icon`;
            } else {
                icon.className = 'fas fa-sort sort-icon';
            }
        }
    });
}

// Load alerts with filters
async function loadAlerts(page = 1) {
    try {
        const status = document.getElementById('statusFilter')?.value;
        const assignment = document.getElementById('assignmentFilter')?.value;
        const client = document.getElementById('clientFilter')?.value;
        const date = document.getElementById('dateFilter')?.value;
        const search = document.getElementById('searchFilter')?.value;
        const perPage = document.getElementById('alertsPerPage')?.value || 20;  // Changed default to 20
        
        let url = `/samsara/alerts?page=${page}&per_page=${perPage}&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;
        
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (assignment === 'my_alerts' && currentUserId) url += `&assigned_user_id=${currentUserId}`;
        if (assignment === 'unassigned') url += `&assigned_user_id=none`;
        if (client) url += `&client_id=${encodeURIComponent(client)}`;
        if (date) url += `&date=${encodeURIComponent(date)}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        
        const response = await fetch(url);
        
        // Check if response is redirecting to login page
        if (response.redirected || response.status === 401 || response.status === 403) {
            showError('Your session has expired. Please refresh the page to log in again.');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
            return;
        }
        
        // Check if response is HTML instead of JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
            showError('Your session has expired. Please refresh the page to log in again.');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
            return;
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            renderAlerts(data.alerts);
            updatePagination(data.current_page, data.pages, data.total);
            updateSortIcons(); // Update sort indicators
        } else {
            showError('Failed to load alerts');
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
        if (error instanceof SyntaxError) {
            showError('Your session has expired. Please refresh the page to log in again.');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showError('Failed to load alerts');
        }
    }
}

// Render alerts in table
function renderAlerts(alerts) {
    const tbody = document.getElementById('alertsTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    alerts.forEach(alert => {
        const row = document.createElement('tr');
        row.className = getRowClass(alert.status, alert.severity);
        
        // Format timestamps
        const alertTime = formatCompactDateTime(alert.timestamp);
        const createdTime = formatCompactDateTime(alert.created_at);
        const updatedTime = formatCompactDateTime(alert.updated_at);
        
        row.innerHTML = `
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="showAlertDetails(${alert.id})" title="View Details">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
            <td title="${formatLocalDateTime(alert.timestamp)}">${alertTime}</td>
            <td title="${formatLocalDateTime(alert.created_at)}">${createdTime}</td>
            <td title="${formatLocalDateTime(alert.updated_at)}">${updatedTime}</td>
            <td title="${alert.vehicle_name || 'Unknown'}">${truncateText(alert.vehicle_name || 'Unknown', 8)}</td>
            <td title="${alert.driver_name || 'Unknown'}">${truncateText(alert.driver_name || 'Unknown', 12)}</td>
            <td title="${alert.alert_type}">${truncateText(alert.alert_type, 15)}</td>
            <td>
                <select class="form-select severity-select severity-${alert.severity}" data-alert-id="${alert.id}" data-field="severity">
                    <option value="low" ${alert.severity === 'low' ? 'selected' : ''}>🟢 Low</option>
                    <option value="medium" ${alert.severity === 'medium' ? 'selected' : ''}>🟡 Medium</option>
                    <option value="high" ${alert.severity === 'high' ? 'selected' : ''}>🟠 High</option>
                    <option value="critical" ${alert.severity === 'critical' ? 'selected' : ''}>🔴 Critical</option>
                </select>
            </td>
            <td>
                <select class="form-select status-select status-${alert.status}" data-alert-id="${alert.id}" data-field="status">
                    <option value="unassigned" ${alert.status === 'unassigned' ? 'selected' : ''}>⚪ Unassigned</option>
                    <option value="assigned" ${alert.status === 'assigned' ? 'selected' : ''}>🔵 Assigned</option>
                    <option value="in_progress" ${alert.status === 'in_progress' ? 'selected' : ''}>🟡 In Progress</option>
                    <option value="resolved" ${alert.status === 'resolved' ? 'selected' : ''}>✅ Resolved</option>
                    <option value="escalated" ${alert.status === 'escalated' ? 'selected' : ''}>🚨 Escalated</option>
                </select>
            </td>
            <td>
                <select class="form-select assignment-select ${alert.assigned_to ? 'assigned' : 'unassigned'}" data-alert-id="${alert.id}" data-field="assigned_user_id">
                    <option value="">👤 Unassigned</option>
                    ${users.map(user => 
                        `<option value="${user.id}" ${alert.assigned_to && alert.assigned_to.id === user.id ? 'selected' : ''}>${truncateText(user.name, 12)}</option>`
                    ).join('')}
                </select>
            </td>
            <td title="${alert.client_name || 'Unknown'}">${truncateText(alert.client_name || 'Unknown', 10)}</td>
            <td class="note-column" title="${alert.latest_note || 'No notes'}">${alert.latest_note_truncated || '<em>No notes</em>'}</td>
            <td title="${alert.last_edited_by ? alert.last_edited_by.name : 'Unknown'}">${truncateText(alert.last_edited_by ? alert.last_edited_by.name : 'Unknown', 12)}</td>
        `;
        
        tbody.appendChild(row);
    });
    
    // Attach event listeners for quick edits
    attachQuickEditListeners();
}

// Load users for assignment
async function loadUsers() {
    try {
        const response = await fetch('/users/operations');
        const data = await response.json();
        
        if (data.status === 'success') {
            users = data.users;
            const select = document.getElementById('assignToUser');
            select.innerHTML = '<option value="">Select User</option>';
            
            users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.name;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading users:', error);
        showError('Failed to load users');
    }
}

// Load clients for filter
async function loadClients() {
    try {
        const response = await fetch('/samsara/clients/list');
        const data = await response.json();
        
        if (data.status === 'success') {
            const select = document.getElementById('clientFilter');
            select.innerHTML = '<option value="">All Clients</option>';
            
            data.clients.forEach(client => {
                const option = document.createElement('option');
                option.value = client.id;
                option.textContent = client.name;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading clients:', error);
        showError('Failed to load clients');
    }
}

// Show alert details
async function showAlertDetails(alertId) {
    try {
        currentAlertId = alertId;
        const response = await fetch(`/samsara/alerts/${alertId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const alert = data.alert;
            
            // Update modal fields
            document.getElementById('modalAlertId').textContent = alert.alert_id;
            document.getElementById('modalAlertType').textContent = alert.alert_type;
            document.getElementById('modalSeverity').innerHTML = `<span class="badge bg-${getSeverityClass(alert.severity)}">${alert.severity}</span>`;
            document.getElementById('modalStatus').innerHTML = `<span class="badge bg-${getStatusClass(alert.status)}">${alert.status}</span>`;
            document.getElementById('modalTimestamp').textContent = formatLocalDateTime(alert.timestamp);
            
            document.getElementById('modalVehicle').textContent = alert.vehicle_name || alert.vehicle_id || 'Unknown';
            document.getElementById('modalDriver').textContent = alert.driver_name || 'N/A';
            document.getElementById('modalLocation').textContent = alert.location || 'N/A';
            document.getElementById('modalClient').textContent = alert.client_name || 'Unknown';
            
            // Store company name for call context
            currentCompanyName = alert.client_name || 'Unknown';
            
            // Set up driver call functionality
            if (alert.driver_phone) {
                currentDriverPhone = alert.driver_phone;
                currentDriverName = alert.driver_name;
                document.getElementById('callDriverBtn').style.display = 'inline-block';
            } else {
                currentDriverPhone = null;
                currentDriverName = null;
                document.getElementById('callDriverBtn').style.display = 'none';
            }
            
            document.getElementById('modalDescription').textContent = alert.description;
            
            // Set current assignment if any
            const assignToUser = document.getElementById('assignToUser');
            if (assignToUser) {
                assignToUser.value = alert.assigned_to ? alert.assigned_to.id : '';
            }
            
            // Load drivers and vehicles for assignment dropdowns
            if (alert.client_id) {
                await loadDriversForAssignment(alert.client_id);
                await loadVehiclesForAssignment(alert.client_id);
                
                // Set current selections
                if (alert.driver_id) {
                    document.getElementById('updateDriver').value = alert.driver_id;
                }
                if (alert.vehicle_id) {
                    document.getElementById('updateVehicle').value = alert.vehicle_id;
                }
            }
            
            // Load activities
            renderActivities(alert.activities);
            
            // Set up assignment update event listener (remove existing first)
            const updateAssignmentBtn = document.getElementById('updateAssignment');
            if (updateAssignmentBtn) {
                updateAssignmentBtn.replaceWith(updateAssignmentBtn.cloneNode(true));
                document.getElementById('updateAssignment').addEventListener('click', updateAlertAssignment);
            }
            
            // Show modal
            if (alertDetailsModal) {
                alertDetailsModal.show();
            } else {
                console.error('Modal not initialized');
                showError('Could not display alert details');
            }
        }
    } catch (error) {
        console.error('Error loading alert details:', error);
        showError('Failed to load alert details');
    }
}

// Render activities in timeline
function renderActivities(activities) {
    const timeline = document.getElementById('activityTimeline');
    timeline.innerHTML = '';
    
    if (!activities || activities.length === 0) {
        timeline.innerHTML = '<div class="text-center text-muted py-3">No activities yet</div>';
        return;
    }
    
    activities.forEach(activity => {
        const activityElement = createActivityElement(activity);
        timeline.appendChild(activityElement);
    });
}

// Create activity element
function createActivityElement(activity) {
    const div = document.createElement('div');
    div.className = 'timeline-item mb-3';
    
    const iconClass = getActivityIcon(activity.activity_type);
    const badgeClass = getActivityBadgeClass(activity.activity_type);
    
    let changeInfo = '';
    if (activity.old_value && activity.new_value) {
        changeInfo = `<small class="text-muted d-block">Changed from "${activity.old_value}" to "${activity.new_value}"</small>`;
    } else if (activity.new_value && !activity.old_value) {
        changeInfo = `<small class="text-muted d-block">Set to "${activity.new_value}"</small>`;
    } else if (activity.old_value && !activity.new_value) {
        changeInfo = `<small class="text-muted d-block">Removed "${activity.old_value}"</small>`;
    }
    
    div.innerHTML = `
        <div class="d-flex">
            <div class="flex-shrink-0">
                <span class="badge bg-${badgeClass} rounded-pill">
                    <i class="fas ${iconClass}"></i>
                </span>
            </div>
            <div class="flex-grow-1 ms-3">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${activity.description}</h6>
                        ${changeInfo}
                        ${activity.notes ? `<div class="mt-2 p-2 bg-light rounded"><small>${activity.notes}</small></div>` : ''}
                    </div>
                    <small class="text-muted">${formatLocalDateTime(activity.created_at)}</small>
                </div>
                <small class="text-muted">by ${activity.user_name}</small>
            </div>
        </div>
    `;
    
    return div;
}

// Get activity icon
function getActivityIcon(activityType) {
    const icons = {
        'status_change': 'fa-exchange-alt',
        'assignment': 'fa-user',
        'severity_change': 'fa-exclamation-triangle',
        'note': 'fa-comment',
        'resolution': 'fa-check-circle',
        'created': 'fa-plus-circle',
        'call_initiated': 'fa-phone',
        'call_completed': 'fa-phone-slash'
    };
    return icons[activityType] || 'fa-circle';
}

// Get activity badge class
function getActivityBadgeClass(activityType) {
    const classes = {
        'status_change': 'primary',
        'assignment': 'info',
        'severity_change': 'warning',
        'note': 'secondary',
        'resolution': 'success',
        'created': 'dark',
        'call_initiated': 'success',
        'call_completed': 'success'
    };
    return classes[activityType] || 'secondary';
}

// Assign alert to user
document.getElementById('assignAlert').addEventListener('click', async function() {
    try {
        const userId = document.getElementById('assignToUser').value;
        
        if (!userId) {
            showError('Please select a user to assign the alert to');
            return;
        }
        
        // Get CSRF token from meta tag
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        
        if (!csrfToken) {
            console.error('CSRF token not found');
            showError('Security token not found. Please refresh the page.');
            return;
        }
        
        console.log('Making assignment request:', {
            currentAlertId,
            userId,
            hasCSRFToken: !!csrfToken
        });
        
        const response = await fetch(`/samsara/alerts/${currentAlertId}/assign`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ user_id: userId }),
            credentials: 'same-origin'
        });
        
        // Log response details for debugging
        console.log('Assignment response:', {
            status: response.status,
            statusText: response.statusText,
            contentType: response.headers.get('content-type')
        });
        
        // Check if response is redirecting to login page
        if (response.redirected || response.status === 401 || response.status === 403) {
            showError('Your session has expired. Please refresh the page to log in again.');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
            return;
        }
        
        // Check if response is HTML instead of JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
            console.error('Received HTML response instead of JSON');
            showError('Unexpected response from server. Please try again.');
            return;
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showSuccess('Alert assigned successfully');
            loadAlerts(); // Refresh the alerts list
            if (alertDetailsModal) {
                alertDetailsModal.hide();
            }
        } else {
            showError(data.message || 'Failed to assign alert');
        }
    } catch (error) {
        console.error('Error assigning alert:', error);
        showError('Failed to assign alert. Please try again.');
    }
});

// Update alert status (modified to work with new system)
document.getElementById('updateAlertStatus').addEventListener('click', async function() {
    try {
        const status = document.getElementById('updateStatus').value;
        
        if (!status) {
            showError('Please select a status');
            return;
        }
        
        // For resolved/escalated status, prompt for notes
        let notes = '';
        if (status === 'resolved' || status === 'escalated') {
            notes = prompt(`Please provide notes for ${status} status:`);
            if (notes === null) return; // User cancelled
            if (!notes.trim()) {
                showError('Notes are required for this status');
                return;
            }
        }
        
        const requestBody = { 
            status: status
        };
        
        // Only add notes if they exist and are not empty
        if (notes && notes.trim()) {
            requestBody.notes = notes.trim();
        }
        
        const response = await fetch(`/samsara/alerts/${currentAlertId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // If we have notes for escalated/resolved, also create a separate note entry
            if ((status === 'resolved' || status === 'escalated') && requestBody.notes) {
                try {
                    await fetch(`/samsara/alerts/${currentAlertId}/notes`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                        },
                        body: JSON.stringify({ notes: `${status.charAt(0).toUpperCase() + status.slice(1)} Details: ${requestBody.notes}` })
                    });
                } catch (noteError) {
                    console.warn('Failed to create separate note entry:', noteError);
                    // Don't fail the whole operation if note creation fails
                }
            }
            
            showSuccess('Alert status updated successfully');
            loadAlerts();  // Refresh alerts table
            refreshActivities(); // Refresh activities
            
            // Clear form
            document.getElementById('updateStatus').value = '';
            
            // Update modal status display
            document.getElementById('modalStatus').innerHTML = `<span class="badge bg-${getStatusClass(status)}">${status}</span>`;
        } else {
            showError(data.message || 'Failed to update alert status');
        }
    } catch (error) {
        console.error('Error updating alert status:', error);
        showError('Failed to update alert status');
    }
});

// Helper functions for status and severity classes
function getSeverityClass(severity) {
    const classes = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'success'
    };
    return classes[severity.toLowerCase()] || 'secondary';
}

function getStatusClass(status) {
    const classes = {
        'unassigned': 'secondary',
        'in_progress': 'primary',
        'resolved': 'success',
        'escalated': 'danger'
    };
    return classes[status.toLowerCase()] || 'secondary';
}

// Toast notifications
function showSuccess(message) {
    // Implement your preferred toast notification
    alert(message);  // Replace with your toast implementation
}

function showError(message) {
    // Implement your preferred toast notification
    alert(message);  // Replace with your toast implementation
}

// Helper function to format date in user's timezone (compact version)
function formatCompactDateTime(utcDateString) {
    if (!utcDateString) return 'N/A';
    try {
        const date = new Date(utcDateString);
        
        if (isNaN(date.getTime())) {
            console.error('Invalid date:', utcDateString);
            return 'Invalid';
        }
        
        // More compact format
        const options = {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        };

        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const formatter = new Intl.DateTimeFormat('en-US', { ...options, timeZone });
        
        // Format and remove unnecessary parts
        let formatted = formatter.format(date);
        
        // Get current year to decide if we need to show year
        const currentYear = new Date().getFullYear();
        const dateYear = date.getFullYear();
        
        if (dateYear !== currentYear) {
            formatted = `${formatted.split(',')[0]}/${dateYear.toString().slice(-2)}`;
        }
        
        return formatted;
    } catch (error) {
        console.error('Error formatting date:', error, utcDateString);
        return 'Invalid';
    }
}

// Helper function to format date in user's timezone
function formatLocalDateTime(utcDateString) {
    if (!utcDateString) return 'N/A';
    try {
        // Parse the UTC date string
        const date = new Date(utcDateString);
        
        // Check if the date is valid
        if (isNaN(date.getTime())) {
            console.error('Invalid date:', utcDateString);
            return 'Invalid Date';
        }
        
        // Format options for date and time
        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
            timeZoneName: 'short'
        };

        // Get user's timezone
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        
        // Format the date in the user's local timezone
        const formatter = new Intl.DateTimeFormat('en-US', { ...options, timeZone });
        return formatter.format(date);
    } catch (error) {
        console.error('Error formatting date:', error, utcDateString);
        return 'Invalid Date';
    }
}

// Add pagination controls
function updatePagination(currentPage, totalPages, totalItems) {
    const paginationContainer = document.getElementById('alertsPagination');
    if (!paginationContainer) return;

    let html = '<ul class="pagination justify-content-center">';
    
    // Previous button
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadAlerts(${currentPage - 1}); return false;">Previous</a>
        </li>
    `;
    
    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        html += `
            <li class="page-item ${currentPage === i ? 'active' : ''}">
                <a class="page-link" href="#" onclick="loadAlerts(${i}); return false;">${i}</a>
            </li>
        `;
    }
    
    // Next button
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadAlerts(${currentPage + 1}); return false;">Next</a>
        </li>
    `;
    
    html += '</ul>';
    
    // Add total items count
    html += `<div class="text-center mt-2">Total items: ${totalItems}</div>`;
    
    paginationContainer.innerHTML = html;
}

// Show severity edit dropdown
function showSeverityEdit(cell) {
    if (currentEditingCell) return;
    currentEditingCell = cell;

    const alertId = cell.dataset.alertId;
    const currentValue = cell.dataset.value;
    
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm';
    select.innerHTML = `
        <option value="critical" ${currentValue === 'critical' ? 'selected' : ''}>Critical</option>
        <option value="high" ${currentValue === 'high' ? 'selected' : ''}>High</option>
        <option value="medium" ${currentValue === 'medium' ? 'selected' : ''}>Medium</option>
        <option value="low" ${currentValue === 'low' ? 'selected' : ''}>Low</option>
    `;
    
    const originalContent = cell.innerHTML;
    cell.innerHTML = '';
    cell.appendChild(select);
    
    select.focus();
    
    select.addEventListener('change', async () => {
        const newValue = select.value;
        try {
            console.log('Updating severity to:', newValue); // Debug log
            
            const requestData = { 
                severity: newValue
            };
            
            console.log('Sending request data:', requestData); // Debug log
            
            const response = await fetch(`/samsara/alerts/${alertId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                },
                body: JSON.stringify(requestData)
            });
            
            const responseData = await response.json();
            console.log('Response:', response.status, responseData); // Debug log
            
            if (response.ok) {
                loadAlerts(); // Refresh the table
                showSuccess(responseData.message || 'Severity updated successfully');
            } else {
                cell.innerHTML = originalContent;
                showError(responseData.message || 'Failed to update severity');
            }
        } catch (error) {
            console.error('Error updating severity:', error);
            cell.innerHTML = originalContent;
            showError('Failed to update severity. Please try again.');
        }
        currentEditingCell = null;
    });
    
    select.addEventListener('blur', () => {
        setTimeout(() => {
            if (currentEditingCell === cell) {
                cell.innerHTML = originalContent;
                currentEditingCell = null;
            }
        }, 200); // Small delay to allow the change event to fire first
    });
}

// Show status edit dropdown
function showStatusEdit(cell) {
    if (currentEditingCell) return;
    currentEditingCell = cell;

    const alertId = cell.dataset.alertId;
    const currentValue = cell.dataset.value;
    
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm';
    select.innerHTML = `
        <option value="unassigned" ${currentValue === 'unassigned' ? 'selected' : ''}>Unassigned</option>
        <option value="in_progress" ${currentValue === 'in_progress' ? 'selected' : ''}>In Progress</option>
        <option value="resolved" ${currentValue === 'resolved' ? 'selected' : ''}>Resolved</option>
        <option value="escalated" ${currentValue === 'escalated' ? 'selected' : ''}>Escalated</option>
    `;
    
    const originalContent = cell.innerHTML;
    cell.innerHTML = '';
    cell.appendChild(select);
    
    select.focus();
    
    select.addEventListener('change', async () => {
        const newValue = select.value;
        try {
            console.log('Updating status to:', newValue); // Debug log
            
            const requestData = { 
                status: newValue
            };
            
            // For resolved or escalated status, prompt for meaningful notes
            if (newValue === 'resolved' || newValue === 'escalated') {
                const userNotes = prompt(`Please provide details for ${newValue} status:`);
                if (userNotes === null) {
                    // User cancelled, restore original content
                    cell.innerHTML = originalContent;
                    currentEditingCell = null;
                    return;
                }
                if (!userNotes.trim()) {
                    showError('Notes are required for this status');
                    cell.innerHTML = originalContent;
                    currentEditingCell = null;
                    return;
                }
                requestData.notes = userNotes.trim();
            }
            
            console.log('Sending request data:', requestData); // Debug log
            
            const response = await fetch(`/samsara/alerts/${alertId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                },
                body: JSON.stringify(requestData)
            });
            
            const responseData = await response.json();
            console.log('Response:', response.status, responseData); // Debug log
            
            if (response.ok) {
                // If we have notes for escalated/resolved, also create a separate note entry
                if ((newValue === 'resolved' || newValue === 'escalated') && requestData.notes) {
                    try {
                        await fetch(`/samsara/alerts/${alertId}/notes`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                            },
                            body: JSON.stringify({ notes: `${newValue.charAt(0).toUpperCase() + newValue.slice(1)} Details: ${requestData.notes}` })
                        });
                    } catch (noteError) {
                        console.warn('Failed to create separate note entry:', noteError);
                        // Don't fail the whole operation if note creation fails
                    }
                }
                
                loadAlerts(); // Refresh the table
                showSuccess(responseData.message || 'Status updated successfully');
            } else {
                cell.innerHTML = originalContent;
                showError(responseData.message || 'Failed to update status');
            }
        } catch (error) {
            console.error('Error updating status:', error);
            cell.innerHTML = originalContent;
            showError('Failed to update status. Please try again.');
        }
        currentEditingCell = null;
    });
    
    select.addEventListener('blur', () => {
        setTimeout(() => {
            if (currentEditingCell === cell) {
                cell.innerHTML = originalContent;
                currentEditingCell = null;
            }
        }, 200); // Small delay to allow the change event to fire first
    });
}

// Show assign edit dropdown
function showAssignEdit(cell) {
    if (currentEditingCell) return;
    currentEditingCell = cell;

    const alertId = cell.dataset.alertId;
    const currentValue = cell.dataset.value;
    
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm';
    select.innerHTML = '<option value="">Unassigned</option>' +
        users.map(user => `
            <option value="${user.id}" ${currentValue === user.id.toString() ? 'selected' : ''}>
                ${truncateText(user.name, 12)}
            </option>
        `).join('');
    
    const originalContent = cell.innerHTML;
    cell.innerHTML = '';
    cell.appendChild(select);
    
    select.focus();
    
    select.addEventListener('change', async () => {
        const newValue = select.value;
        try {
            const response = await fetch(`/samsara/alerts/${alertId}/assign`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                },
                body: JSON.stringify({ user_id: newValue })
            });
            
            if (response.ok) {
                loadAlerts(); // Refresh the table
            } else {
                const errorData = await response.json();
                cell.innerHTML = originalContent;
                showError(errorData.message || 'Failed to update assignment');
            }
        } catch (error) {
            console.error('Error updating assignment:', error);
            cell.innerHTML = originalContent;
            showError('Failed to update assignment');
        }
        currentEditingCell = null;
    });
    
    select.addEventListener('blur', () => {
        setTimeout(() => {
            if (currentEditingCell === cell) {
                cell.innerHTML = originalContent;
                currentEditingCell = null;
            }
        }, 200); // Small delay to allow the change event to fire first
    });
}

// Add some CSS for the editable cells and timeline
const style = document.createElement('style');
style.textContent = `
    .cursor-pointer {
        cursor: pointer;
    }
    .cursor-pointer:hover {
        opacity: 0.8;
    }
    .severity-cell, .status-cell, .assign-cell {
        position: relative;
    }
    .form-select-sm {
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
        border-radius: 0.2rem;
    }
    
    /* Timeline Styles */
    .timeline {
        position: relative;
    }
    
    .timeline-item {
        position: relative;
        padding-left: 0;
    }
    
    .timeline-item:not(:last-child)::after {
        content: '';
        position: absolute;
        left: 15px;
        top: 40px;
        bottom: -15px;
        width: 2px;
        background-color: #e9ecef;
        z-index: 1;
    }
    
    .timeline-item .badge {
        position: relative;
        z-index: 2;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
    }
    
    .timeline-item .flex-grow-1 {
        min-width: 0;
    }
    
    .timeline-item h6 {
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }
    
    .timeline-item small {
        font-size: 0.75rem;
    }
    
    /* Activity note styling */
    .timeline-item .bg-light {
        border-left: 3px solid #007bff;
        font-style: italic;
    }
    
    /* Scrollbar styling for timeline */
    .timeline::-webkit-scrollbar {
        width: 6px;
    }
    
    .timeline::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    
    .timeline::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 3px;
    }
    
    .timeline::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
`;
document.head.appendChild(style);

// Refresh activities
async function refreshActivities() {
    if (!currentAlertId) return;
    
    try {
        const response = await fetch(`/samsara/alerts/${currentAlertId}/activities`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderActivities(data.activities);
        } else {
            showError('Failed to refresh activities');
        }
    } catch (error) {
        console.error('Error refreshing activities:', error);
        showError('Failed to refresh activities');
    }
}

// Attach event listeners for quick edits
function attachQuickEditListeners() {
    // Severity dropdowns
    document.querySelectorAll('.severity-select').forEach(select => {
        select.addEventListener('change', async (e) => {
            const alertId = e.target.dataset.alertId;
            const newValue = e.target.value;
            
            // Update color class
            e.target.className = `form-select severity-select severity-${newValue}`;
            
            await updateAlertField(alertId, 'severity', newValue);
        });
    });
    
    // Status dropdowns
    document.querySelectorAll('.status-select').forEach(select => {
        select.addEventListener('change', async (e) => {
            const alertId = e.target.dataset.alertId;
            const newValue = e.target.value;
            
            // Update color class
            e.target.className = `form-select status-select status-${newValue}`;
            
            // For resolved or escalated status, prompt for notes
            if (newValue === 'resolved' || newValue === 'escalated') {
                const userNotes = prompt(`Please provide details for ${newValue} status:`);
                if (userNotes === null) {
                    // User cancelled, restore original value
                    e.target.value = e.target.dataset.originalValue || 'unassigned';
                    e.target.className = `form-select status-select status-${e.target.value}`;
                    return;
                }
                if (!userNotes.trim()) {
                    showError('Notes are required for this status');
                    e.target.value = e.target.dataset.originalValue || 'unassigned';
                    e.target.className = `form-select status-select status-${e.target.value}`;
                    return;
                }
                await updateAlertField(alertId, 'status', newValue, userNotes);
            } else {
                await updateAlertField(alertId, 'status', newValue);
            }
        });
        
        // Store original value for cancellation
        select.dataset.originalValue = select.value;
    });
    
    // Assignment dropdowns
    document.querySelectorAll('.assignment-select').forEach(select => {
        select.addEventListener('change', async (e) => {
            const alertId = e.target.dataset.alertId;
            const newValue = e.target.value;
            
            // Update color class
            e.target.className = `form-select assignment-select ${newValue ? 'assigned' : 'unassigned'}`;
            
            await updateAlertField(alertId, 'assigned_user_id', newValue);
        });
    });
}

// Generic function to update alert fields
async function updateAlertField(alertId, field, value, notes = null) {
    try {
        let url, method, body;
        
        if (field === 'severity') {
            url = `/samsara/alerts/${alertId}/severity`;
            method = 'PUT';
            body = JSON.stringify({ severity: value });
        } else if (field === 'status') {
            url = `/samsara/alerts/${alertId}/status`;
            method = 'PUT';
            body = JSON.stringify({ status: value, notes: notes });
        } else if (field === 'assigned_user_id') {
            url = `/samsara/alerts/${alertId}/assign`;
            method = 'PUT';
            body = JSON.stringify({ assigned_user_id: value || null });
        }
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            },
            body: body
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showSuccess(`${field.replace('_', ' ')} updated successfully`);
            
            // If we have notes for escalated/resolved, also create a separate note entry
            if ((value === 'resolved' || value === 'escalated') && notes) {
                try {
                    await fetch(`/samsara/alerts/${alertId}/notes`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                        },
                        body: JSON.stringify({ notes: `${value.charAt(0).toUpperCase() + value.slice(1)} Details: ${notes}` })
                    });
                } catch (noteError) {
                    console.error('Error adding note:', noteError);
                }
            }
            
            // Reload alerts to reflect changes
            loadAlerts();
        } else {
            showError(data.message || `Failed to update ${field}`);
            // Reload to restore original state
            loadAlerts();
        }
    } catch (error) {
        console.error(`Error updating ${field}:`, error);
        showError(`Failed to update ${field}`);
        // Reload to restore original state
        loadAlerts();
    }
}

// Helper function to get row class based on status and severity
function getRowClass(status, severity) {
    if (status === 'resolved') {
        return 'table-success';
    } else if (status === 'escalated') {
        return 'table-danger';
    } else if (severity === 'critical') {
        return 'table-warning';
    }
    return '';
}

// Phone Integration Functions
function initiateDriverCall() {
    if (!currentDriverPhone) {
        showError('No phone number available for this driver');
        return;
    }
    
    // Format phone number with +1 for Twilio
    let formattedPhone = currentDriverPhone;
    if (!formattedPhone.startsWith('+')) {
        formattedPhone = '+1' + formattedPhone.replace(/\D/g, '');
    }
    
    // Store call context for phone interface
    localStorage.setItem('call_context', JSON.stringify({
        type: 'alert_driver_call',
        alert_id: currentAlertId,
        driver_name: currentDriverName,
        driver_phone: formattedPhone,
        company_name: currentCompanyName
    }));
    
    // Open phone window with pre-filled number
    openOperationsPhoneWindow(formattedPhone);
}

function openOperationsPhoneWindow(phoneNumber = '') {
    const phoneWindow = window.open(
        `/operations/phone${phoneNumber ? '?number=' + encodeURIComponent(phoneNumber) : ''}`,
        "LOS_Operations_Phone_Window",
        "width=320,height=600,resizable=yes,top=100,left=100,menubar=no,toolbar=no,location=no,status=no,titlebar=yes"
    );
    if (phoneWindow) phoneWindow.focus();
}

// Load drivers for assignment dropdown
async function loadDriversForAssignment(clientId) {
    try {
        const response = await fetch(`/samsara/fleet/drivers/${clientId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            availableDrivers = data.drivers;
            populateDriverDropdown();
        } else {
            console.error('Failed to load drivers:', data.message);
        }
    } catch (error) {
        console.error('Error loading drivers:', error);
    }
}

// Load vehicles for assignment dropdown
async function loadVehiclesForAssignment(clientId) {
    try {
        const response = await fetch(`/samsara/fleet/vehicles/${clientId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            availableVehicles = data.vehicles;
            populateVehicleDropdown();
        } else {
            console.error('Failed to load vehicles:', data.message);
        }
    } catch (error) {
        console.error('Error loading vehicles:', error);
    }
}

// Populate driver dropdown
function populateDriverDropdown() {
    const driverSelect = document.getElementById('updateDriver');
    if (!driverSelect) return;
    
    driverSelect.innerHTML = '<option value="">Select Driver</option>';
    availableDrivers.forEach(driver => {
        const option = document.createElement('option');
        option.value = driver.driver_id;
        option.textContent = `${truncateText(driver.name, 12)} (${truncateText(driver.username || 'N/A', 12)})`;
        option.dataset.phone = driver.phone || '';
        driverSelect.appendChild(option);
    });
}

// Populate vehicle dropdown
function populateVehicleDropdown() {
    const vehicleSelect = document.getElementById('updateVehicle');
    if (!vehicleSelect) return;
    
    vehicleSelect.innerHTML = '<option value="">Select Vehicle</option>';
    availableVehicles.forEach(vehicle => {
        const option = document.createElement('option');
        option.value = vehicle.vehicle_id;
        option.textContent = `${truncateText(vehicle.name, 12)} (${truncateText(vehicle.vin || 'N/A', 12)})`;
        vehicleSelect.appendChild(option);
    });
}

// Update alert assignment (driver/vehicle)
async function updateAlertAssignment() {
    const driverId = document.getElementById('updateDriver').value;
    const vehicleId = document.getElementById('updateVehicle').value;
    
    if (!driverId && !vehicleId) {
        showError('Please select a driver or vehicle to update');
        return;
    }
    
    if (!currentAlertId) {
        showError('No alert selected');
        return;
    }
    
    try {
        const updateData = {};
        if (driverId) updateData.driver_id = driverId;
        if (vehicleId) updateData.vehicle_id = vehicleId;
        
        const response = await fetch(`/samsara/alerts/${currentAlertId}/assignment`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            },
            body: JSON.stringify(updateData)
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showSuccess('Assignment updated successfully');
            refreshActivities();
            loadAlerts(); // Refresh the main table
            
            // Update modal display
            if (driverId) {
                const selectedDriver = availableDrivers.find(d => d.driver_id === driverId);
                if (selectedDriver) {
                    document.getElementById('modalDriver').textContent = truncateText(selectedDriver.name, 12);
                    currentDriverName = truncateText(selectedDriver.name, 12);
                    currentDriverPhone = selectedDriver.phone;
                    
                    // Show/hide call button based on phone availability
                    const callBtn = document.getElementById('callDriverBtn');
                    if (selectedDriver.phone) {
                        callBtn.style.display = 'inline-block';
                    } else {
                        callBtn.style.display = 'none';
                    }
                }
            }
            
            if (vehicleId) {
                const selectedVehicle = availableVehicles.find(v => v.vehicle_id === vehicleId);
                if (selectedVehicle) {
                    document.getElementById('modalVehicle').textContent = truncateText(selectedVehicle.name, 12);
                }
            }
        } else {
            showError(data.message || 'Failed to update assignment');
        }
    } catch (error) {
        console.error('Error updating assignment:', error);
        showError('Failed to update assignment');
    }
}

// Load KPI data
async function loadKPIs() {
    try {
        const response = await fetch('/operations/kpis');
        const data = await response.json();
        
        if (data.status === 'success') {
            const kpis = data.kpis;
            
            // Update KPI values
            document.getElementById('todayAlerts').textContent = kpis.today_alerts;
            document.getElementById('todayAlertsChange').textContent = 
                `${kpis.today_alerts_change >= 0 ? '+' : ''}${kpis.today_alerts_change} from yesterday`;
            
            document.getElementById('unassignedAlerts').textContent = kpis.unassigned_alerts;
            document.getElementById('unassignedPercentage').textContent = `${kpis.unassigned_percentage}% of total`;
            
            document.getElementById('inProgressAlerts').textContent = kpis.in_progress_alerts;
            document.getElementById('avgResolutionTime').textContent = `Avg: ${kpis.avg_resolution_time}`;
            
            document.getElementById('resolvedToday').textContent = kpis.resolved_today;
            document.getElementById('resolutionRate').textContent = `${kpis.resolution_rate}% resolution rate`;
            
            document.getElementById('criticalAlerts').textContent = kpis.critical_alerts;
            document.getElementById('criticalPercentage').textContent = `${kpis.critical_percentage}% of total`;
            
            document.getElementById('escalatedAlerts').textContent = kpis.escalated_alerts;
            document.getElementById('escalatedAge').textContent = `Avg age: ${kpis.escalated_age}h`;
            
            document.getElementById('avgResponseTime').textContent = `${kpis.avg_response_time}m`;
            
            document.getElementById('activeAgents').textContent = kpis.active_agents;
            document.getElementById('teamEfficiency').textContent = `${kpis.team_efficiency} alerts/agent`;
            
            // Update colors based on performance
            updateKPIColors(kpis);
            
        } else {
            console.error('Failed to load KPIs:', data.message);
        }
    } catch (error) {
        console.error('Error loading KPIs:', error);
    }
}

// Update KPI colors based on performance thresholds
function updateKPIColors(kpis) {
    // Today's alerts change indicator
    const changeElement = document.getElementById('todayAlertsChange');
    if (kpis.today_alerts_change > 0) {
        changeElement.className = 'text-warning';
    } else if (kpis.today_alerts_change < 0) {
        changeElement.className = 'text-success';
    } else {
        changeElement.className = 'text-muted';
    }
    
    // Unassigned percentage warning
    const unassignedElement = document.getElementById('unassignedPercentage');
    if (kpis.unassigned_percentage > 20) {
        unassignedElement.className = 'text-danger';
    } else if (kpis.unassigned_percentage > 10) {
        unassignedElement.className = 'text-warning';
    } else {
        unassignedElement.className = 'text-success';
    }
    
    // Resolution rate indicator
    const resolutionElement = document.getElementById('resolutionRate');
    if (kpis.resolution_rate >= 80) {
        resolutionElement.className = 'text-success';
    } else if (kpis.resolution_rate >= 60) {
        resolutionElement.className = 'text-warning';
    } else {
        resolutionElement.className = 'text-danger';
    }
    
    // Critical alerts percentage
    const criticalElement = document.getElementById('criticalPercentage');
    if (kpis.critical_percentage > 15) {
        criticalElement.className = 'text-danger';
    } else if (kpis.critical_percentage > 5) {
        criticalElement.className = 'text-warning';
    } else {
        criticalElement.className = 'text-success';
    }
    
    // Response time indicator (target is 15 minutes)
    const responseElement = document.getElementById('avgResponseTime');
    if (kpis.avg_response_time <= 15) {
        responseElement.className = 'fw-extrabold mb-0 text-success';
    } else if (kpis.avg_response_time <= 30) {
        responseElement.className = 'fw-extrabold mb-0 text-warning';
    } else {
        responseElement.className = 'fw-extrabold mb-0 text-danger';
    }
}

// Helper function to truncate text
function truncateText(text, maxLength) {
    if (text.length > maxLength) {
        return text.slice(0, maxLength) + '...';
    }
    return text;
} 