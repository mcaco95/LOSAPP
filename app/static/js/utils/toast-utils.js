const Toast = {
    init() {
        this.container = document.querySelector('.toast-container');
    },
    
    show(message, type = 'success') {
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'error' ? 'bg-danger' : 
                      type === 'warning' ? 'bg-warning' : 
                      type === 'info' ? 'bg-info' : 'bg-success';
        const icon = type === 'error' ? 'fas fa-times-circle' :
                   type === 'warning' ? 'fas fa-exclamation-circle' :
                   type === 'info' ? 'fas fa-info-circle' : 'fas fa-check-circle';
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center ${bgClass} text-white border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="${icon} me-2"></i>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        this.container.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
        toast.show();
        
        // Remove toast from DOM after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    },
    
    success(message) {
        this.show(message, 'success');
    },
    
    error(message) {
        this.show(message, 'error');
    },
    
    warning(message) {
        this.show(message, 'warning');
    },
    
    info(message) {
        this.show(message, 'info');
    }
};

// Initialize toast system
document.addEventListener('DOMContentLoaded', () => {
    Toast.init();
}); 