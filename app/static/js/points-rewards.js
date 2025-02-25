// Points & Rewards Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Points Chart
    if(document.querySelector('.ct-chart-points')) {
        const pointsData = {
            labels: [], // Will be populated from API
            series: [[]] // Will be populated from API
        };

        const pointsChart = new Chartist.Line('.ct-chart-points', pointsData, {
            low: 0,
            showArea: true,
            fullWidth: true,
            plugins: [
                Chartist.plugins.tooltip()
            ],
            axisY: {
                onlyInteger: true,
                offset: 20
            }
        });

        // Add animation
        pointsChart.on('draw', function(data) {
            if(data.type === 'line' || data.type === 'area') {
                data.element.animate({
                    d: {
                        begin: 2000 * data.index,
                        dur: 2000,
                        from: data.path.clone().scale(1, 0).translate(0, data.chartRect.height()).stringify(),
                        to: data.path.clone().stringify(),
                        easing: Chartist.Svg.Easing.easeOutQuint
                    }
                });
            }
        });

        // Load initial points data
        loadPointsData('month'); // Default to monthly view
    }

    // Points History Period Buttons
    const periodButtons = document.querySelectorAll('.btn-group .btn');
    periodButtons.forEach(button => {
        button.addEventListener('click', function() {
            periodButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            loadPointsData(this.textContent.toLowerCase());
        });
    });

    // Company Status Update
    const statusModal = document.getElementById('updateStatus');
    if(statusModal) {
        statusModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const companyRow = button.closest('tr');
            const companyName = companyRow.querySelector('.fw-bold').textContent;
            const currentStatus = companyRow.querySelector('.badge').textContent;
            
            const modal = this;
            modal.querySelector('.modal-title').textContent = `Update Status: ${companyName}`;
            
            // Set current status in select
            const statusSelect = modal.querySelector('#statusSelect');
            Array.from(statusSelect.options).forEach(option => {
                if(option.text === currentStatus) {
                    option.selected = true;
                }
            });

            // Store company data for submission
            modal.dataset.companyId = companyRow.dataset.companyId;
        });

        // Handle status update submission
        const updateButton = statusModal.querySelector('.btn-primary');
        updateButton.addEventListener('click', async function() {
            const modal = this.closest('.modal');
            const companyId = modal.dataset.companyId;
            const newStatus = modal.querySelector('#statusSelect').value;

            try {
                const response = await fetch(`/api/v1/company/companies/${companyId}/status`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: newStatus })
                });

                if (!response.ok) throw new Error('Failed to update status');

                const result = await response.json();

                // Show success notification
                Swal.fire({
                    title: 'Status Updated!',
                    text: `You earned ${result.points_earned} points!`,
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });

                // Update UI
                updateCompanyStatus(companyId, newStatus, result.points_earned);
                updateTotalPoints(result.total_points);

                // Close modal
                bootstrap.Modal.getInstance(modal).hide();

            } catch (error) {
                Swal.fire({
                    title: 'Error!',
                    text: 'Failed to update status. Please try again.',
                    icon: 'error'
                });
            }
        });
    }

    // Initialize real-time updates
    initializeRealtimeUpdates();

    // Admin Points Management
    if (document.getElementById('addPointRule')) {
        initializePointsAdmin();
    }
});

// Load points history data
async function loadPointsData(period) {
    try {
        const response = await fetch(`/dashboard/points/history?period=${period}`);
        if (!response.ok) throw new Error('Failed to load points data');
        
        const data = await response.json();
        
        // Update chart
        const chart = Chartist.instances['.ct-chart-points'];
        if (chart) {
            chart.update({
                labels: Object.keys(data.data),
                series: [Object.values(data.data)]
            });
        }

    } catch (error) {
        console.error('Error loading points data:', error);
    }
}

// Update company status in UI
function updateCompanyStatus(companyId, newStatus, pointsEarned) {
    const companyRow = document.querySelector(`tr[data-company-id="${companyId}"]`);
    if (!companyRow) return;

    const statusBadge = companyRow.querySelector('.badge');
    const pointsCell = companyRow.querySelector('td:nth-child(3) .fw-bold');

    // Remove old status class and add new one
    statusBadge.classList.forEach(className => {
        if (className.startsWith('bg-')) {
            statusBadge.classList.remove(className);
        }
    });
    statusBadge.classList.add(`bg-${newStatus}`);
    statusBadge.textContent = newStatus;

    // Update points with animation
    const currentPoints = parseInt(pointsCell.textContent);
    const newPoints = currentPoints + pointsEarned;
    pointsCell.textContent = newPoints;
    pointsCell.classList.add('points-change');
    setTimeout(() => pointsCell.classList.remove('points-change'), 600);
}

// Update total points display
function updateTotalPoints(newTotal) {
    const totalPointsElements = document.querySelectorAll('.total-points');
    totalPointsElements.forEach(element => {
        element.textContent = newTotal;
        element.classList.add('points-change');
        setTimeout(() => element.classList.remove('points-change'), 600);
    });
}

// Initialize WebSocket or polling for real-time updates
function initializeRealtimeUpdates() {
    // Poll for updates every 30 seconds
    setInterval(async () => {
        try {
            const response = await fetch('/api/v1/points-rewards/points/summary');
            if (!response.ok) throw new Error('Failed to fetch updates');
            
            const data = await response.json();
            
            // Update UI with new data
            updateTotalPoints(data.total_points);
            
            // Update rank if changed
            const rankElement = document.querySelector('.rank-display');
            if (rankElement && data.rank !== rankElement.textContent) {
                rankElement.textContent = `#${data.rank}`;
                rankElement.classList.add('points-change');
                setTimeout(() => rankElement.classList.remove('points-change'), 600);
            }

            // Update next reward progress
            const progressBar = document.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${data.next_reward_progress}%`;
                progressBar.setAttribute('aria-valuenow', data.next_reward_progress);
            }

        } catch (error) {
            console.error('Error fetching updates:', error);
        }
    }, 30000);
}

// Initialize Points Admin functionality
function initializePointsAdmin() {
    // Add Point Rule
    const addRuleModal = document.getElementById('addPointRule');
    const addRuleForm = addRuleModal.querySelector('form');
    const addRuleButton = addRuleModal.querySelector('.btn-primary');

    addRuleButton.addEventListener('click', async function() {
        // Get form values
        const actionName = addRuleForm.querySelector('#actionName').value;
        const description = addRuleForm.querySelector('#description').value;
        const points = parseInt(addRuleForm.querySelector('#points').value);
        const frequencyLimit = addRuleForm.querySelector('#frequencyLimit').value;
        const frequencyPeriod = addRuleForm.querySelector('#frequencyPeriod').value;
        const isActive = addRuleForm.querySelector('#isActive').checked;

        // Generate key from action name
        const key = actionName.toLowerCase().replace(/\s+/g, '_');

        try {
            const response = await fetch('/api/v1/points-rewards/points/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    [key]: points,
                    metadata: {
                        description: description,
                        frequency_limit: frequencyLimit || null,
                        frequency_period: frequencyPeriod,
                        is_active: isActive
                    }
                })
            });

            if (!response.ok) throw new Error('Failed to add point rule');

            // Show success notification
            Swal.fire({
                title: 'Rule Added!',
                text: 'The point rule has been added successfully.',
                icon: 'success',
                timer: 2000,
                showConfirmButton: false
            });

            // Reload page to show new rule
            setTimeout(() => window.location.reload(), 2000);

        } catch (error) {
            Swal.fire({
                title: 'Error!',
                text: 'Failed to add point rule. Please try again.',
                icon: 'error'
            });
        }
    });

    // Edit Point Rule
    const editRuleModal = document.getElementById('editPointRule');
    if (editRuleModal) {
        editRuleModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const ruleId = button.dataset.ruleId;
            
            // Find rule data from the table
            const ruleRow = document.querySelector(`tr[data-rule-id="${ruleId}"]`);
            if (!ruleRow) return;
            
            const actionName = ruleRow.querySelector('.fw-bold').textContent;
            const description = ruleRow.querySelector('.small.text-gray').textContent;
            const points = ruleRow.querySelector('td:nth-child(2)').textContent;
            const frequencyText = ruleRow.querySelector('td:nth-child(3)').textContent;
            const isActive = ruleRow.querySelector('.badge.bg-success') !== null;
            
            // Parse frequency limit
            let frequencyLimit = '';
            let frequencyPeriod = 'day';
            if (frequencyText !== 'No limit') {
                const match = frequencyText.match(/(\d+) per (\w+)/);
                if (match) {
                    frequencyLimit = match[1];
                    frequencyPeriod = match[2];
                }
            }
            
            // Set form values
            const form = editRuleModal.querySelector('form');
            form.querySelector('#editRuleId').value = ruleId;
            form.querySelector('#editActionName').value = actionName;
            form.querySelector('#editDescription').value = description;
            form.querySelector('#editPoints').value = points;
            form.querySelector('#editFrequencyLimit').value = frequencyLimit;
            form.querySelector('#editFrequencyPeriod').value = frequencyPeriod;
            form.querySelector('#editIsActive').checked = isActive;
        });
        
        // Handle edit submission
        const editButton = editRuleModal.querySelector('.btn-primary');
        editButton.addEventListener('click', async function() {
            const form = editRuleModal.querySelector('form');
            const ruleId = form.querySelector('#editRuleId').value;
            const actionName = form.querySelector('#editActionName').value;
            const description = form.querySelector('#editDescription').value;
            const points = parseInt(form.querySelector('#editPoints').value);
            const frequencyLimit = form.querySelector('#editFrequencyLimit').value;
            const frequencyPeriod = form.querySelector('#editFrequencyPeriod').value;
            const isActive = form.querySelector('#editIsActive').checked;
            
            // Find the key from the table
            const ruleRow = document.querySelector(`tr[data-rule-id="${ruleId}"]`);
            if (!ruleRow) return;
            
            const key = ruleRow.dataset.ruleKey;
            
            try {
                const response = await fetch('/api/v1/points-rewards/points/config', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        [key]: points,
                        metadata: {
                            description: description,
                            frequency_limit: frequencyLimit || null,
                            frequency_period: frequencyPeriod,
                            is_active: isActive
                        }
                    })
                });
                
                if (!response.ok) throw new Error('Failed to update point rule');
                
                // Show success notification
                Swal.fire({
                    title: 'Rule Updated!',
                    text: 'The point rule has been updated successfully.',
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Reload page to show updated rule
                setTimeout(() => window.location.reload(), 2000);
                
            } catch (error) {
                Swal.fire({
                    title: 'Error!',
                    text: 'Failed to update point rule. Please try again.',
                    icon: 'error'
                });
            }
        });
    }
    
    // Delete Point Rule
    const deleteRuleModal = document.getElementById('deletePointRule');
    if (deleteRuleModal) {
        deleteRuleModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const ruleId = button.dataset.ruleId;
            deleteRuleModal.dataset.ruleId = ruleId;
        });
        
        // Handle delete submission
        const deleteButton = deleteRuleModal.querySelector('.btn-danger');
        deleteButton.addEventListener('click', async function() {
            const ruleId = deleteRuleModal.dataset.ruleId;
            
            try {
                const response = await fetch(`/api/v1/points-rewards/points/config/${ruleId}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) throw new Error('Failed to delete point rule');
                
                // Show success notification
                Swal.fire({
                    title: 'Rule Deleted!',
                    text: 'The point rule has been deleted successfully.',
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Reload page to update rule list
                setTimeout(() => window.location.reload(), 2000);
                
            } catch (error) {
                Swal.fire({
                    title: 'Error!',
                    text: 'Failed to delete point rule. Please try again.',
                    icon: 'error'
                });
            }
        });
    }
    
    // Initialize Points Distribution Chart
    if (document.querySelector('.ct-chart-distribution')) {
        const distributionData = JSON.parse(document.getElementById('distributionData').textContent);
        
        new Chartist.Bar('.ct-chart-distribution', {
            labels: distributionData.labels,
            series: [distributionData.series]
        }, {
            distributeSeries: true,
            plugins: [
                Chartist.plugins.tooltip()
            ]
        });
    }
}
