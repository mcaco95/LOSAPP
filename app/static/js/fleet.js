// Initialize components
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    loadFleetData();
    
    // Set up event listeners
    document.getElementById('refreshFleet').addEventListener('click', loadFleetData);
    document.getElementById('syncFleet').addEventListener('click', syncFleetData);
    document.getElementById('driverSearch').addEventListener('input', debounce(filterDrivers, 300));
    document.getElementById('vehicleSearch').addEventListener('input', debounce(filterVehicles, 300));
    document.getElementById('trailerSearch').addEventListener('input', debounce(filterTrailers, 300));
});

// Sync fleet data with Samsara API
async function syncFleetData() {
    const syncButton = document.getElementById('syncFleet');
    const originalText = syncButton.innerHTML;
    
    try {
        // Show loading state
        syncButton.disabled = true;
        syncButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
        
        // Hide any existing alerts
        hideSyncAlert();
        
        const response = await fetch(`/samsara/fleet/sync/${clientId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Show success message with sync stats
            const stats = data.sync_stats;
            const message = `
                <strong>Sync completed successfully!</strong><br>
                <small>
                    Drivers: ${stats.drivers.created} created, ${stats.drivers.updated} updated (${stats.drivers.total_synced} total)<br>
                    Vehicles: ${stats.vehicles.created} created, ${stats.vehicles.updated} updated (${stats.vehicles.total_synced} total)
                </small>
            `;
            showSyncAlert(message, 'success');
            
            // Reload the fleet data to show updated information
            await loadFleetData();
        } else {
            throw new Error(data.message || 'Failed to sync fleet data');
        }
        
    } catch (error) {
        console.error('Error syncing fleet data:', error);
        showSyncAlert(`<strong>Sync failed:</strong> ${error.message}`, 'danger');
    } finally {
        // Restore button state
        syncButton.disabled = false;
        syncButton.innerHTML = originalText;
    }
}

// Show sync alert
function showSyncAlert(message, type = 'info') {
    const alertElement = document.getElementById('syncAlert');
    const contentElement = document.getElementById('syncAlertContent');
    
    // Set alert type and content
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    contentElement.innerHTML = message;
    
    // Show the alert
    alertElement.style.display = 'block';
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            hideSyncAlert();
        }, 5000);
    }
}

// Hide sync alert
function hideSyncAlert() {
    const alertElement = document.getElementById('syncAlert');
    alertElement.style.display = 'none';
    alertElement.className = 'alert alert-dismissible fade';
}

// Get CSRF token from meta tag or cookie
function getCSRFToken() {
    // Try to get from meta tag first
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    
    // Fallback to cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') {
            return decodeURIComponent(value);
        }
    }
    
    return '';
}

// Fetch functions for API calls
async function fetchDriverHosLogs(driverId, startTime = null, endTime = null) {
    try {
        let url = `/samsara/fleet/drivers/hos/${clientId}/${driverId}`;
        if (startTime || endTime) {
            const params = new URLSearchParams();
            if (startTime) params.append('start_time', startTime);
            if (endTime) params.append('end_time', endTime);
            url += `?${params.toString()}`;
        }
        const response = await fetch(url);
        const data = await response.json();
        return data.status === 'success' ? data.hos_logs : [];
    } catch (error) {
        console.error('Error fetching HOS logs:', error);
        return [];
    }
}

async function fetchDriverHosViolations(driverId, startTime = null, endTime = null) {
    try {
        let url = `/samsara/fleet/drivers/hos/violations/${clientId}/${driverId}`;
        if (startTime || endTime) {
            const params = new URLSearchParams();
            if (startTime) params.append('start_time', startTime);
            if (endTime) params.append('end_time', endTime);
            url += `?${params.toString()}`;
        }
        const response = await fetch(url);
        const data = await response.json();
        return data.status === 'success' ? data.violations : [];
    } catch (error) {
        console.error('Error fetching HOS violations:', error);
        return [];
    }
}

async function fetchDriverHosDailyLogs(driverId, startTime = null, endTime = null) {
    try {
        let url = `/samsara/fleet/drivers/hos/daily/${clientId}/${driverId}`;
        if (startTime || endTime) {
            const params = new URLSearchParams();
            
            // Ensure we're not sending future dates
            const now = new Date();
            
            if (startTime) {
                const startDate = new Date(startTime);
                if (startDate > now) {
                    startDate.setDate(now.getDate() - 7); // Default to 7 days ago if future date
                }
                params.append('start_time', startDate.toISOString());
            }
            
            if (endTime) {
                const endDate = new Date(endTime);
                if (endDate > now) {
                    endDate.setTime(now.getTime()); // Set to current time if future date
                }
                params.append('end_time', endDate.toISOString());
            }
            
            url += `?${params.toString()}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`Failed to fetch HOS daily logs: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        if (!data || data.length === 0) {
            console.log('No HOS data found for driver', driverId);
            return [];
        }
        
        return data;
    } catch (error) {
        console.error('Error fetching HOS daily logs:', error);
        throw error;
    }
}

async function fetchVehicleLocation(vehicleId) {
    try {
        const response = await fetch(`/samsara/fleet/vehicles/locations/${clientId}?vehicleId=${vehicleId}`);
        const data = await response.json();
        return data.status === 'success' ? data.locations : null;
    } catch (error) {
        console.error('Error fetching vehicle location:', error);
        return null;
    }
}

async function fetchVehicleStats(vehicleId) {
    try {
        const response = await fetch(`/samsara/fleet/vehicles/stats/${clientId}?vehicleId=${vehicleId}`);
        const data = await response.json();
        return data.status === 'success' ? data.stats[0] : null;
    } catch (error) {
        console.error('Error fetching vehicle stats:', error);
        return null;
    }
}

async function fetchTrailerLocation(trailerId) {
    try {
        const response = await fetch(`/samsara/fleet/trailers/locations/${clientId}?trailerId=${trailerId}`);
        const data = await response.json();
        return data.status === 'success' ? data.locations[0] : null;
    } catch (error) {
        console.error('Error fetching trailer location:', error);
        return null;
    }
}

// Use ModalUtils for showing modals
function showModal(content, options = {}) {
    return window.ModalUtils.showModal(content, options);
}

// Debounce function for search inputs
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

// Load all fleet data
async function loadFleetData() {
    try {
        // Show loading state
        document.getElementById('totalDrivers').textContent = '...';
        document.getElementById('totalVehicles').textContent = '...';
        document.getElementById('totalTrailers').textContent = '...';
        
        // Load data in parallel
        const [drivers, vehicles, trailers] = await Promise.all([
            loadDrivers(),
            loadVehicles(),
            loadTrailers()
        ]);
        
        // Update counters
        document.getElementById('totalDrivers').textContent = drivers.length;
        document.getElementById('totalVehicles').textContent = vehicles.length;
        document.getElementById('totalTrailers').textContent = trailers.length;
        
    } catch (error) {
        console.error('Error loading fleet data:', error);
        showError('Failed to load fleet data');
    }
}

// Load and render drivers
async function loadDrivers() {
    try {
        const response = await fetch(`/samsara/fleet/drivers/${clientId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('First driver data:', data.drivers[0]);
            renderDrivers(data.drivers);
            
            // Show sync stats if available
            if (data.sync_stats) {
                const stats = data.sync_stats;
                if (stats.created > 0 || stats.updated > 0) {
                    console.log(`Driver sync: ${stats.created} created, ${stats.updated} updated, ${stats.total_synced} total`);
                }
            }
            
            return data.drivers;
        } else {
            throw new Error(data.message || 'Failed to load drivers');
        }
    } catch (error) {
        console.error('Error loading drivers:', error);
        showError('Failed to load drivers');
        return [];
    }
}

// Load and render vehicles
async function loadVehicles() {
    try {
        const response = await fetch(`/samsara/fleet/vehicles/${clientId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('First vehicle data:', data.vehicles[0]);
            renderVehicles(data.vehicles);
            
            // Show sync stats if available
            if (data.sync_stats) {
                const stats = data.sync_stats;
                if (stats.created > 0 || stats.updated > 0) {
                    console.log(`Vehicle sync: ${stats.created} created, ${stats.updated} updated, ${stats.total_synced} total`);
                }
            }
            
            return data.vehicles;
        } else {
            throw new Error(data.message || 'Failed to load vehicles');
        }
    } catch (error) {
        console.error('Error loading vehicles:', error);
        showError('Failed to load vehicles');
        return [];
    }
}

// Load and render trailers
async function loadTrailers() {
    try {
        const response = await fetch(`/samsara/fleet/trailers/${clientId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('First trailer data:', data.trailers[0]);
            renderTrailers(data.trailers);
            return data.trailers;
        } else {
            throw new Error(data.message || 'Failed to load trailers');
        }
    } catch (error) {
        console.error('Error loading trailers:', error);
        showError('Failed to load trailers');
        return [];
    }
}

// Render drivers table
function renderDrivers(drivers) {
    const tbody = document.querySelector('#driversTable tbody');
    tbody.innerHTML = '';
    
    if (drivers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No drivers found</td></tr>';
        return;
    }
    
    drivers.forEach(driver => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-driver-id', driver.id);
        tr.setAttribute('data-driver', JSON.stringify(driver));
        
        // Create a clean ELD status display
        const eldStatus = [];
        if (driver.eldAdverseWeatherExemptionEnabled) eldStatus.push('Weather Exempt');
        if (driver.eldPcEnabled) eldStatus.push('PC Enabled');
        if (driver.eldYmEnabled) eldStatus.push('YM Enabled');
        
        // Format the carrier settings
        const carrierInfo = driver.carrierSettings || {};
        const carrierDetails = [
            carrierInfo.carrierName,
            carrierInfo.dotNumber ? `DOT: ${carrierInfo.dotNumber}` : null,
            carrierInfo.mainOfficeAddress
        ].filter(Boolean).join(' • ');

        tr.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <div class="avatar avatar-sm rounded-circle bg-primary text-white me-2">
                        ${driver.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <span class="d-block fw-bold">${driver.name}</span>
                        <small class="text-muted">
                            ${driver.username ? `@${driver.username}` : 'No username'} • 
                            ${driver.timezone || 'No timezone'}
                        </small>
                    </div>
                </div>
            </td>
            <td>
                <span class="badge bg-${getStatusClass(driver.driverActivationStatus)}">
                    ${driver.driverActivationStatus || 'Unknown'}
                </span>
                ${eldStatus.map(status => 
                    `<span class="badge bg-info ms-1">${status}</span>`
                ).join('')}
            </td>
            <td>
                <div class="d-flex flex-column">
                    <span>${driver.phone || 'N/A'}</span>
                    <small class="text-muted">${carrierDetails || 'No carrier info'}</small>
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    ${driver.eldSettings?.rulesets?.map(ruleset => `
                        <span class="badge bg-light text-dark mb-1">
                            ${ruleset.cycle}
                        </span>
                        <small class="text-muted d-block">
                            ${ruleset.shift} • ${ruleset.restart}
                        </small>
                    `).join('') || 'No ELD settings'}
                </div>
            </td>
            <td>
                ${driver.tags?.map(tag => `
                    <span class="badge bg-secondary me-1">
                        ${tag.name}
                    </span>
                `).join('') || 'No tags'}
            </td>
            <td class="text-end">
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="showDriverDetails('${driver.id}')">
                        <i class="fas fa-eye me-1"></i> View
                </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="showDriverHOS('${driver.id}')">
                        <i class="fas fa-clock me-1"></i> HOS
                </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Render vehicles table
function renderVehicles(vehicles) {
    const tbody = document.querySelector('#vehiclesTable tbody');
    tbody.innerHTML = '';
    
    if (vehicles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No vehicles found</td></tr>';
        return;
    }
    
    vehicles.forEach(vehicle => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-vehicle-id', vehicle.id);
        tr.setAttribute('data-vehicle', JSON.stringify(vehicle));
        
        // Format vehicle name and details
        const vehicleDetails = [
            vehicle.year,
            vehicle.make,
            vehicle.model
        ].filter(Boolean).join(' ');
        
        tr.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <div class="avatar avatar-sm rounded-circle bg-success text-white me-2">
                        <i class="fas fa-truck"></i>
                    </div>
                    <div>
                        <span class="d-block fw-bold">${vehicle.name || 'Unnamed Vehicle'}</span>
                        <small class="text-muted">${vehicleDetails || 'No details available'}</small>
                    </div>
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    <span class="badge bg-${getStatusClass(vehicle.vehicleRegulationMode)}">
                        ${formatRegulationMode(vehicle.vehicleRegulationMode)}
                    </span>
                    ${vehicle.harshAccelerationSettingType ? 
                        `<small class="text-muted mt-1">
                            <i class="fas fa-tachometer-alt me-1"></i>
                            ${formatSettingType(vehicle.harshAccelerationSettingType)}
                        </small>` : ''
                    }
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    <span class="text-primary">${vehicle.vin || 'N/A'}</span>
                    <small class="text-muted">
                        <i class="fas fa-hashtag me-1"></i>
                        ${vehicle.licensePlate || 'No plate'}
                    </small>
                </div>
            </td>
            <td>
                ${vehicle.tags?.map(tag => `
                    <span class="badge bg-secondary me-1">
                        ${tag.name}
                    </span>
                `).join('') || 'No tags'}
            </td>
            <td>
                <div class="d-flex flex-column">
                    <small class="text-muted">Created: ${formatDateTime(vehicle.createdAtTime)}</small>
                    <small class="text-muted">Updated: ${formatDateTime(vehicle.updatedAtTime)}</small>
                </div>
            </td>
            <td class="text-end">
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="showVehicleDetails('${vehicle.id}')">
                        <i class="fas fa-eye me-1"></i> View
                </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="showVehicleStats('${vehicle.id}')">
                        <i class="fas fa-chart-line me-1"></i> Stats
                    </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="showVehicleLocation('${vehicle.id}')">
                        <i class="fas fa-map-marker-alt me-1"></i> Location
                </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Render trailers table
function renderTrailers(trailers) {
    const tbody = document.querySelector('#trailersTable tbody');
    tbody.innerHTML = '';
    
    if (trailers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No trailers found</td></tr>';
        return;
    }
    
    trailers.forEach(trailer => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-trailer-id', trailer.id);
        tr.setAttribute('data-trailer', JSON.stringify(trailer));
        
        // Get gateway info
        const gateway = trailer.installedGateway || {};
        
        tr.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <div class="avatar avatar-sm rounded-circle bg-info text-white me-2">
                        <i class="fas fa-trailer"></i>
                    </div>
                    <div>
                        <span class="d-block fw-bold">${trailer.name || 'Unnamed Trailer'}</span>
                        <small class="text-muted">
                            ${gateway.model ? `Model: ${gateway.model}` : 'No gateway model'}
                        </small>
                    </div>
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    <span class="badge bg-${trailer.enabledForMobile ? 'success' : 'warning'}">
                        ${trailer.enabledForMobile ? 'Mobile Enabled' : 'Mobile Disabled'}
                    </span>
                    ${gateway.serial ? 
                        `<small class="text-muted mt-1">
                            <i class="fas fa-microchip me-1"></i>
                            Serial: ${gateway.serial}
                        </small>` : ''
                    }
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    <span class="text-primary">${trailer.licensePlate || 'N/A'}</span>
                    ${trailer.externalIds ? 
                        `<small class="text-muted">
                            ID: ${trailer.externalIds['samsara.serial'] || 'N/A'}
                        </small>` : ''
                    }
                </div>
            </td>
            <td>
                ${trailer.tags?.map(tag => `
                    <span class="badge bg-secondary me-1">
                        ${tag.name}
                    </span>
                `).join('') || 'No tags'}
            </td>
            <td>
                <div class="d-flex flex-column">
                    ${trailer.assignedVehicle ? `
                        <span class="text-success">
                            <i class="fas fa-link me-1"></i>
                            ${trailer.assignedVehicle.name}
                        </span>
                        <small class="text-muted">
                            Since: ${formatDateTime(trailer.assignedVehicle.since)}
                        </small>
                    ` : `
                        <span class="text-muted">
                            <i class="fas fa-unlink me-1"></i>
                            Unassigned
                        </span>
                    `}
                </div>
            </td>
            <td>
                <div class="d-flex flex-column">
                    ${trailer.location ? `
                        <span>${formatLocation(trailer.location)}</span>
                        <small class="text-muted">
                            Updated: ${formatDateTime(trailer.lastLocationTime)}
                        </small>
                    ` : `
                        <span class="text-muted">Location unknown</span>
                    `}
                </div>
            </td>
            <td class="text-end">
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="showTrailerDetails('${trailer.id}')">
                        <i class="fas fa-eye me-1"></i> View
                </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="showTrailerLocation('${trailer.id}')">
                        <i class="fas fa-map-marker-alt me-1"></i> Location
                </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Show driver details
function showDriverDetails(driverId) {
    console.log('Showing driver details for ID:', driverId);
    
    // Find the driver row and get its data
    const driverRow = document.querySelector(`tr[data-driver-id="${driverId}"]`);
        if (!driverRow) {
        console.error('Driver row not found');
        showToast('error', 'Driver not found');
        return;
    }
    
    console.log('Found driver row:', driverRow);
    const driverDataStr = driverRow.getAttribute('data-driver');
    console.log('Driver data from attribute:', driverDataStr);
    
    const driverData = JSON.parse(driverDataStr);
    console.log('Parsed driver data:', driverData);
    
    // Prepare the modal content with available data
    const modalContent = `
        <div class="modal-header">
            <h5 class="modal-title">Driver Details - ${driverData.name || 'Unknown'}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Basic Information</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Name</dt>
                                <dd class="col-sm-8">${driverData.name || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Username</dt>
                                <dd class="col-sm-8">${driverData.username || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Phone</dt>
                                <dd class="col-sm-8">${driverData.phone || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Status</dt>
                                <dd class="col-sm-8">
                                    <span class="badge bg-${driverData.driverActivationStatus === 'active' ? 'success' : 'warning'}">
                                        ${driverData.driverActivationStatus || 'Unknown'}
                                    </span>
                                </dd>
                                
                                <dt class="col-sm-4">Timezone</dt>
                                <dd class="col-sm-8">${driverData.timezone || 'N/A'}</dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">ELD Settings</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Cycle</dt>
                                <dd class="col-sm-8">${driverData.eldSettings?.rulesets?.[0]?.cycle || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Shift</dt>
                                <dd class="col-sm-8">${driverData.eldSettings?.rulesets?.[0]?.shift || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Restart</dt>
                                <dd class="col-sm-8">${driverData.eldSettings?.rulesets?.[0]?.restart || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Break</dt>
                                <dd class="col-sm-8">${driverData.eldSettings?.rulesets?.[0]?.break || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Exemptions</dt>
                                <dd class="col-sm-8">
                                    ${[
                                        driverData.eldAdverseWeatherExemptionEnabled ? 'Weather' : null,
                                        driverData.eldPcEnabled ? 'Personal Conveyance' : null,
                                        driverData.eldYmEnabled ? 'Yard Move' : null
                                    ].filter(Boolean).join(', ') || 'None'}
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Carrier Information</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Carrier</dt>
                                <dd class="col-sm-8">${driverData.carrierSettings?.carrierName || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">DOT Number</dt>
                                <dd class="col-sm-8">${driverData.carrierSettings?.dotNumber || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Office</dt>
                                <dd class="col-sm-8">${driverData.carrierSettings?.mainOfficeAddress || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Terminal</dt>
                                <dd class="col-sm-8">
                                    ${driverData.carrierSettings?.homeTerminalName || 'N/A'}
                                    ${driverData.carrierSettings?.homeTerminalAddress ? 
                                        `<br><small class="text-muted">${driverData.carrierSettings.homeTerminalAddress}</small>` 
                                        : ''}
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">HOS Information</h6>
                            <div id="driverHosInfo">Loading HOS data...</div>
                        </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Show the modal
    showModal(modalContent);
    
    // Fetch HOS data
    fetchDriverHosLogs(driverId).then(hosData => {
        const hosContent = hosData && hosData.length > 0 ? `
            <dl class="row">
                <dt class="col-sm-4">Current Status</dt>
                <dd class="col-sm-8">
                    <span class="badge bg-${getHosStatusClass(hosData[0].hosStatus)}">
                        ${hosData[0].hosStatus || 'Unknown'}
                    </span>
                </dd>
                
                <dt class="col-sm-4">Drive Time</dt>
                <dd class="col-sm-8">${formatDuration(hosData[0].driveTimeRemaining)}</dd>
                
                <dt class="col-sm-4">Shift Time</dt>
                <dd class="col-sm-8">${formatDuration(hosData[0].shiftTimeRemaining)}</dd>
                
                <dt class="col-sm-4">Cycle Time</dt>
                <dd class="col-sm-8">${formatDuration(hosData[0].cycleTimeRemaining)}</dd>
            </dl>
        ` : '<div class="alert alert-info">No recent HOS data available</div>';
        
        document.getElementById('driverHosInfo').innerHTML = hosContent;
    }).catch(error => {
        console.error('Error fetching HOS data:', error);
        document.getElementById('driverHosInfo').innerHTML = 
            '<div class="alert alert-warning">Unable to fetch HOS data. Please try again later.</div>';
    });
}

// Show driver HOS logs
async function showDriverHOS(driverId) {
    try {
        // Get date range inputs
        const now = new Date();
        const defaultStartTime = new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000)); // 7 days ago
        
        const modalId = `hosModal_${driverId}`;
        const modalContent = `
            <div class="modal-header">
                <h5 class="modal-title">Hours of Service Logs</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="${modalId}">
                <div class="row mb-3">
                    <div class="col-md-6">
                        <div class="form-group">
                            <label for="hosStartTime">Start Date</label>
                            <input type="datetime-local" class="form-control" id="hosStartTime" 
                                value="${defaultStartTime.toISOString().slice(0, 16)}">
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="form-group">
                            <label for="hosEndTime">End Date</label>
                            <input type="datetime-local" class="form-control" id="hosEndTime" 
                                value="${now.toISOString().slice(0, 16)}">
                        </div>
                    </div>
                </div>
                
                <ul class="nav nav-tabs mb-3" id="hosTabList" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="logs-tab" data-bs-toggle="tab" data-bs-target="#logs" type="button" role="tab" aria-controls="logs" aria-selected="true">
                            <i class="fas fa-clock me-1"></i>Logs
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="violations-tab" data-bs-toggle="tab" data-bs-target="#violations" type="button" role="tab" aria-controls="violations" aria-selected="false">
                            <i class="fas fa-exclamation-triangle me-1"></i>Violations
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="daily-tab" data-bs-toggle="tab" data-bs-target="#daily" type="button" role="tab" aria-controls="daily" aria-selected="false">
                            <i class="fas fa-calendar-alt me-1"></i>Daily Summary
                        </button>
                    </li>
                </ul>
                
                <div class="tab-content" id="hosTabContent">
                    <div class="tab-pane fade show active" id="logs" role="tabpanel" aria-labelledby="logs-tab">
                        <div id="hosLogsContent">
                            <div class="text-center py-4">
                                <div class="spinner-border text-primary" role="status"></div>
                                <div class="mt-2">Loading logs...</div>
                            </div>
                        </div>
                    </div>
                    <div class="tab-pane fade" id="violations" role="tabpanel" aria-labelledby="violations-tab">
                        <div id="hosViolationsContent">
                            <div class="text-center py-4">
                                <div class="spinner-border text-primary" role="status"></div>
                                <div class="mt-2">Loading violations...</div>
                            </div>
                        </div>
                    </div>
                    <div class="tab-pane fade" id="daily" role="tabpanel" aria-labelledby="daily-tab">
                        <div id="hosDailyContent">
                            <div class="text-center py-4">
                                <div class="spinner-border text-primary" role="status"></div>
                                <div class="mt-2">Loading daily summary...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Show the modal
        showModal(modalContent);
        
        // Get the tab list element once and reuse it
        const tabList = document.getElementById('hosTabList');
        if (tabList) {
            // Initialize Bootstrap tabs
            const tabs = tabList.querySelectorAll('[data-bs-toggle="tab"]');
            tabs.forEach(tab => {
                new bootstrap.Tab(tab); // Initialize each tab
                // Set up tab change listeners using Bootstrap's tab API
                tab.addEventListener('shown.bs.tab', () => loadHosData(driverId));
            });
        }
        
        // Load initial data
        await loadHosData(driverId);
        
        // Set up event listeners for date range changes
        document.getElementById('hosStartTime')?.addEventListener('change', () => loadHosData(driverId));
        document.getElementById('hosEndTime')?.addEventListener('change', () => loadHosData(driverId));
        
    } catch (error) {
        console.error('Error showing HOS modal:', error);
        showModal(`
            <div class="modal-header">
                <h5 class="modal-title">Hours of Service Logs</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="alert alert-danger">
                    Failed to load HOS data. Please try again later.
                </div>
            </div>
        `);
    }
}

// Helper function to load HOS data based on current tab and date range
async function loadHosData(driverId) {
    try {
        const startTimeEl = document.getElementById('hosStartTime');
        const endTimeEl = document.getElementById('hosEndTime');
        
        if (!startTimeEl || !endTimeEl) {
            console.error('Date range inputs not found');
            return;
        }
        
        const startTime = startTimeEl.value;
        const endTime = endTimeEl.value;
        
        const hosTabContent = document.getElementById('hosTabContent');
        if (!hosTabContent) {
            console.error('HOS tab content container not found');
            return;
        }
        
        const activeTabEl = hosTabContent.querySelector('.tab-pane.show.active');
        if (!activeTabEl) {
            console.error('No active tab pane found in HOS tab content');
            return;
        }
        
        const activeTab = activeTabEl.id.replace('hosTab', '').toLowerCase();
        
        switch (activeTab) {
            case 'logs':
                const logsResponse = await fetchDriverHosLogs(driverId, startTime, endTime);
                const logs = logsResponse?.[0]?.hosLogs || [];
                const logsContentEl = document.getElementById('hosLogsContent');
                
                if (logsContentEl) {
                    if (logs.length > 0) {
                        logsContentEl.innerHTML = `
                            <div class="timeline">
                                ${logs.map(log => `
                                    <div class="timeline-item">
                                        <div class="timeline-marker bg-${getHosStatusClass(log.hosStatusType)}"></div>
                                        <div class="timeline-content">
                                            <div class="d-flex justify-content-between">
                                                <span class="fw-bold">${formatHosStatus(log.hosStatusType)}</span>
                                                <small class="text-gray-500">${formatDateTime(log.logStartTime)} - ${formatDateTime(log.logEndTime)}</small>
                                            </div>
                                            ${log.remark ? `<p class="text-sm mb-0">${log.remark}</p>` : ''}
                                            ${log.logRecordedLocation ? `
                                                <small class="text-gray-500">
                                                    Location: ${log.logRecordedLocation.latitude.toFixed(6)}, ${log.logRecordedLocation.longitude.toFixed(6)}
                                                </small>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>`;
                    } else {
                        logsContentEl.innerHTML = '<div class="alert alert-info">No logs available for this period</div>';
                    }
                }
                break;
                
            case 'violations':
                const violationsResponse = await fetchDriverHosViolations(driverId, startTime, endTime);
                // The violations array is directly in the response
                const violations = violationsResponse?.[0]?.violations || [];
                const violationsContentEl = document.getElementById('hosViolationsContent');
                
                if (violationsContentEl) {
                    if (violations.length > 0) {
                        violationsContentEl.innerHTML = `
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>Type</th>
                                            <th>Description</th>
                                            <th>Start Time</th>
                                            <th>Duration</th>
                                            <th>Day</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${violations.map(violation => `
                                            <tr>
                                                <td>${formatViolationType(violation.type)}</td>
                                                <td>${violation.description}</td>
                                                <td>${formatDateTime(violation.violationStartTime)}</td>
                                                <td>${formatDuration(violation.durationMs / 60000)}</td>
                                                <td>${formatDate(violation.day?.startTime)} - ${formatDate(violation.day?.endTime)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>`;
                    } else {
                        violationsContentEl.innerHTML = '<div class="alert alert-info">No violations found for this period</div>';
                    }
                }
                break;
                
            case 'daily':
                const dailyLogsResponse = await fetchDriverHosDailyLogs(driverId, startTime, endTime);
                const dailyLogs = dailyLogsResponse?.daily_logs || [];
                const dailyContentEl = document.getElementById('hosDailyContent');
                
                if (dailyContentEl) {
                    if (dailyLogs.length > 0) {
                        dailyContentEl.innerHTML = `
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Drive Time</th>
                                            <th>On Duty Time</th>
                                            <th>Off Duty Time</th>
                                            <th>Sleeper Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${dailyLogs.map(log => `
                                            <tr>
                                                <td>${formatDate(log.date)}</td>
                                                <td>${formatDuration(log.driveTime)}</td>
                                                <td>${formatDuration(log.onDutyTime)}</td>
                                                <td>${formatDuration(log.offDutyTime)}</td>
                                                <td>${formatDuration(log.sleeperTime)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>`;
                    } else {
                        dailyContentEl.innerHTML = '<div class="alert alert-info">No daily logs available for this period</div>';
                    }
                }
                break;
        }
    } catch (error) {
        console.error('Error loading HOS data:', error);
        showError('Failed to load HOS data. Please try again.');
    }
}

// Helper function to format violation type
function formatViolationType(type) {
    if (!type) return 'Unknown';
    return type.split(/(?=[A-Z])/).join(' ');
}

// Helper function to format HOS status
function formatHosStatus(status) {
    if (!status) return 'Unknown';
    const statusMap = {
        'offDuty': 'Off Duty',
        'sleeper': 'Sleeper',
        'driving': 'Driving',
        'onDuty': 'On Duty',
        'personalConveyance': 'Personal Conveyance',
        'yardMove': 'Yard Move'
    };
    return statusMap[status] || status.split(/(?=[A-Z])/).join(' ');
}

// Helper function to get HOS status class
function getHosStatusClass(status) {
    if (!status) return 'secondary';
    const statusClasses = {
        'onDuty': 'warning',
        'offDuty': 'secondary',
        'sleeper': 'info',
        'driving': 'success',
        'personalConveyance': 'primary',
        'yardMove': 'primary'
    };
    return statusClasses[status] || 'secondary';
}

// Helper function to format date
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString();
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateStr;
    }
}

// Helper function to format duration in minutes to hours and minutes
function formatDuration(minutes) {
    if (!minutes && minutes !== 0) return 'N/A';
    try {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}h ${mins}m`;
    } catch (e) {
        console.error('Error formatting duration:', e);
        return `${minutes}m`;
    }
}

// Show vehicle details
function showVehicleDetails(vehicleId) {
    console.log('Showing vehicle details for ID:', vehicleId);
    
    // Find the vehicle row and get its data
    const vehicleRow = document.querySelector(`tr[data-vehicle-id="${vehicleId}"]`);
    if (!vehicleRow) {
        console.error('Vehicle row not found');
        showToast('error', 'Vehicle not found');
        return;
    }
    
    console.log('Found vehicle row:', vehicleRow);
    const vehicleDataStr = vehicleRow.getAttribute('data-vehicle');
    console.log('Vehicle data from attribute:', vehicleDataStr);
    
    const vehicleData = JSON.parse(vehicleDataStr);
    console.log('Parsed vehicle data:', vehicleData);
    
    // Prepare the modal content with available data
    const modalContent = `
        <div class="modal-header">
            <h5 class="modal-title">Vehicle Details - ${vehicleData.name || 'Unknown'}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Basic Information</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Name</dt>
                                <dd class="col-sm-8">${vehicleData.name || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Make</dt>
                                <dd class="col-sm-8">${vehicleData.make || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Model</dt>
                                <dd class="col-sm-8">${vehicleData.model || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Year</dt>
                                <dd class="col-sm-8">${vehicleData.year || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">License</dt>
                                <dd class="col-sm-8">${vehicleData.licensePlate || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">VIN</dt>
                                <dd class="col-sm-8">${vehicleData.vin || 'N/A'}</dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Status & Settings</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Status</dt>
                                <dd class="col-sm-8">${vehicleData.vehicleRegulationMode || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Tags</dt>
                                <dd class="col-sm-8">${vehicleData.tags ? vehicleData.tags.map(tag => tag.name).join(', ') : 'None'}</dd>
                                
                                <dt class="col-sm-4">Created</dt>
                                <dd class="col-sm-8">${formatDateTime(vehicleData.createdAtTime)}</dd>
                                
                                <dt class="col-sm-4">Updated</dt>
                                <dd class="col-sm-8">${formatDateTime(vehicleData.updatedAtTime)}</dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Real-Time Information</h6>
                            <div id="vehicleRealTimeInfo">Loading real-time data...</div>
                        </div>
                    </div>
                </div>

                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Driver Assignment</h6>
                            <div id="vehicleDriverInfo">Loading driver assignment...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Show the modal
    showModal(modalContent);
    
    // Fetch real-time data and driver assignment in parallel
    Promise.all([
        fetchVehicleLocation(vehicleId),
        fetchVehicleStats(vehicleId),
        fetch(`/samsara/fleet/vehicles/assignments/${clientId}?vehicleId=${vehicleId}`).then(r => r.json())
    ]).then(([locationData, statsData, assignmentData]) => {
        // Update real-time info
        const realTimeContent = `
            <dl class="row">
                <dt class="col-sm-3">Current Location</dt>
                <dd class="col-sm-9">
                    ${locationData ? formatLocation(locationData.location) : 'Location data unavailable'}
                </dd>
                
                <dt class="col-sm-3">Speed</dt>
                <dd class="col-sm-9">
                    ${locationData?.location?.speed ? formatSpeed(locationData.location.speed) : 'N/A'}
                </dd>
                
                <dt class="col-sm-3">Engine Hours</dt>
                <dd class="col-sm-9">
                    ${statsData?.engineHours || 'N/A'}
                </dd>
                
                <dt class="col-sm-3">Odometer</dt>
                <dd class="col-sm-9">
                    ${statsData?.odometer ? `${statsData.odometer.toLocaleString()} miles` : 'N/A'}
                </dd>
                
                <dt class="col-sm-3">Fuel Level</dt>
                <dd class="col-sm-9">
                    ${statsData?.fuelPercent ? `${statsData.fuelPercent}%` : 'N/A'}
                </dd>
                
                <dt class="col-sm-3">Engine State</dt>
                <dd class="col-sm-9">
                    <span class="badge bg-${statsData?.engineState === 'running' ? 'success' : 'secondary'}">
                        ${statsData?.engineState || 'Unknown'}
                    </span>
                </dd>
            </dl>
        `;
        document.getElementById('vehicleRealTimeInfo').innerHTML = realTimeContent;

        // Update driver assignment info
        const assignment = assignmentData?.assignments?.[0];
        const driverContent = assignment ? `
            <dl class="row">
                <dt class="col-sm-3">Current Driver</dt>
                <dd class="col-sm-9">
                    <div class="d-flex align-items-center">
                        <div class="avatar avatar-sm rounded-circle bg-primary text-white me-2">
                            ${assignment.driver.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <span class="d-block">${assignment.driver.name}</span>
                            <small class="text-muted">Since: ${formatDateTime(assignment.startTime)}</small>
                        </div>
                    </div>
                </dd>
            </dl>
        ` : '<div class="alert alert-info">No driver currently assigned</div>';
        document.getElementById('vehicleDriverInfo').innerHTML = driverContent;
    }).catch(error => {
        console.error('Error fetching real-time data:', error);
        document.getElementById('vehicleRealTimeInfo').innerHTML = 
            '<div class="alert alert-warning">Unable to fetch real-time data. Please try again later.</div>';
        document.getElementById('vehicleDriverInfo').innerHTML = 
            '<div class="alert alert-warning">Unable to fetch driver assignment. Please try again later.</div>';
    });
}

// Helper function to format location data
function formatLocation(location) {
    if (!location) return 'Unknown';
    if (location.reverseGeo?.formattedLocation) {
        return location.reverseGeo.formattedLocation;
    }
    return `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`;
}

// Helper function to format speed
function formatSpeed(speedMs) {
    const speedMph = speedMs * 2.237; // Convert m/s to mph
    return `${speedMph.toFixed(1)} mph`;
}

// Helper function to format date and time
function formatDateTime(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString();
    } catch (e) {
        console.error('Error formatting datetime:', e);
        return dateStr;
    }
}

// Show trailer details
function showTrailerDetails(trailerId) {
    console.log('Showing trailer details for ID:', trailerId);
    
    // Find the trailer row and get its data
    const trailerRow = document.querySelector(`tr[data-trailer-id="${trailerId}"]`);
    if (!trailerRow) {
        console.error('Trailer row not found');
        showToast('error', 'Trailer not found');
        return;
    }
    
    console.log('Found trailer row:', trailerRow);
    const trailerDataStr = trailerRow.getAttribute('data-trailer');
    console.log('Trailer data from attribute:', trailerDataStr);
    
    const trailerData = JSON.parse(trailerDataStr);
    console.log('Parsed trailer data:', trailerData);
    
    // Prepare the modal content with available data
    const modalContent = `
        <div class="modal-header">
            <h5 class="modal-title">Trailer Details - ${trailerData.name || 'Unknown'}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Basic Information</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Name</dt>
                                <dd class="col-sm-8">${trailerData.name || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">License Plate</dt>
                                <dd class="col-sm-8">${trailerData.licensePlate || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Type</dt>
                                <dd class="col-sm-8">${trailerData.tags ? trailerData.tags.map(tag => tag.name).join(', ') : 'Unknown'}</dd>
                                
                                <dt class="col-sm-4">Mobile Enabled</dt>
                                <dd class="col-sm-8">
                                    <span class="badge bg-${trailerData.enabledForMobile ? 'success' : 'secondary'}">
                                        ${trailerData.enabledForMobile ? 'Yes' : 'No'}
                                    </span>
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Gateway Information</h6>
                            <dl class="row">
                                <dt class="col-sm-4">Model</dt>
                                <dd class="col-sm-8">${trailerData.installedGateway?.model || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">Serial</dt>
                                <dd class="col-sm-8">${trailerData.installedGateway?.serial || 'N/A'}</dd>
                                
                                <dt class="col-sm-4">External ID</dt>
                                <dd class="col-sm-8">${trailerData.externalIds?.['samsara.serial'] || 'N/A'}</dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Real-Time Information</h6>
                            <div id="trailerRealTimeInfo">Loading real-time data...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Show the modal
    showModal(modalContent);
    
    // Fetch real-time data
    fetchTrailerLocation(trailerId).then(locationData => {
        const realTimeContent = `
            <dl class="row">
                <dt class="col-sm-3">Current Location</dt>
                <dd class="col-sm-9">
                    ${locationData ? formatLocation(locationData.location) : 'Location data unavailable'}
                </dd>
                
                <dt class="col-sm-3">Last Updated</dt>
                <dd class="col-sm-9">
                    ${locationData?.location?.time ? formatDateTime(locationData.location.time) : 'N/A'}
                </dd>
                
                ${trailerData.tags?.some(tag => tag.name === 'Reefer') ? `
                    <dt class="col-sm-3">Temperature</dt>
                    <dd class="col-sm-9">Temperature data not available</dd>
                ` : ''}
            </dl>
        `;
        document.getElementById('trailerRealTimeInfo').innerHTML = realTimeContent;
    }).catch(error => {
        console.error('Error fetching real-time data:', error);
        document.getElementById('trailerRealTimeInfo').innerHTML = 
            '<div class="alert alert-warning">Unable to fetch real-time data. Please try again later.</div>';
    });
}

// Filter functions
function filterDrivers() {
    const searchTerm = document.getElementById('driverSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#driversTable tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

function filterVehicles() {
    const searchTerm = document.getElementById('vehicleSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#vehiclesTable tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

function filterTrailers() {
    const searchTerm = document.getElementById('trailerSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#trailersTable tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

// Helper functions
function getStatusClass(status) {
    const classes = {
        'active': 'success',
        'inactive': 'secondary',
        'maintenance': 'warning',
        'out_of_service': 'danger'
    };
    return classes[status?.toLowerCase()] || 'secondary';
}

function formatLocation(location) {
    if (!location) return 'Unknown';
    if (typeof location === 'string') return location;
    if (location.latitude && location.longitude) {
        return `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`;
    }
    return 'Unknown';
}

function formatDateTime(timestamp) {
    if (!timestamp) return 'N/A';
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch (error) {
        return timestamp;
    }
}

// Toast notifications
function showSuccess(message) {
    // Implement your preferred toast notification
    alert(message);
}

function showError(message) {
    // Implement your preferred toast notification
    alert(message);
}

// Helper function to format regulation mode
function formatRegulationMode(mode) {
    if (!mode) return 'Unknown';
    return mode.split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

// Helper function to format setting type
function formatSettingType(type) {
    if (!type) return 'Unknown';
    return type.split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

// Function to show vehicle statistics in modal
async function showVehicleStats(vehicleId) {
    try {
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('detailsModalTitle');
        const modalBody = document.getElementById('detailsModalBody');

        // Show loading state
        modalTitle.textContent = 'Vehicle Statistics';
        modalBody.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">Loading statistics...</div></div>';
        
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        const stats = await fetchVehicleStats(vehicleId);

        if (stats) {
            // Safely access values, providing 'N/A' or 0 as default
            const engineState = stats.engineState ? stats.engineState.value : 'N/A';
            const fuelPercent = stats.fuelPercent ? stats.fuelPercent.value : 0;
            const obdOdometerMeters = stats.obdOdometerMeters ? stats.obdOdometerMeters.value : 0;
            const obdEngineSeconds = stats.obdEngineSeconds ? stats.obdEngineSeconds.value : 0;

            // Calculate engine hours (1 hour = 3600 seconds)
            const engineHours = obdEngineSeconds ? (obdEngineSeconds / 3600).toFixed(1) : '0';

            // Calculate odometer in miles (1 meter = 0.000621371 miles)
            const odometerMiles = obdOdometerMeters ? (obdOdometerMeters * 0.000621371).toFixed(1) : '0';

            modalBody.innerHTML = `
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div class="card shadow-sm">
                            <div class="card-body">
                                <h5 class="card-title text-primary mb-3">
                                    <i class="fas fa-tachometer-alt me-2"></i>Engine Statistics
                                </h5>
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="text-muted">Engine Hours</span>
                                    <span class="fw-bold fs-4">${engineHours} <small class="text-muted">hrs</small></span>
                                </div>
                                <hr class="my-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="text-muted">Engine State</span>
                                    <span class="badge bg-${engineState === 'On' ? 'success' : (engineState === 'Off' ? 'danger' : 'secondary')} fs-6">
                                        ${engineState}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6 mb-4">
                        <div class="card shadow-sm">
                            <div class="card-body">
                                <h5 class="card-title text-success mb-3">
                                    <i class="fas fa-gas-pump me-2"></i>Fuel Information
                                </h5>
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="text-muted">Fuel Level</span>
                                    <span class="fw-bold fs-4">${fuelPercent}%</span>
                                </div>
                                <div class="progress" style="height: 20px;">
                                    <div class="progress-bar bg-success" role="progressbar" style="width: ${fuelPercent}%;" aria-valuenow="${fuelPercent}" aria-valuemin="0" aria-valuemax="100">
                                        ${fuelPercent}%
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-12">
                        <div class="card shadow-sm">
                            <div class="card-body">
                                <h5 class="card-title text-info mb-3">
                                    <i class="fas fa-road me-2"></i>Odometer
                                </h5>
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="text-muted">Distance Traveled</span>
                                    <span class="fw-bold fs-4">${odometerMiles} <small class="text-muted">miles</small></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            modalBody.innerHTML = `
                <div class="alert alert-danger text-center" role="alert">
                    <h5 class="alert-heading mb-2"><i class="fas fa-exclamation-triangle me-2"></i>Failed to load statistics</h5>
                    <p>Could not retrieve vehicle statistics at this time. Please try again later.</p>
                    <hr>
                    <p class="mb-0 small text-muted">If the problem persists, please check the application logs or contact support.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error in showVehicleStats:', error);
        const modalBody = document.getElementById('detailsModalBody');
        if (modalBody) { // Ensure modalBody exists before trying to update it
            modalBody.innerHTML = `
                <div class="alert alert-danger text-center" role="alert">
                    <h5 class="alert-heading mb-2"><i class="fas fa-cogs me-2"></i>An Error Occurred</h5>
                    <p>An unexpected error occurred while trying to display vehicle statistics.</p>
                    <pre class="bg-light p-2 rounded small text-start">${error.message}\\n${error.stack ? error.stack.substring(0, 300) + '...' : ''}</pre>
                </div>
            `;
        }
        // Ensure modal is shown even if an error occurs early
        const modal = document.getElementById('detailsModal');
        if (modal && !bootstrap.Modal.getInstance(modal)) {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    }
}

// Add new function to show vehicle location
async function showVehicleLocation(vehicleId) {
    try {
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('detailsModalTitle');
        const modalBody = document.getElementById('detailsModalBody');
        
        modalTitle.textContent = 'Vehicle Location';
        modalBody.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">Loading location...</div></div>';
        
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        const location = await fetchVehicleLocation(vehicleId);
        
        if (location) {
            // location object now comes from the stats API (gps type)
            // It includes: vehicleId, name, time, latitude, longitude, heading, speed, address
            const speedDisplay = location.speed !== null && location.speed !== undefined ? `${parseFloat(location.speed).toFixed(1)} mph` : 'N/A';
            const headingDisplay = location.heading !== null && location.heading !== undefined ? `${parseFloat(location.heading).toFixed(0)}°` : 'N/A';
            
            modalBody.innerHTML = `
                <div class="card shadow-sm">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3 pb-2 border-bottom">
                            <div class="icon-shape bg-primary text-white rounded-circle me-3 fs-5 d-flex align-items-center justify-content-center" style="width: 50px; height: 50px;">
                                <i class="fas fa-map-marker-alt fa-fw"></i>
                            </div>
                            <div>
                                <h5 class="mb-0 text-primary">Current Location: ${location.name || 'Vehicle'} (#${location.vehicleId || vehicleId})</h5>
                                <small class="text-muted">Last updated: ${formatDateTime(location.time) || 'Not available'}</small>
                            </div>
                        </div>
                        
                        <div class="row g-3">
                            <div class="col-md-12">
                                <div class="p-3 bg-light rounded">
                                    <h6 class="text-muted mb-1"><i class="fas fa-map-pin me-2"></i>Address</h6>
                                    <p class="mb-0 fs-5">${location.address || 'Address not available'}</p>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded">
                                    <h6 class="text-muted mb-1"><i class="fas fa-compass me-2"></i>Coordinates</h6>
                                    <p class="mb-0 fs-5">
                                        Lat: ${location.latitude?.toFixed(5) || 'N/A'}<br>
                                        Lon: ${location.longitude?.toFixed(5) || 'N/A'}
                                    </p>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded">
                                    <h6 class="text-muted mb-1"><i class="fas fa-tachometer-alt me-2"></i>Speed & Heading</h6>
                                    <p class="mb-0 fs-5">
                                        Speed: ${speedDisplay}<br>
                                        Heading: ${headingDisplay}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            modalBody.innerHTML = `
                <div class="alert alert-danger text-center" role="alert">
                    <h5 class="alert-heading mb-2"><i class="fas fa-map-marked-alt me-2"></i>Location Not Found</h5>
                    <p>Could not retrieve location data for this vehicle at this time. It may be offline or data may not be available.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error in showVehicleLocation:', error);
        const modalBody = document.getElementById('detailsModalBody');
        if (modalBody) {
            modalBody.innerHTML = `
                <div class="alert alert-danger text-center" role="alert">
                    <h5 class="alert-heading mb-2"><i class="fas fa-cogs me-2"></i>An Error Occurred</h5>
                    <p>An unexpected error occurred while trying to display vehicle location.</p>
                    <pre class="bg-light p-2 rounded small text-start">${error.message}\\n${error.stack ? error.stack.substring(0, 300) + '...' : ''}</pre>
                </div>
            `;
        }
        const modal = document.getElementById('detailsModal');
        if (modal && !bootstrap.Modal.getInstance(modal)) {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    }
}

// Add new function to show trailer location
async function showTrailerLocation(trailerId) {
    try {
        const response = await fetch(`/samsara/fleet/trailers/locations/${clientId}?trailerId=${trailerId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const modal = document.getElementById('detailsModal');
            const modalTitle = document.getElementById('detailsModalTitle');
            const modalBody = document.getElementById('detailsModalBody');
            
            modalTitle.textContent = 'Trailer Location';
            
            const location = data.locations[0] || {};
            modalBody.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <div class="icon-shape bg-info text-white rounded-circle me-3">
                                <i class="fas fa-map-marker-alt fa-fw"></i>
                            </div>
                            <div>
                                <h5 class="mb-0">Current Location</h5>
                                <small class="text-muted">Last updated: ${formatDateTime(location.time)}</small>
                            </div>
                        </div>
                        
                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="info-box bg-light">
                                    <h6 class="mb-2">Coordinates</h6>
                                    <p class="mb-0">
                                        ${location.latitude?.toFixed(6) || 'N/A'}, 
                                        ${location.longitude?.toFixed(6) || 'N/A'}
                                    </p>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="info-box bg-light">
                                    <h6 class="mb-2">Status</h6>
                                    <p class="mb-0">
                                        ${location.status || 'Status unknown'}
                                    </p>
                                </div>
                            </div>
                            <div class="col-12">
                                <div class="info-box bg-light">
                                    <h6 class="mb-2">Address</h6>
                                    <p class="mb-0">
                                        ${location.address || 'Address not available'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    } catch (error) {
        console.error('Error loading trailer location:', error);
        showError('Failed to load trailer location');
    }
} 