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
});

// Load points history data
async function loadPointsData(period) {
    try {
        const response = await fetch(`/api/v1/points-rewards/points/history?period=${period}`);
        if (!response.ok) throw new Error('Failed to load points data');
        
        const data = await response.json();
        
        // Update chart
        const chart = Chartist.instances['.ct-chart-points'];
        chart.update({
            labels: data.labels,
            series: [data.points]
        });

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
