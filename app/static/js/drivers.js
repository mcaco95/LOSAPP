// Driver Management JavaScript

let currentPage = 1;
let currentFilters = {};
let currentDriverId = null;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    loadCompanies();
    loadDrivers();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('searchDrivers');
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 1;
            loadDrivers();
        }, 500);
    });

    // Filter dropdowns
    ['companyFilter', 'statusFilter', 'sortBy', 'sortOrder'].forEach(id => {
        document.getElementById(id).addEventListener('change', function() {
            currentPage = 1;
            loadDrivers();
        });
    });
}

// Load companies for filter dropdown
async function loadCompanies() {
    try {
        const response = await fetch('/drivers/api/companies');
        const data = await response.json();
        
        if (data.status === 'success') {
            const companySelect = document.getElementById('companyFilter');
            companySelect.innerHTML = '<option value="">All Companies</option>';
            
            data.companies.forEach(company => {
                const option = document.createElement('option');
                option.value = company.id;
                option.textContent = `${company.name} (${company.driver_count} drivers)`;
                companySelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading companies:', error);
    }
}

// Load drivers with current filters
async function loadDrivers() {
    showLoading(true);
    
    try {
        // Build query parameters
        const params = new URLSearchParams({
            page: currentPage,
            per_page: 20,
            search: document.getElementById('searchDrivers').value,
            company_id: document.getElementById('companyFilter').value,
            status: document.getElementById('statusFilter').value,
            sort_by: document.getElementById('sortBy').value,
            sort_order: document.getElementById('sortOrder').value
        });

        // Remove empty parameters
        for (let [key, value] of [...params.entries()]) {
            if (!value) params.delete(key);
        }

        const response = await fetch(`/drivers/api/drivers?${params}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderDrivers(data.drivers);
            renderPagination(data.current_page, data.pages, data.total);
            updateDriversCount(data.total);
        } else {
            showError('Failed to load drivers');
        }
    } catch (error) {
        console.error('Error loading drivers:', error);
        showError('Failed to load drivers');
    } finally {
        showLoading(false);
    }
}

// Render drivers table
function renderDrivers(drivers) {
    const tbody = document.getElementById('driversTableBody');
    const emptyState = document.getElementById('driversEmpty');
    
    if (!drivers || drivers.length === 0) {
        tbody.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    tbody.innerHTML = drivers.map(driver => {
        const avatarColor = getAvatarColor(driver.name);
        const statusClass = driver.is_active ? 'driver-status-active' : 'driver-status-inactive';
        const statusIcon = driver.is_active ? 'fa-check-circle' : 'fa-times-circle';
        
        return `
            <tr class="driver-row" onclick="showDriverDetails(${driver.id})">
                <td>
                    <div class="d-flex align-items-center">
                        <div class="driver-avatar" style="background-color: ${avatarColor};">
                            ${(driver.name || 'D')[0].toUpperCase()}
                        </div>
                        <div>
                            <div class="fw-bold">${driver.name || 'Unknown Driver'}</div>
                            <small class="text-muted">
                                ID: ${driver.driver_id}
                                ${driver.username ? ` • @${driver.username}` : ''}
                            </small>
                        </div>
                    </div>
                </td>
                <td>
                    <i class="fas ${statusIcon} ${statusClass} me-1"></i>
                    <span class="${statusClass}">${driver.is_active ? 'Active' : 'Inactive'}</span>
                </td>
                <td>
                    <div>
                        ${driver.phone ? `<div><i class="fas fa-phone me-1"></i>${driver.phone}</div>` : ''}
                        ${driver.email ? `<div class="text-muted small"><i class="fas fa-envelope me-1"></i>${driver.email}</div>` : ''}
                        ${!driver.phone && !driver.email ? '<span class="text-muted">No contact info</span>' : ''}
                    </div>
                </td>
                <td>
                    <div>
                        ${driver.license_number ? `<div>${driver.license_number}</div>` : ''}
                        ${driver.license_state ? `<small class="text-muted">${driver.license_state}${driver.license_class ? ` • ${driver.license_class}` : ''}</small>` : ''}
                        ${!driver.license_number && !driver.license_state ? '<span class="text-muted">N/A</span>' : ''}
                    </div>
                </td>
                <td>
                    <span class="badge bg-light text-dark">
                        <i class="fas fa-building me-1"></i>
                        ${driver.company_name}
                    </span>
                </td>
                <td>
                    <div class="alert-stats">
                        <span class="badge bg-primary">${driver.total_alerts}</span>
                        ${driver.recent_alerts > 0 ? `<span class="badge bg-warning">${driver.recent_alerts} recent</span>` : ''}
                    </div>
                </td>
                <td>
                    <small class="text-muted">
                        ${formatDate(driver.created_at)}
                    </small>
                </td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation(); showDriverDetails(${driver.id})">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="event.stopPropagation(); viewDriverPage(${driver.id})">
                            <i class="fas fa-external-link-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Show driver details in modal
async function showDriverDetails(driverId) {
    currentDriverId = driverId;
    
    try {
        const response = await fetch(`/drivers/api/drivers/${driverId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderDriverDetailsModal(data.driver);
            const modal = new bootstrap.Modal(document.getElementById('driverDetailsModal'));
            modal.show();
        } else {
            showError('Failed to load driver details');
        }
    } catch (error) {
        console.error('Error loading driver details:', error);
        showError('Failed to load driver details');
    }
}

// Render driver details in modal
function renderDriverDetailsModal(driver) {
    const container = document.getElementById('driverDetailsContent');
    const avatarColor = getAvatarColor(driver.name);
    
    container.innerHTML = `
        <div class="row">
            <!-- Driver Header -->
            <div class="col-12 mb-4">
                <div class="d-flex align-items-center p-3 bg-light rounded">
                    <div class="driver-avatar me-3" style="background-color: ${avatarColor}; width: 60px; height: 60px; font-size: 1.5rem;">
                        ${(driver.name || 'D')[0].toUpperCase()}
                    </div>
                    <div class="flex-grow-1">
                        <h4 class="mb-1">${driver.name || 'Unknown Driver'}</h4>
                        <p class="mb-1 text-muted">
                            <i class="fas fa-id-card me-2"></i>Driver ID: ${driver.driver_id}
                            ${driver.username ? ` • @${driver.username}` : ''}
                        </p>
                        <div class="d-flex gap-2">
                            <span class="badge ${driver.is_active ? 'bg-success' : 'bg-danger'}">
                                ${driver.is_active ? 'Active' : 'Inactive'}
                            </span>
                            ${driver.company ? `<span class="badge bg-light text-dark">${driver.company.name}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Statistics -->
            <div class="col-12 mb-4">
                <h6>Alert Statistics</h6>
                <div class="row g-2">
                    <div class="col-3">
                        <div class="text-center p-2 bg-primary text-white rounded">
                            <div class="h4 mb-0">${driver.alert_stats.total}</div>
                            <small>Total</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center p-2 bg-warning text-white rounded">
                            <div class="h4 mb-0">${driver.alert_stats.unassigned}</div>
                            <small>Unassigned</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center p-2 bg-info text-white rounded">
                            <div class="h4 mb-0">${driver.alert_stats.in_progress}</div>
                            <small>In Progress</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center p-2 bg-success text-white rounded">
                            <div class="h4 mb-0">${driver.alert_stats.resolved}</div>
                            <small>Resolved</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Driver Information -->
            <div class="col-md-6">
                <h6>Contact Information</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>Phone:</strong></td>
                        <td>${driver.phone || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>Email:</strong></td>
                        <td>${driver.email || 'N/A'}</td>
                    </tr>
                </table>
                
                <h6 class="mt-3">License Information</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>License Number:</strong></td>
                        <td>${driver.license_number || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>State:</strong></td>
                        <td>${driver.license_state || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>Class:</strong></td>
                        <td>${driver.license_class || 'N/A'}</td>
                    </tr>
                </table>
            </div>
            
            <!-- Recent Alerts -->
            <div class="col-md-6">
                <h6>Recent Alerts</h6>
                <div style="max-height: 300px; overflow-y: auto;">
                    ${driver.recent_alerts && driver.recent_alerts.length > 0 ? 
                        driver.recent_alerts.map(alert => `
                            <div class="border-start border-3 border-${getSeverityColor(alert.severity)} ps-3 mb-2">
                                <div class="d-flex justify-content-between">
                                    <strong>${alert.alert_type}</strong>
                                    <span class="badge bg-${getSeverityColor(alert.severity)}">${alert.severity}</span>
                                </div>
                                <div class="text-muted small">${alert.vehicle_name}</div>
                                <div class="text-muted small">${formatDateTime(alert.timestamp)}</div>
                            </div>
                        `).join('') : 
                        '<div class="text-muted text-center py-3">No recent alerts</div>'
                    }
                </div>
            </div>
        </div>
    `;
}

// Navigate to driver details page
function viewDriverPage(driverId = null) {
    const id = driverId || currentDriverId;
    if (id) {
        window.open(`/drivers/${id}`, '_blank');
    }
}

// Render pagination
function renderPagination(currentPage, totalPages, totalItems) {
    const paginationHtml = generatePaginationHtml(currentPage, totalPages, totalItems, 'loadPage');
    document.getElementById('driversPaginationTop').innerHTML = paginationHtml;
    document.getElementById('driversPaginationBottom').innerHTML = paginationHtml;
}

// Load specific page
function loadPage(page) {
    currentPage = page;
    loadDrivers();
}

// Update drivers count display
function updateDriversCount(total) {
    document.getElementById('driversCount').textContent = `${total} driver${total !== 1 ? 's' : ''} found`;
}

// Show/hide loading state
function showLoading(show) {
    const loading = document.getElementById('driversLoading');
    const table = document.getElementById('driversTable');
    
    if (show) {
        loading.style.display = 'block';
        table.style.opacity = '0.5';
    } else {
        loading.style.display = 'none';
        table.style.opacity = '1';
    }
}

// Refresh drivers
function refreshDrivers() {
    loadDrivers();
}

// Utility functions
function getAvatarColor(name) {
    const colors = [
        '#007bff', '#6f42c1', '#e83e8c', '#dc3545', '#fd7e14',
        '#ffc107', '#28a745', '#20c997', '#17a2b8', '#6c757d'
    ];
    const index = (name || '').charCodeAt(0) % colors.length;
    return colors[index];
}

function getSeverityColor(severity) {
    const colors = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'success'
    };
    return colors[severity] || 'secondary';
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
}

function showError(message) {
    // You can implement a toast notification here
    console.error(message);
    alert('Error: ' + message);
}

// Generate pagination HTML (reusable function)
function generatePaginationHtml(currentPage, totalPages, totalItems, onClickFunction) {
    if (totalPages <= 1) return '';
    
    let html = '<nav><ul class="pagination pagination-sm justify-content-center mb-0">';
    
    // Previous button
    html += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" onclick="${onClickFunction}(${currentPage - 1}); return false;">Previous</a>
    </li>`;
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        html += `<li class="page-item"><a class="page-link" href="#" onclick="${onClickFunction}(1); return false;">1</a></li>`;
        if (startPage > 2) {
            html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
            <a class="page-link" href="#" onclick="${onClickFunction}(${i}); return false;">${i}</a>
        </li>`;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
        html += `<li class="page-item"><a class="page-link" href="#" onclick="${onClickFunction}(${totalPages}); return false;">${totalPages}</a></li>`;
    }
    
    // Next button
    html += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
        <a class="page-link" href="#" onclick="${onClickFunction}(${currentPage + 1}); return false;">Next</a>
    </li>`;
    
    html += '</ul></nav>';
    
    // Add items info
    const startItem = (currentPage - 1) * 20 + 1;
    const endItem = Math.min(currentPage * 20, totalItems);
    html += `<div class="text-center text-muted mt-2 small">
        Showing ${startItem}-${endItem} of ${totalItems} drivers
    </div>`;
    
    return html;
} 