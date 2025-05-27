// DOT Infractions Management JavaScript

let currentInfractionId = null;
let selectedAlertId = null;
let currentCompanyDrivers = [];
let currentCompanyVehicles = [];
let selectedVehicleIds = [];

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    loadCompanies();
    loadInfractions();
    
    // Set up form submission
    document.getElementById('infractionForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const data = {};
        
        // Basic form fields
        for (let [key, value] of formData.entries()) {
            if (key.endsWith('[]')) {
                const arrayKey = key.slice(0, -2);
                if (!data[arrayKey]) data[arrayKey] = [];
                data[arrayKey].push(value);
            } else {
                data[key] = value;
            }
        }
        
        // Add selected vehicle IDs
        data.linked_vehicles = selectedVehicleIds;
        
        // Process manual vehicle data
        if (data.vehicle_unit) {
            data.vehicles_data = [];
            for (let i = 0; i < data.vehicle_unit.length; i++) {
                if (data.vehicle_unit[i] || data.vehicle_type[i]) {
                    data.vehicles_data.push({
                        unit: data.vehicle_unit[i],
                        type: data.vehicle_type[i],
                        year: data.vehicle_year[i],
                        make: data.vehicle_make[i],
                        state: data.vehicle_state[i],
                        license: data.vehicle_license[i]
                    });
                }
            }
            // Remove array fields
            delete data.vehicle_unit;
            delete data.vehicle_type;
            delete data.vehicle_year;
            delete data.vehicle_make;
            delete data.vehicle_state;
            delete data.vehicle_license;
        }
        
        // Process violations data
        if (data.violation_section_code) {
            data.violations = [];
            for (let i = 0; i < data.violation_section_code.length; i++) {
                if (data.violation_section_code[i] && data.violation_description[i]) {
                    data.violations.push({
                        unit_type: data.violation_unit_type[i],
                        oos_indicator: data.violation_oos[i],
                        section_code: data.violation_section_code[i],
                        violation_description: data.violation_description[i],
                        violation_category: data.violation_category[i],
                        citation: data.violation_citation[i]
                    });
                }
            }
            // Remove array fields
            delete data.violation_unit_type;
            delete data.violation_oos;
            delete data.violation_section_code;
            delete data.violation_description;
            delete data.violation_category;
            delete data.violation_citation;
        }
        
        try {
            const response = await fetch('/dot-infractions/api/infractions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showAlert('Infraction created successfully', 'success');
                hideCreateForm();
                loadInfractions();
            } else {
                showAlert(result.message || 'Error creating infraction', 'danger');
            }
        } catch (error) {
            console.error('Error:', error);
            showAlert('Error creating infraction', 'danger');
        }
    });
    
    // Set up search functionality
    document.getElementById('searchInfractions').addEventListener('input', debounce(loadInfractions, 300));
    document.getElementById('dateFrom').addEventListener('change', loadInfractions);
    document.getElementById('dateTo').addEventListener('change', loadInfractions);
    
    // Set up alert search
    document.getElementById('alertSearch').addEventListener('input', debounce(searchAlerts, 300));
});

// Debounce function
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

// Show/hide create form
function showCreateForm() {
    document.getElementById('infractionFormContainer').style.display = 'block';
    document.getElementById('formTitle').textContent = 'Add New DOT Infraction';
    document.getElementById('infractionForm').reset();
    currentInfractionId = null;
}

function hideCreateForm() {
    document.getElementById('infractionFormContainer').style.display = 'none';
    document.getElementById('infractionForm').reset();
    currentInfractionId = null;
}

// Load infractions list
async function loadInfractions(page = 1) {
    try {
        const search = document.getElementById('searchInfractions').value;
        const dateFrom = document.getElementById('dateFrom').value;
        const dateTo = document.getElementById('dateTo').value;
        
        let url = `/dot-infractions/api/infractions?page=${page}&per_page=20`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (dateFrom) url += `&date_from=${dateFrom}`;
        if (dateTo) url += `&date_to=${dateTo}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderInfractions(data.infractions);
            updatePagination(data.current_page, data.pages, data.total, 'infractionsPagination');
        } else {
            showError('Failed to load infractions');
        }
    } catch (error) {
        console.error('Error loading infractions:', error);
        showError('Failed to load infractions');
    }
}

// Render infractions table
function renderInfractions(infractions) {
    const tbody = document.getElementById('infractionsTableBody');
    tbody.innerHTML = '';
    
    if (infractions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center">No infractions found</td></tr>';
        return;
    }
    
    infractions.forEach(infraction => {
        const row = document.createElement('tr');
        
        // Format severity summary
        let severityBadges = '';
        if (infraction.severity_summary) {
            Object.entries(infraction.severity_summary).forEach(([severity, count]) => {
                const badgeClass = getSeverityBadgeClass(severity);
                severityBadges += `<span class="badge bg-${badgeClass} severity-badge me-1">${severity}: ${count}</span>`;
            });
        }
        
        row.innerHTML = `
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="showInfractionDetails(${infraction.id})">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
            <td>${infraction.report_number}</td>
            <td>${formatDate(infraction.inspection_date)}</td>
            <td>${infraction.carrier_name || 'N/A'}</td>
            <td>${infraction.us_dot || 'N/A'}</td>
            <td>${infraction.driver_name || 'N/A'}</td>
            <td>${infraction.inspection_location || 'N/A'}</td>
            <td>
                <span class="badge bg-primary">${infraction.violation_count}</span>
                <div class="mt-1">${severityBadges}</div>
            </td>
            <td>
                <span class="badge bg-info">${infraction.linked_alerts_count}</span>
            </td>
            <td>${infraction.created_by}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// Show infraction details modal
async function showInfractionDetails(infractionId) {
    try {
        currentInfractionId = infractionId;
        
        const response = await fetch(`/dot-infractions/api/infractions/${infractionId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderInfractionDetails(data.infraction);
            
            const modal = new bootstrap.Modal(document.getElementById('infractionDetailsModal'));
            modal.show();
        } else {
            showError('Failed to load infraction details');
        }
    } catch (error) {
        console.error('Error loading infraction details:', error);
        showError('Failed to load infraction details');
    }
}

// Render infraction details
function renderInfractionDetails(infraction) {
    const container = document.getElementById('infractionDetailsContent');
    
    // Format vehicles
    let vehiclesHtml = '';
    if (infraction.vehicles_data && infraction.vehicles_data.length > 0) {
        vehiclesHtml = infraction.vehicles_data.map(vehicle => `
            <div class="row mb-2">
                <div class="col-md-2"><strong>Unit ${vehicle.unit}:</strong></div>
                <div class="col-md-10">${vehicle.type} - ${vehicle.year} ${vehicle.make} (${vehicle.state} ${vehicle.license})</div>
            </div>
        `).join('');
    } else {
        vehiclesHtml = '<p class="text-muted">No vehicle information available</p>';
    }
    
    // Format violations
    let violationsHtml = '';
    if (infraction.violations && infraction.violations.length > 0) {
        violationsHtml = infraction.violations.map(violation => `
            <div class="violation-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${violation.section_code}</strong>
                        ${violation.oos_indicator === 'Y' ? '<span class="badge bg-danger ms-2">OOS</span>' : ''}
                        ${violation.violation_category ? `<span class="badge bg-secondary ms-1">${violation.violation_category}</span>` : ''}
                    </div>
                    <small class="text-muted">Unit: ${violation.unit_type || 'N/A'}</small>
                </div>
                <p class="mb-1 mt-2">${violation.violation_description}</p>
                ${violation.citation ? `<small class="text-muted">Citation: ${violation.citation}</small>` : ''}
            </div>
        `).join('');
    } else {
        violationsHtml = '<p class="text-muted">No violations recorded</p>';
    }
    
    container.innerHTML = `
        <div class="row mb-4">
            <div class="col-md-6">
                <h6>Carrier Information</h6>
                <p><strong>Name:</strong> ${infraction.carrier_name || 'N/A'}</p>
                <p><strong>Address:</strong> ${infraction.carrier_address || 'N/A'}</p>
                <p><strong>US DOT:</strong> ${infraction.us_dot || 'N/A'}</p>
                <p><strong>MC Number:</strong> ${infraction.mc_number || 'N/A'}</p>
            </div>
            <div class="col-md-6">
                <h6>Inspection Information</h6>
                <p><strong>Report #:</strong> ${infraction.report_number}</p>
                <p><strong>Date:</strong> ${formatDate(infraction.inspection_date)}</p>
                <p><strong>Location:</strong> ${infraction.inspection_location || 'N/A'}</p>
                <p><strong>Level:</strong> ${infraction.inspection_level || 'N/A'}</p>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6">
                <h6>Driver Information</h6>
                <p><strong>Name:</strong> ${infraction.driver_name || 'N/A'}</p>
                <p><strong>Age:</strong> ${infraction.driver_age || 'N/A'}</p>
                <p><strong>License State:</strong> ${infraction.driver_license_state || 'N/A'}</p>
            </div>
        </div>
        
        <div class="mb-4">
            <h6>Vehicle Information</h6>
            ${vehiclesHtml}
        </div>
        
        <div class="mb-4">
            <h6>Violations</h6>
            ${violationsHtml}
        </div>
    `;
    
    // Render linked alerts
    renderLinkedAlerts(infraction.linked_alerts);
}

// Render linked alerts
function renderLinkedAlerts(linkedAlerts) {
    const container = document.getElementById('linkedAlertsContainer');
    
    if (linkedAlerts.length === 0) {
        container.innerHTML = '<p class="text-muted">No alerts linked to this infraction</p>';
        return;
    }
    
    container.innerHTML = linkedAlerts.map(link => `
        <div class="linked-alert">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${link.alert_type}</strong>
                    <br>
                    <small class="text-muted">Vehicle: ${link.vehicle_name}</small>
                    <br>
                    <small class="text-muted">${formatDateTime(link.alert_timestamp)}</small>
                </div>
                <button class="btn btn-sm btn-outline-danger" onclick="unlinkAlert(${link.id})">
                    <i class="fas fa-unlink"></i>
                </button>
            </div>
            ${link.link_reason ? `<p class="mb-0 mt-2"><small><strong>Reason:</strong> ${link.link_reason}</small></p>` : ''}
            <small class="text-muted">Linked by ${link.linked_by} on ${formatDateTime(link.linked_at)}</small>
        </div>
    `).join('');
}

// Search alerts for linking
async function searchAlerts() {
    const search = document.getElementById('alertSearch').value;
    
    if (search.length < 2) {
        document.getElementById('alertSearchResults').innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`/dot-infractions/api/search-alerts?search=${encodeURIComponent(search)}&limit=5`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderAlertSearchResults(data.alerts);
        }
    } catch (error) {
        console.error('Error searching alerts:', error);
    }
}

// Render alert search results
function renderAlertSearchResults(alerts) {
    const container = document.getElementById('alertSearchResults');
    
    if (alerts.length === 0) {
        container.innerHTML = '<p class="text-muted small">No alerts found</p>';
        return;
    }
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-search-result p-2 border rounded mb-1 cursor-pointer" onclick="selectAlert(${alert.id})" style="cursor: pointer;">
            <div class="d-flex justify-content-between">
                <div>
                    <strong>${alert.alert_type}</strong>
                    <br>
                    <small class="text-muted">${alert.vehicle_name} - ${alert.client_name}</small>
                </div>
                <small class="text-muted">${formatDateTime(alert.timestamp)}</small>
            </div>
        </div>
    `).join('');
}

// Select alert for linking
function selectAlert(alertId) {
    selectedAlertId = alertId;
    
    // Highlight selected alert
    document.querySelectorAll('.alert-search-result').forEach(el => {
        el.classList.remove('bg-primary', 'text-white');
    });
    
    event.target.closest('.alert-search-result').classList.add('bg-primary', 'text-white');
}

// Link selected alert to infraction
async function linkSelectedAlert() {
    if (!selectedAlertId) {
        showError('Please select an alert to link');
        return;
    }
    
    if (!currentInfractionId) {
        showError('No infraction selected');
        return;
    }
    
    const linkReason = document.getElementById('linkReason').value.trim();
    
    try {
        const response = await fetch(`/dot-infractions/api/infractions/${currentInfractionId}/link-alert`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            },
            body: JSON.stringify({
                alert_id: selectedAlertId,
                link_reason: linkReason
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showSuccess('Alert linked successfully');
            
            // Clear form
            document.getElementById('alertSearch').value = '';
            document.getElementById('linkReason').value = '';
            document.getElementById('alertSearchResults').innerHTML = '';
            selectedAlertId = null;
            
            // Refresh infraction details
            showInfractionDetails(currentInfractionId);
        } else {
            showError(data.message || 'Failed to link alert');
        }
    } catch (error) {
        console.error('Error linking alert:', error);
        showError('Failed to link alert');
    }
}

// Vehicle management functions
function addVehicle() {
    const container = document.getElementById('vehiclesContainer');
    const vehicleEntry = container.querySelector('.vehicle-entry').cloneNode(true);
    
    // Clear values
    vehicleEntry.querySelectorAll('input, select').forEach(input => {
        input.value = '';
    });
    
    container.appendChild(vehicleEntry);
}

function removeVehicle(button) {
    const container = document.getElementById('vehiclesContainer');
    if (container.children.length > 1) {
        button.closest('.vehicle-entry').remove();
    }
}

// Violation management functions
function addViolation() {
    const container = document.getElementById('violationsContainer');
    const violationEntry = container.querySelector('.violation-entry').cloneNode(true);
    
    // Clear values
    violationEntry.querySelectorAll('input, select, textarea').forEach(input => {
        input.value = '';
    });
    
    container.appendChild(violationEntry);
}

function removeViolation(button) {
    const container = document.getElementById('violationsContainer');
    if (container.children.length > 1) {
        button.closest('.violation-entry').remove();
    }
}

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
}

function getSeverityBadgeClass(severity) {
    const classes = {
        'BASIC': 'warning',
        'Weight': 'info',
        'Citation': 'danger',
        'Emergency Equipment': 'secondary',
        'Speeding': 'danger'
    };
    return classes[severity] || 'secondary';
}

function updatePagination(currentPage, totalPages, totalItems, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = '<ul class="pagination justify-content-center">';
    
    // Previous button
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadInfractions(${currentPage - 1}); return false;">Previous</a>
        </li>
    `;
    
    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        html += `
            <li class="page-item ${currentPage === i ? 'active' : ''}">
                <a class="page-link" href="#" onclick="loadInfractions(${i}); return false;">${i}</a>
            </li>
        `;
    }
    
    // Next button
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadInfractions(${currentPage + 1}); return false;">Next</a>
        </li>
    `;
    
    html += '</ul>';
    html += `<div class="text-center mt-2">Total items: ${totalItems}</div>`;
    
    container.innerHTML = html;
}

// Toast notifications (you can replace with your preferred notification system)
function showSuccess(message) {
    alert('Success: ' + message);
}

function showError(message) {
    alert('Error: ' + message);
}

// Load companies for dropdown
async function loadCompanies() {
    try {
        const response = await fetch('/dot-infractions/api/companies');
        const data = await response.json();
        
        if (data.status === 'success') {
            const companySelect = document.getElementById('companySelect');
            companySelect.innerHTML = '<option value="">Choose a company...</option>';
            
            data.companies.forEach(company => {
                const option = document.createElement('option');
                option.value = company.id;
                option.textContent = `${company.name} (${company.driver_count} drivers, ${company.vehicle_count} vehicles)`;
                companySelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading companies:', error);
        showAlert('Error loading companies', 'danger');
    }
}

// Load company data when company is selected
async function loadCompanyData() {
    const companyId = document.getElementById('companySelect').value;
    
    if (!companyId) {
        // Reset everything
        currentCompanyDrivers = [];
        currentCompanyVehicles = [];
        selectedVehicleIds = [];
        document.getElementById('driverCount').textContent = '-';
        document.getElementById('vehicleCount').textContent = '-';
        document.getElementById('primaryDriverSelect').innerHTML = '<option value="">Select from existing drivers...</option>';
        document.getElementById('linkedVehiclesContainer').innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Select a company first to see available vehicles
            </div>
        `;
        return;
    }
    
    try {
        // Load drivers and vehicles in parallel
        const [driversResponse, vehiclesResponse] = await Promise.all([
            fetch(`/dot-infractions/api/companies/${companyId}/drivers`),
            fetch(`/dot-infractions/api/companies/${companyId}/vehicles`)
        ]);
        
        const driversData = await driversResponse.json();
        const vehiclesData = await vehiclesResponse.json();
        
        if (driversData.status === 'success') {
            currentCompanyDrivers = driversData.drivers;
            updateDriverDropdown();
            document.getElementById('driverCount').textContent = driversData.drivers.length;
        }
        
        if (vehiclesData.status === 'success') {
            currentCompanyVehicles = vehiclesData.vehicles;
            updateVehicleSelection();
            document.getElementById('vehicleCount').textContent = vehiclesData.vehicles.length;
        }
        
    } catch (error) {
        console.error('Error loading company data:', error);
        showAlert('Error loading company data', 'danger');
    }
}

// Update driver dropdown
function updateDriverDropdown() {
    const driverSelect = document.getElementById('primaryDriverSelect');
    driverSelect.innerHTML = '<option value="">Select from existing drivers...</option>';
    
    currentCompanyDrivers.forEach(driver => {
        const option = document.createElement('option');
        option.value = driver.id;
        option.textContent = driver.display_name;
        option.dataset.driverData = JSON.stringify(driver);
        driverSelect.appendChild(option);
    });
}

// Update vehicle selection interface
function updateVehicleSelection() {
    const container = document.getElementById('linkedVehiclesContainer');
    
    if (currentCompanyVehicles.length === 0) {
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                No vehicles found for this company
            </div>
        `;
        return;
    }
    
    let html = '<div class="row">';
    currentCompanyVehicles.forEach(vehicle => {
        html += `
            <div class="col-md-6 mb-2">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${vehicle.id}" 
                           id="vehicle_${vehicle.id}" onchange="toggleVehicleSelection(${vehicle.id})">
                    <label class="form-check-label" for="vehicle_${vehicle.id}">
                        <strong>${vehicle.name}</strong>
                        <br><small class="text-muted">
                            ${vehicle.year || ''} ${vehicle.make || ''} ${vehicle.model || ''}
                            ${vehicle.license_plate ? '• ' + vehicle.license_plate : ''}
                            ${vehicle.vin ? '• VIN: ' + vehicle.vin.slice(-6) : ''}
                        </small>
                    </label>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

// Toggle vehicle selection
function toggleVehicleSelection(vehicleId) {
    const checkbox = document.getElementById(`vehicle_${vehicleId}`);
    
    if (checkbox.checked) {
        if (!selectedVehicleIds.includes(vehicleId)) {
            selectedVehicleIds.push(vehicleId);
        }
    } else {
        selectedVehicleIds = selectedVehicleIds.filter(id => id !== vehicleId);
    }
}

// Handle driver selection
function handleDriverSelection() {
    const driverSelect = document.getElementById('primaryDriverSelect');
    const selectedOption = driverSelect.options[driverSelect.selectedIndex];
    
    if (selectedOption.dataset.driverData) {
        const driverData = JSON.parse(selectedOption.dataset.driverData);
        
        // Auto-fill manual fields if they're visible
        if (document.getElementById('manualDriverFields').style.display !== 'none') {
            document.getElementById('driverName').value = driverData.name || '';
            document.getElementById('driverLicenseState').value = driverData.license_state || '';
        }
        
        // Disable manual entry checkbox when driver is selected
        document.getElementById('manualDriverEntry').checked = false;
        document.getElementById('manualDriverFields').style.display = 'none';
    }
}

// Toggle manual driver entry
function toggleManualDriverEntry() {
    const checkbox = document.getElementById('manualDriverEntry');
    const manualFields = document.getElementById('manualDriverFields');
    const driverSelect = document.getElementById('primaryDriverSelect');
    
    if (checkbox.checked) {
        manualFields.style.display = 'block';
        driverSelect.value = ''; // Clear driver selection
    } else {
        manualFields.style.display = 'none';
        // Clear manual fields
        document.getElementById('driverName').value = '';
        document.getElementById('driverAge').value = '';
        document.getElementById('driverLicenseState').value = '';
    }
}

// Toggle manual vehicles section
function toggleManualVehicles() {
    const checkbox = document.getElementById('enableManualVehicles');
    const manualSection = document.getElementById('manualVehiclesSection');
    
    manualSection.style.display = checkbox.checked ? 'block' : 'none';
} 