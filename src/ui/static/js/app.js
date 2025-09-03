// Compliance Kit - Frontend JavaScript

// Global configuration
const ComplianceKit = {
    config: {
        apiBase: '/api',
        wsUrl: window.location.protocol === 'https:' ? 'wss://' : 'ws://' + window.location.host + '/ws'
    },
    
    // Utility functions
    utils: {
        // Format file size
        formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },
        
        // Format date
        formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },
        
        // Show toast notification
        showToast(message, type = 'info') {
            const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
            const toast = this.createToast(message, type);
            toastContainer.appendChild(toast);
            
            // Auto-remove after delay
            setTimeout(() => {
                toast.remove();
            }, 5000);
        },
        
        createToastContainer() {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
            return container;
        },
        
        createToast(message, type) {
            const toast = document.createElement('div');
            toast.className = `toast show align-items-center text-white bg-${type} border-0`;
            toast.role = 'alert';
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="this.parentElement.parentElement.remove()"></button>
                </div>
            `;
            return toast;
        },
        
        // Copy to clipboard
        async copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                this.showToast('Copied to clipboard', 'success');
            } catch (err) {
                this.showToast('Failed to copy to clipboard', 'danger');
            }
        },
        
        // Debounce function
        debounce(func, wait) {
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
    },
    
    // API client
    api: {
        async request(endpoint, options = {}) {
            const url = ComplianceKit.config.apiBase + endpoint;
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                },
            };
            
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                throw new Error(`API request failed: ${response.statusText}`);
            }
            
            return response.json();
        },
        
        async get(endpoint) {
            return this.request(endpoint);
        },
        
        async post(endpoint, data) {
            return this.request(endpoint, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },
        
        async put(endpoint, data) {
            return this.request(endpoint, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },
        
        async delete(endpoint) {
            return this.request(endpoint, {
                method: 'DELETE'
            });
        }
    },
    
    // Form handling
    forms: {
        // Serialize form data to JSON
        serialize(form) {
            const formData = new FormData(form);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                if (data[key]) {
                    // Handle multiple values (convert to array)
                    if (Array.isArray(data[key])) {
                        data[key].push(value);
                    } else {
                        data[key] = [data[key], value];
                    }
                } else {
                    data[key] = value;
                }
            }
            
            return data;
        },
        
        // Reset form and show success message
        handleSuccess(form, message) {
            form.reset();
            ComplianceKit.utils.showToast(message, 'success');
        },
        
        // Show form errors
        handleError(form, error) {
            ComplianceKit.utils.showToast(error.message || 'Form submission failed', 'danger');
        }
    },
    
    // Initialize the application
    init() {
        console.log('Compliance Kit initialized');
        
        // Setup HTMX event handlers
        this.setupHTMXHandlers();
        
        // Setup global error handling
        this.setupErrorHandling();
        
        // Setup tooltips
        this.setupTooltips();
        
        // Auto-refresh status indicators
        this.startStatusUpdates();
    },
    
    setupHTMXHandlers() {
        // Handle successful form submissions
        document.body.addEventListener('htmx:afterRequest', (event) => {
            if (event.detail.successful) {
                const form = event.target.closest('form');
                if (form) {
                    // Check if response indicates success
                    if (event.detail.xhr.status === 200 || event.detail.xhr.status === 201) {
                        ComplianceKit.utils.showToast('Operation completed successfully', 'success');
                        
                        // Close modal if form is in a modal
                        const modal = form.closest('.modal');
                        if (modal) {
                            const modalInstance = bootstrap.Modal.getInstance(modal);
                            if (modalInstance) {
                                modalInstance.hide();
                            }
                        }
                    }
                }
            }
        });
        
        // Handle HTMX errors
        document.body.addEventListener('htmx:responseError', (event) => {
            ComplianceKit.utils.showToast('Request failed. Please try again.', 'danger');
        });
        
        // Handle network errors
        document.body.addEventListener('htmx:sendError', (event) => {
            ComplianceKit.utils.showToast('Network error. Please check your connection.', 'danger');
        });
    },
    
    setupErrorHandling() {
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
            // Don't show user notification for script errors in production
            if (window.location.hostname === 'localhost') {
                ComplianceKit.utils.showToast('A JavaScript error occurred', 'warning');
            }
        });
    },
    
    setupTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    },
    
    startStatusUpdates() {
        // Poll for status updates every 30 seconds
        setInterval(() => {
            const statusElements = document.querySelectorAll('[data-status-url]');
            statusElements.forEach(element => {
                const url = element.dataset.statusUrl;
                htmx.ajax('GET', url, { target: element });
            });
        }, 30000);
    }
};

// File upload enhancements
class FileUploader {
    constructor(dropZone, fileInput) {
        this.dropZone = dropZone;
        this.fileInput = fileInput;
        this.setupEvents();
    }
    
    setupEvents() {
        // Drag and drop
        this.dropZone.addEventListener('dragover', this.handleDragOver.bind(this));
        this.dropZone.addEventListener('dragleave', this.handleDragLeave.bind(this));
        this.dropZone.addEventListener('drop', this.handleDrop.bind(this));
        
        // File input change
        this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));
    }
    
    handleDragOver(e) {
        e.preventDefault();
        this.dropZone.classList.add('dragover');
    }
    
    handleDragLeave(e) {
        if (!this.dropZone.contains(e.relatedTarget)) {
            this.dropZone.classList.remove('dragover');
        }
    }
    
    handleDrop(e) {
        e.preventDefault();
        this.dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFiles(files);
        }
    }
    
    handleFileSelect(e) {
        this.handleFiles(e.target.files);
    }
    
    handleFiles(files) {
        const file = files[0];
        if (!file) return;
        
        // Validate file type
        const allowedTypes = ['.csv', '.xlsx', '.xls', '.pdf', '.json', '.yaml', '.yml'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExt)) {
            ComplianceKit.utils.showToast(`File type ${fileExt} is not allowed`, 'warning');
            return;
        }
        
        // Update UI to show selected file
        this.showFileInfo(file);
        
        // Trigger file analysis
        this.analyzeFile(file);
    }
    
    showFileInfo(file) {
        // Implementation would update UI elements to show file info
        console.log('File selected:', file.name, ComplianceKit.utils.formatFileSize(file.size));
    }
    
    analyzeFile(file) {
        // This would trigger the file analysis via HTMX
        ComplianceKit.utils.showToast('Analyzing file...', 'info');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    ComplianceKit.init();
    
    // Initialize file uploaders if present
    const dropZones = document.querySelectorAll('.drop-zone');
    dropZones.forEach(dropZone => {
        const fileInput = dropZone.querySelector('input[type="file"]');
        if (fileInput) {
            new FileUploader(dropZone, fileInput);
        }
    });
});

// Export for global use
window.ComplianceKit = ComplianceKit;