// Points & Rewards Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Points Chart
    if(document.querySelector('.ct-chart-points')) {
        const pointsData = {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            series: [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]
        };

        // Create a new Chartist Line chart in the ".ct-chart-points" element
        new Chartist.Line('.ct-chart-points', pointsData, {
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

        // Load initial points data
        loadPointsData('month'); // Default to monthly view
    }

    // Points History Period Buttons
    const periodButtons = document.querySelectorAll('.btn-group .btn[data-period]');
    periodButtons.forEach(button => {
        button.addEventListener('click', function() {
            periodButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            loadPointsData(this.getAttribute('data-period'));
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

    // Initialize points trend chart
    if (document.querySelector('.ct-chart-points')) {
        const chartElement = document.querySelector('.ct-chart-points');
        const trendData = JSON.parse(chartElement.dataset.trend || '{"labels":[], "series":[[]]}');

        const options = {
            height: 400,
            fullWidth: true,
            chartPadding: {
                top: 40,
                right: 30,
                bottom: 30,
                left: 50
            },
            lineSmooth: Chartist.Interpolation.monotoneCubic({
                fillHoles: false
            }),
            low: 0,
            showArea: true,
            showPoint: true,
            showLine: true,
            axisX: {
                showGrid: false,
                labelOffset: {
                    x: -5,
                    y: 0
                },
                labelInterpolationFnc: function(value) {
                    return value.length > 10 ? value.slice(0, 10) + '...' : value;
                }
            },
            axisY: {
                onlyInteger: true,
                offset: 40,
                labelInterpolationFnc: function(value) {
                    if (value >= 1000) {
                        return (value / 1000).toFixed(1) + 'k';
                    }
                    return value;
                },
                scaleMinSpace: 40
            },
            plugins: [
                Chartist.plugins.tooltip({
                    appendToBody: true,
                    class: 'points-chart-tooltip',
                    transformTooltipTextFnc: function(value) {
                        return value + ' points';
                    }
                }),
                Chartist.plugins.ctPointLabels({
                    textAnchor: 'middle',
                    labelInterpolationFnc: function(value) {
                        if (value === 0) return '';
                        if (value >= 1000) {
                            return (value / 1000).toFixed(1) + 'k';
                        }
                        return value;
                    }
                })
            ]
        };

        // Create gradient for the area
        const defs = [
            '<defs>',
                '<linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">',
                    '<stop offset="0%" stop-color="rgba(13, 110, 253, 0.2)"/>',
                    '<stop offset="100%" stop-color="rgba(13, 110, 253, 0)"/>',
                '</linearGradient>',
            '</defs>'
        ];

        const chart = new Chartist.Line('.ct-chart-points', trendData, options);

        // Add gradient and styling after chart is created
        chart.on('created', function(context) {
            const svg = context.svg._node;
            svg.insertAdjacentHTML('afterbegin', defs.join(''));

            // Style the chart elements
            context.svg.querySelectorAll('.ct-area').forEach(area => {
                area.style.fill = 'url(#areaGradient)';
            });

            context.svg.querySelectorAll('.ct-line').forEach(line => {
                line.style.stroke = '#0d6efd';
                line.style.strokeWidth = '2px';
            });

            context.svg.querySelectorAll('.ct-point').forEach(point => {
                point.style.stroke = '#0d6efd';
                point.style.strokeWidth = '6px';
                point.style.fill = '#ffffff';
            });
        });

        // Animate the chart on draw
        chart.on('draw', function(data) {
            if(data.type === 'line' || data.type === 'area') {
                data.element.animate({
                    d: {
                        begin: 1000 * data.index,
                        dur: 2000,
                        from: data.path.clone().scale(1, 0).translate(0, data.chartRect.height()).stringify(),
                        to: data.path.clone().stringify(),
                        easing: Chartist.Svg.Easing.easeOutQuint
                    }
                });
            } else if (data.type === 'point') {
                data.element.animate({
                    opacity: {
                        begin: 1000 * data.index,
                        dur: 500,
                        from: 0,
                        to: 1,
                        easing: 'ease'
                    },
                    x1: {
                        begin: 1000 * data.index,
                        dur: 500,
                        from: data.x - 10,
                        to: data.x,
                        easing: 'ease'
                    }
                });
            }
        });

        // Handle period changes
        const periodButtons = document.querySelectorAll('[data-period]');
        periodButtons.forEach(button => {
            button.addEventListener('click', function() {
                periodButtons.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');
                
                const period = this.dataset.period;
                updateChartData(period, chart);
            });
        });
    }

    // Add hover effects to transaction rows
    document.querySelectorAll('.transaction-row').forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(5px)';
            this.style.transition = 'transform 0.2s ease';
        });

        row.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Animate numbers
    const animateValue = (element, start, end, duration) => {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const value = Math.floor(progress * (end - start) + start);
            element.textContent = value.toLocaleString();
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    };

    // Animate all elements with data-count attribute
    document.querySelectorAll('[data-count]').forEach(el => {
        const endValue = parseInt(el.getAttribute('data-count'));
        animateValue(el, 0, endValue, 2000);
    });

    // Add hover effects to reward cards
    document.querySelectorAll('.reward-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px) scale(1.02)';
            this.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.12)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
        });
    });
});

// Load points history data
async function loadPointsData(period) {
    const chartElement = document.querySelector('.ct-chart-points');
    if (!chartElement) return;

    // Add loading state
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chart-loading';
    loadingDiv.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    chartElement.parentElement.appendChild(loadingDiv);

    try {
        const response = await fetch(`/api/v1/points-rewards/points/trend?period=${period}`);
        if (!response.ok) throw new Error('Failed to fetch points data');
        
        const data = await response.json();
        
        // Update chart with new data
        const chart = new Chartist.Line('.ct-chart-points', data, {
            height: 400,
            fullWidth: true,
            chartPadding: {
                top: 40,
                right: 30,
                bottom: 30,
                left: 50
            },
            lineSmooth: Chartist.Interpolation.monotoneCubic({
                fillHoles: false
            }),
            low: 0,
            showArea: true,
            showPoint: true,
            showLine: true,
            axisX: {
                showGrid: false,
                labelOffset: {
                    x: -5,
                    y: 0
                }
            },
            axisY: {
                onlyInteger: true,
                offset: 40,
                labelInterpolationFnc: function(value) {
                    if (value >= 1000) {
                        return (value / 1000).toFixed(1) + 'k';
                    }
                    return value;
                }
            },
            plugins: [
                Chartist.plugins.tooltip({
                    class: 'points-chart-tooltip',
                    transformTooltipTextFnc: function(value) {
                        return value + ' points';
                    }
                })
            ]
        });

        // Add gradient and animations
        chart.on('created', function(context) {
            const defs = [
                '<defs>',
                    '<linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">',
                        '<stop offset="0%" stop-color="rgba(13, 110, 253, 0.2)"/>',
                        '<stop offset="100%" stop-color="rgba(13, 110, 253, 0)"/>',
                    '</linearGradient>',
                '</defs>'
            ];
            
            context.svg._node.insertAdjacentHTML('afterbegin', defs.join(''));
            
            context.svg.querySelectorAll('.ct-area').forEach(area => {
                area.style.fill = 'url(#areaGradient)';
            });

            context.svg.querySelectorAll('.ct-line').forEach(line => {
                line.style.stroke = '#0d6efd';
                line.style.strokeWidth = '2px';
            });

            context.svg.querySelectorAll('.ct-point').forEach(point => {
                point.style.stroke = '#0d6efd';
                point.style.strokeWidth = '6px';
                point.style.fill = '#ffffff';
            });
        });

    } catch (error) {
        console.error('Error loading points data:', error);
        chartElement.innerHTML = `
            <div class="text-center py-4">
                <p class="text-danger mb-2">Failed to load points data</p>
                <button class="btn btn-sm btn-primary" onclick="loadPointsData('${period}')">
                    <i class="fas fa-sync-alt me-1"></i> Retry
                </button>
            </div>`;
    } finally {
        // Remove loading state
        const loadingDiv = chartElement.parentElement.querySelector('.chart-loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
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
        try {
            const distributionDataElement = document.getElementById('distributionData');
            if (!distributionDataElement || !distributionDataElement.textContent.trim()) {
                console.error('Distribution data element is empty or not found');
                return;
            }
            
            const distributionData = JSON.parse(distributionDataElement.textContent);
            console.log('Initial distribution data:', distributionData);
            
            if (!distributionData.labels || !distributionData.series || 
                distributionData.labels.length === 0 || distributionData.series.length === 0) {
                console.error('Distribution data is empty or invalid');
                // Set default data
                distributionData.labels = ['Lead Gen', 'Demo Sched', 'Demo Comp', 'Client Sign', 'Renewed'];
                distributionData.series = [2, 5, 15, 50, 25];
            }
            
            const distributionChart = new Chartist.Bar('.ct-chart-distribution', {
                labels: distributionData.labels,
                series: [distributionData.series]
            }, {
                distributeSeries: true,
                plugins: [
                    Chartist.plugins.tooltip()
                ],
                axisY: {
                    onlyInteger: true
                }
            });
            
            // Connect time period buttons to the chart
            const periodButtons = document.querySelectorAll('.card-header .btn-group .btn');
            periodButtons.forEach(button => {
                button.addEventListener('click', async function() {
                    // Remove active class from all buttons
                    periodButtons.forEach(b => b.classList.remove('active'));
                    // Add active class to clicked button
                    this.classList.add('active');
                    
                    // Get the selected period
                    const period = this.getAttribute('data-period');
                    console.log('Selected period:', period);
                    
                    try {
                        // Fetch distribution data for the selected period
                        const response = await fetch(`/api/v1/points-rewards/points/distribution?period=${period}`);
                        if (!response.ok) throw new Error('Failed to load distribution data');
                        
                        const data = await response.json();
                        console.log('Fetched distribution data:', data);
                        
                        // Ensure we have valid data
                        if (!data.labels || !data.series || 
                            data.labels.length === 0 || data.series.length === 0) {
                            throw new Error('Received empty or invalid data');
                        }
                        
                        // Update chart with new data
                        distributionChart.update({
                            labels: data.labels,
                            series: [data.series]
                        });
                    } catch (error) {
                        console.error('Error loading distribution data:', error);
                        // Show error notification
                        Swal.fire({
                            title: 'Error!',
                            text: 'Failed to load distribution data. Please try again.',
                            icon: 'error',
                            timer: 2000,
                            showConfirmButton: false
                        });
                    }
                });
            });
        } catch (error) {
            console.error('Error initializing distribution chart:', error);
        }
    }
}

// Function to update chart data based on selected period
function updateChartData(period, chart) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chart-loading';
    loadingDiv.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    
    const chartContainer = document.querySelector('.points-trend-chart');
    chartContainer.appendChild(loadingDiv);

    fetch(`/api/v1/points-rewards/trend?period=${period}`)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            chart.update(data);
            loadingDiv.remove();
        })
        .catch(error => {
            console.error('Error fetching trend data:', error);
            chartContainer.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-exclamation-circle mb-2"></i>
                    <p>Failed to load chart data</p>
                    <button class="btn btn-sm btn-primary" onclick="updateChartData('${period}', chart)">
                        Try Again
                    </button>
                </div>
            `;
        });
}

// Redeem reward function
function redeemReward(rewardId) {
    const modal = new bootstrap.Modal(document.getElementById('redeemConfirmation'));
    const confirmButton = document.getElementById('confirmRedeem');
    
    // Store the reward ID
    confirmButton.setAttribute('data-reward-id', rewardId);
    
    // Show confirmation modal
    modal.show();
    
    // Handle confirmation
    confirmButton.onclick = async function() {
        try {
            const response = await fetch('/api/v1/rewards/redeem', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ reward_id: rewardId })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Show success message
                Swal.fire({
                    title: 'Congratulations!',
                    text: 'You have successfully redeemed your reward!',
                    icon: 'success',
                    confirmButtonText: 'Continue'
                }).then(() => {
                    // Reload page to update status
                    window.location.reload();
                });
            } else {
                throw new Error(result.message || 'Failed to redeem reward');
            }
        } catch (error) {
            Swal.fire({
                title: 'Oops!',
                text: error.message || 'Something went wrong',
                icon: 'error',
                confirmButtonText: 'Try Again'
            });
        } finally {
            modal.hide();
        }
    };
}

// Add smooth scroll animation when reward cards appear in viewport
const observeElements = () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.reward-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(card);
    });
};

// Initialize animations when document is ready
document.addEventListener('DOMContentLoaded', observeElements);
