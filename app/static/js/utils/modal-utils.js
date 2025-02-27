/**
 * Modal Utilities
 * 
 * This file contains utility functions for handling Bootstrap modals
 * to ensure consistent behavior across the application.
 */

const ModalUtils = {
    /**
     * Initialize all modals on the page with proper z-index and event handlers
     */
    init: function() {
        // Set proper z-index for existing backdrops
        const modalBackdrop = document.querySelector('.modal-backdrop');
        if (modalBackdrop) {
            modalBackdrop.style.zIndex = '1040';
        }
        
        // Process all modals on the page
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            // Set proper z-index
            modal.style.zIndex = '1050';
            
            // Set proper z-index for modal dialog
            const dialog = modal.querySelector('.modal-dialog');
            if (dialog) {
                dialog.style.zIndex = '1050';
            }
            
            // Set proper z-index for modal content
            const content = modal.querySelector('.modal-content');
            if (content) {
                content.style.zIndex = '1051';
            }
            
            // Add show event handler
            this._addShowEventHandler(modal);
            
            // Add hidden event handler
            this._addHiddenEventHandler(modal);
        });
        
        // Add handlers for close buttons
        this._addCloseButtonHandlers();
        
        // Add handlers for ESC key and clicking outside modal
        this._addGlobalHandlers();
    },
    
    /**
     * Add show event handler to a modal
     * @param {HTMLElement} modal - The modal element
     */
    _addShowEventHandler: function(modal) {
        modal.addEventListener('show.bs.modal', function() {
            // Create backdrop if it doesn't exist
            if (!document.querySelector('.modal-backdrop')) {
                const backdrop = document.createElement('div');
                backdrop.className = 'modal-backdrop fade show';
                backdrop.style.zIndex = '1040';
                document.body.appendChild(backdrop);
            }
            
            // Ensure modal has proper z-index when shown
            this.style.zIndex = '1050';
            
            const dialog = this.querySelector('.modal-dialog');
            if (dialog) {
                dialog.style.zIndex = '1050';
            }
            
            const content = this.querySelector('.modal-content');
            if (content) {
                content.style.zIndex = '1051';
            }
            
            // Ensure buttons have proper z-index
            const buttons = this.querySelectorAll('.btn');
            buttons.forEach(function(button) {
                button.style.zIndex = '1052';
            });
        });
    },
    
    /**
     * Add hidden event handler to a modal
     * @param {HTMLElement} modal - The modal element
     */
    _addHiddenEventHandler: function(modal) {
        modal.addEventListener('hidden.bs.modal', function() {
            // Remove backdrop when modal is hidden
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
            
            // Remove modal-open class from body
            document.body.classList.remove('modal-open');
            
            // Reset body styles
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        });
    },
    
    /**
     * Add handlers for close buttons
     */
    _addCloseButtonHandlers: function() {
        const closeButtons = document.querySelectorAll('[data-bs-dismiss="modal"]');
        closeButtons.forEach(function(button) {
            button.addEventListener('click', function() {
                const modalElement = this.closest('.modal');
                if (!modalElement) return;
                
                const modalId = modalElement.id;
                if (!modalId) return;
                
                const modalInstance = bootstrap.Modal.getInstance(document.getElementById(modalId));
                if (modalInstance) {
                    modalInstance.hide();
                    
                    // Manually remove backdrop after a short delay
                    setTimeout(function() {
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) {
                            backdrop.remove();
                        }
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                        document.body.style.paddingRight = '';
                    }, 150);
                }
            });
        });
    },
    
    /**
     * Add global handlers for ESC key and clicking outside modal
     */
    _addGlobalHandlers: function() {
        // Handle ESC key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                setTimeout(function() {
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) {
                        backdrop.remove();
                    }
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = '';
                    document.body.style.paddingRight = '';
                }, 150);
            }
        });
        
        // Handle clicking outside modal
        document.addEventListener('click', function(event) {
            if (event.target.classList.contains('modal')) {
                setTimeout(function() {
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) {
                        backdrop.remove();
                    }
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = '';
                    document.body.style.paddingRight = '';
                }, 150);
            }
        });
    },
    
    /**
     * Clean up any lingering modal artifacts
     * Call this function if you notice any modal backdrops or body classes persisting
     */
    cleanupModalArtifacts: function() {
        // Remove any lingering backdrops
        const backdrops = document.querySelectorAll('.modal-backdrop');
        backdrops.forEach(backdrop => backdrop.remove());
        
        // Remove modal-open class from body
        document.body.classList.remove('modal-open');
        
        // Reset body styles
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }
};

// Initialize modals when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Skip initialization for pages with custom modal handling
    if (window.location.pathname.includes('/dashboard/admin/companies')) {
        console.log('Admin companies page detected - using page-specific modal handling');
        return;
    }
    
    // Initialize modals
    ModalUtils.init();
});

// Export the ModalUtils object for use in other scripts
window.ModalUtils = ModalUtils; 