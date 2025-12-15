// File upload handling
class FileUploader {
    constructor() {
        this.uploadArea = document.getElementById('upload-area');
        this.fileInput = document.getElementById('file-input');
        this.fileInfo = document.getElementById('file-info');
        this.uploadBtn = document.getElementById('upload-btn');
        this.selectedFile = null;
        this.selectedLanguage = 'eng';
        
        this.init();
    }
    
    init() {
        // Language selection
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.selectedLanguage = e.target.dataset.lang;
            });
        });
        
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files[0]);
        });
        
        // Drag and drop
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });
        
        this.uploadArea.addEventListener('dragleave', () => {
            this.uploadArea.classList.remove('dragover');
        });
        
        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });
        
        // Click to upload
        this.uploadArea.addEventListener('click', () => {
            this.fileInput.click();
        });
        
        // Upload button
        this.uploadBtn.addEventListener('click', () => {
            this.uploadFile();
        });
    }
    
    handleFileSelect(file) {
        if (!file) return;
        
        // Validate file type
        const validTypes = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf'];
        if (!validTypes.includes(file.type)) {
            this.showError('Please upload a PDF or image file (JPEG, PNG)');
            return;
        }
        
        // Validate file size (50MB max)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showError('File size must be less than 50MB');
            return;
        }
        
        this.selectedFile = file;
        this.displayFileInfo(file);
        this.uploadBtn.disabled = false;
    }
    
    displayFileInfo(file) {
        const fileSize = (file.size / 1024 / 1024).toFixed(2);
        const fileType = file.type.split('/')[1].toUpperCase();
        
        this.fileInfo.innerHTML = `
            <div style="margin-top: 1rem;">
                <strong>Selected:</strong> ${file.name}<br>
                <strong>Type:</strong> ${fileType}<br>
                <strong>Size:</strong> ${fileSize} MB
            </div>
        `;
    }
    
    async uploadFile() {
        if (!this.selectedFile) {
            this.showError('Please select a file first');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('language', this.selectedLanguage);
        formData.append('run_table_ocr', 'true');
        formData.append('enable_multistage', 'true');
        
        // Show loading
        this.showLoading();
        this.uploadBtn.disabled = true;
        
        try {
            const token = localStorage.getItem('auth_token');
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            
            const response = await fetch('/api/ocr/extract', {
                method: 'POST',
                headers: headers,
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }
            
            const result = await response.json();
            this.hideLoading();
            
            // Store result and file info
            sessionStorage.setItem('extraction_result', JSON.stringify(result));
            sessionStorage.setItem('uploaded_file', JSON.stringify({
                name: this.selectedFile.name,
                type: this.selectedFile.type,
                size: this.selectedFile.size
            }));
            window.location.href = '/extraction';
            
        } catch (error) {
            this.hideLoading();
            this.showError(error.message || 'Failed to upload file');
            this.uploadBtn.disabled = false;
        }
    }
    
    showLoading() {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading" style="margin: 0 auto 1rem;"></div>
                <p>Processing document...</p>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
    
    showError(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-error';
        alert.textContent = message;
        
        const container = document.querySelector('.container');
        container.insertBefore(alert, container.firstChild);
        
        setTimeout(() => alert.remove(), 5000);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new FileUploader();
});

