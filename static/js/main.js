// Main JavaScript functionality for the Copy Trading System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Confirmation dialogs for dangerous actions
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
                return false;
            }
        });
    });

    // Real-time updates for dashboard
    if (window.location.pathname === '/') {
        startRealTimeUpdates();
    }
});

// Real-time updates functionality
function startRealTimeUpdates() {
    setInterval(function() {
        updateTradeStatus();
        updateAccountBalances();
        updateCopierStatus();
        updateApiStatus();
    }, 10000); // Update every 10 seconds
    
    // Update status immediately on page load
    updateCopierStatus();
    updateApiStatus();
}

function updateTradeStatus() {
    // Update trade statuses without full page reload
    const tradeRows = document.querySelectorAll('.trade-row');
    tradeRows.forEach(function(row) {
        const tradeId = row.getAttribute('data-trade-id');
        if (tradeId) {
            fetch(`/api/trade_status/${tradeId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const statusBadge = row.querySelector('.status-badge');
                        if (statusBadge) {
                            statusBadge.textContent = data.status;
                            statusBadge.className = `badge status-badge bg-${getStatusClass(data.status)}`;
                        }
                    }
                })
                .catch(error => console.log('Status update failed:', error));
        }
    });
}

function updateAccountBalances() {
    // Update account balances in real-time
    const balanceElements = document.querySelectorAll('.account-balance');
    balanceElements.forEach(function(element) {
        const accountId = element.getAttribute('data-account-id');
        const accountType = element.getAttribute('data-account-type');
        
        if (accountId && accountType) {
            fetch(`/api/account_balance/${accountType}/${accountId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        element.textContent = `$${data.balance.toFixed(2)}`;
                    }
                })
                .catch(error => console.log('Balance update failed:', error));
        }
    });
}

function updateCopierStatus() {
    // Update trade copier service status
    fetch('/api/copier_status')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('copier-status');
            const descriptionElement = document.getElementById('copier-description');
            
            if (statusElement && descriptionElement) {
                if (data.running) {
                    statusElement.textContent = 'Running';
                    statusElement.className = 'badge bg-success me-2';
                    descriptionElement.textContent = 'Monitoring master accounts for new trades';
                } else {
                    statusElement.textContent = 'Stopped';
                    statusElement.className = 'badge bg-danger me-2';
                    descriptionElement.textContent = 'Trade copying service is not running';
                }
            }
        })
        .catch(error => {
            console.log('Copier status update failed:', error);
            const statusElement = document.getElementById('copier-status');
            const descriptionElement = document.getElementById('copier-description');
            
            if (statusElement && descriptionElement) {
                statusElement.textContent = 'Error';
                statusElement.className = 'badge bg-warning me-2';
                descriptionElement.textContent = 'Unable to check service status';
            }
        });
}

function updateApiStatus() {
    // Update API connections status
    fetch('/api/connections_status')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('api-status');
            const descriptionElement = document.getElementById('api-description');
            
            if (statusElement && descriptionElement) {
                switch(data.status) {
                    case 'all_connected':
                        statusElement.textContent = 'Connected';
                        statusElement.className = 'badge bg-success me-2';
                        descriptionElement.textContent = data.message;
                        break;
                    case 'partial_connected':
                        statusElement.textContent = 'Partial';
                        statusElement.className = 'badge bg-warning me-2';
                        descriptionElement.textContent = data.message;
                        break;
                    case 'none_connected':
                        statusElement.textContent = 'Disconnected';
                        statusElement.className = 'badge bg-danger me-2';
                        descriptionElement.textContent = data.message;
                        break;
                    case 'no_accounts':
                        statusElement.textContent = 'No Accounts';
                        statusElement.className = 'badge bg-secondary me-2';
                        descriptionElement.textContent = data.message;
                        break;
                    case 'error':
                        statusElement.textContent = 'Error';
                        statusElement.className = 'badge bg-warning me-2';
                        descriptionElement.textContent = 'Unable to check API connections';
                        break;
                }
            }
        })
        .catch(error => {
            console.log('API status update failed:', error);
            const statusElement = document.getElementById('api-status');
            const descriptionElement = document.getElementById('api-description');
            
            if (statusElement && descriptionElement) {
                statusElement.textContent = 'Error';
                statusElement.className = 'badge bg-warning me-2';
                descriptionElement.textContent = 'Unable to check API connections';
            }
        });
}

function getStatusClass(status) {
    switch(status.toLowerCase()) {
        case 'executed': return 'success';
        case 'pending': return 'warning';
        case 'failed': return 'danger';
        case 'cancelled': return 'secondary';
        default: return 'secondary';
    }
}

// Form validation
function validateApiCredentials(form) {
    const apiKey = form.querySelector('input[name="api_key"]').value;
    const apiSecret = form.querySelector('input[name="api_secret"]').value;
    
    if (!apiKey || !apiSecret) {
        showAlert('error', 'API Key and Secret are required');
        return false;
    }
    
    if (apiKey.length < 10) {
        showAlert('error', 'API Key appears to be invalid');
        return false;
    }
    
    return true;
}

// Utility function to show alerts
function showAlert(type, message) {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertContainer.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertContainer, container.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(function() {
        const bsAlert = new bootstrap.Alert(alertContainer);
        bsAlert.close();
    }, 5000);
}

// WebSocket connection for real-time updates (if needed)
function initWebSocket() {
    if (typeof WebSocket !== 'undefined') {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('WebSocket connected');
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
        
        ws.onclose = function() {
            console.log('WebSocket disconnected');
            // Try to reconnect after 5 seconds
            setTimeout(initWebSocket, 5000);
        };
        
        ws.onerror = function(error) {
            console.log('WebSocket error:', error);
        };
    }
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'new_trade':
            showAlert('info', `New trade detected: ${data.symbol} ${data.side}`);
            break;
        case 'trade_copied':
            showAlert('success', `Trade copied to ${data.followers} followers`);
            break;
        case 'trade_failed':
            showAlert('error', `Trade copy failed: ${data.error}`);
            break;
        default:
            console.log('Unknown message type:', data.type);
    }
}

// Chart functionality for trade analytics
function initTradeChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (ctx) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Trades',
                    data: data.values,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Trade Activity'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Export functionality
function exportTradesToCSV() {
    const table = document.querySelector('.trades-table');
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [];
        const cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            row.push(cols[j].innerText);
        }
        
        csv.push(row.join(','));
    }
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', '');
    a.setAttribute('href', url);
    a.setAttribute('download', `trades_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+R to refresh
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        location.reload();
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }
});
