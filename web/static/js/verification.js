// Display verification results
class VerificationDisplay {
    constructor() {
        this.extractionResult = null;
        this.verificationResult = null;
        this.init();
    }
    
    init() {
        // Load extraction result
        const resultData = sessionStorage.getItem('extraction_result');
        if (!resultData) {
            this.showError('No extraction result found. Please upload a document first.');
            return;
        }
        
        this.extractionResult = JSON.parse(resultData);
        
        // Check if verification was already done
        const verificationData = sessionStorage.getItem('verification_result');
        if (verificationData) {
            this.verificationResult = JSON.parse(verificationData);
            this.displayVerificationResults();
        } else {
            // Show form to submit data for verification
            this.displayVerificationForm();
        }
    }
    
    displayVerificationForm() {
        const container = document.getElementById('verification-container');
        if (!container) return;
        
        let html = `
            <div class="card">
                <h3 class="card-title">Submit Data for Verification</h3>
                <p style="margin-bottom: 1.5rem; color: var(--text-secondary);">
                    Enter the correct values for each field. The system will compare them with the extracted values.
                </p>
                <form id="verification-form">
        `;
        
        // Create form fields from extracted fields
        for (const [fieldName, fieldValue] of Object.entries(this.extractionResult.fields || {})) {
            const displayName = this.formatFieldName(fieldName);
            const fieldId = `verify-${fieldName}`;
            
            html += `
                <div class="form-group">
                    <label for="${fieldId}">${displayName}</label>
                    <input 
                        type="text" 
                        id="${fieldId}"
                        name="${fieldName}"
                        value="${this.escapeHtml(fieldValue)}"
                        placeholder="Enter ${displayName.toLowerCase()}"
                    />
                    <small style="color: var(--text-secondary);">
                        Extracted: <em>${this.escapeHtml(fieldValue)}</em>
                    </small>
                </div>
            `;
        }
        
        html += `
                    <div style="margin-top: 1.5rem;">
                        <button type="submit" class="btn btn-primary">Verify Data</button>
                        <button type="button" class="btn btn-secondary" onclick="window.location.href='/extraction'">
                            Back to Extraction
                        </button>
                    </div>
                </form>
            </div>
        `;
        
        container.innerHTML = html;
        
        // Setup form submission
        document.getElementById('verification-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitVerification();
        });
    }
    
    async submitVerification() {
        const form = document.getElementById('verification-form');
        const formData = new FormData(form);
        
        // Get submitted fields
        const submittedFields = {};
        for (const [key, value] of formData.entries()) {
            if (value.trim()) {
                submittedFields[key] = value.trim();
            }
        }
        
        // Get original file from session storage or prompt user
        const fileData = sessionStorage.getItem('uploaded_file');
        if (!fileData) {
            this.showError('File not found. Please upload the document again.');
            return;
        }
        
        // Show loading
        this.showLoading();
        
        try {
            const token = localStorage.getItem('auth_token');
            
            // Create FormData with file and fields
            const verifyFormData = new FormData();
            
            // Reconstruct file from stored data
            const fileInfo = JSON.parse(fileData);
            // Note: In production, you'd store the actual file or use document_id
            // For demo, we'll need to get file from document_id endpoint
            
            // Alternative: Use document_id to get file, then verify
            const documentId = this.extractionResult.document_id;
            if (documentId) {
                // Get file from document endpoint
                const fileResponse = await fetch(`/api/documents/${documentId}/original`, {
                    headers: token ? {'Authorization': `Bearer ${token}`} : {}
                });
                
                if (!fileResponse.ok) {
                    throw new Error('Could not retrieve document file');
                }
                
                const blob = await fileResponse.blob();
                const file = new File([blob], fileInfo.name, { type: fileInfo.type });
                
                verifyFormData.append('file', file);
                verifyFormData.append('fields_json', JSON.stringify(submittedFields));
                verifyFormData.append('language', this.extractionResult.language || 'eng');
                verifyFormData.append('run_table_ocr', 'true');
                
                const verifyResponse = await fetch('/api/ocr/verify', {
                    method: 'POST',
                    headers: token ? {'Authorization': `Bearer ${token}`} : {},
                    body: verifyFormData
                });
                
                if (!verifyResponse.ok) {
                    const error = await verifyResponse.json();
                    throw new Error(error.detail || 'Verification failed');
                }
                
                const result = await verifyResponse.json();
                this.verificationResult = result;
                sessionStorage.setItem('verification_result', JSON.stringify(result));
                this.hideLoading();
                this.displayVerificationResults();
            } else {
                throw new Error('Document ID not found');
            }
            
        } catch (error) {
            this.hideLoading();
            this.showError(error.message || 'Verification failed');
        }
    }
    
    displayVerificationResults() {
        const container = document.getElementById('verification-container');
        if (!container) return;
        
        const result = this.verificationResult;
        
        // Summary
        const summaryHtml = `
            <div class="card">
                <h3 class="card-title">Verification Summary</h3>
                <div class="verification-summary">
                    <div class="summary-card">
                        <div class="summary-value">${(result.overall_confidence * 100).toFixed(1)}%</div>
                        <div class="summary-label">Overall Confidence</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value">${result.field_results?.length || 0}</div>
                        <div class="summary-label">Total Fields</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value">${result.field_results?.filter(f => f.status === 'match').length || 0}</div>
                        <div class="summary-label">Matches</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value">${result.field_results?.filter(f => f.status === 'mismatch').length || 0}</div>
                        <div class="summary-label">Mismatches</div>
                    </div>
                </div>
            </div>
        `;
        
        // Field results
        let fieldsHtml = `
            <div class="card">
                <h3 class="card-title">Field Verification Results</h3>
                <div id="field-results">
        `;
        
        if (result.field_results && result.field_results.length > 0) {
            result.field_results.forEach(field => {
                const statusClass = `status-${field.status}`;
                const similarityPercent = (field.similarity * 100).toFixed(1);
                
                fieldsHtml += `
                    <div class="field-item">
                        <div class="field-label">${this.formatFieldName(field.field)}</div>
                        <div style="flex: 1; margin: 0 1rem;">
                            <div><strong>Submitted:</strong> ${this.escapeHtml(field.submitted)}</div>
                            <div><strong>Extracted:</strong> ${this.escapeHtml(field.extracted || 'N/A')}</div>
                        </div>
                        <div>
                            <span class="status-badge ${statusClass}">${field.status}</span>
                            <div style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">
                                ${similarityPercent}% match
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        
        fieldsHtml += `
                </div>
                <div style="margin-top: 1.5rem;">
                    <button class="btn btn-primary" onclick="window.location.href='/'">
                        Upload New Document
                    </button>
                </div>
            </div>
        `;
        
        container.innerHTML = summaryHtml + fieldsHtml;
    }
    
    formatFieldName(name) {
        return name
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    }
    
    escapeHtml(text) {
        if (!text) return 'N/A';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showLoading() {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading" style="margin: 0 auto 1rem;"></div>
                <p>Verifying data...</p>
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
        const container = document.querySelector('.container');
        const alert = document.createElement('div');
        alert.className = 'alert alert-error';
        alert.textContent = message;
        container.insertBefore(alert, container.firstChild);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new VerificationDisplay();
});

