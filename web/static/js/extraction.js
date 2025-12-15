// Display extraction results and allow editing
class ExtractionDisplay {
    constructor() {
        this.result = null;
        this.editedFields = {};
        this.init();
    }
    
    init() {
        // Load result from session storage
        const resultData = sessionStorage.getItem('extraction_result');
        if (!resultData) {
            this.showError('No extraction result found. Please upload a document first.');
            return;
        }
        
        this.result = JSON.parse(resultData);
        this.displayResults();
        this.setupEventListeners();
    }
    
    displayResults() {
        const container = document.getElementById('results-container');
        if (!container) return;
        
        // Debug: Log the result to console
        console.log('Extraction result:', this.result);
        
        // Display document info
        const language = this.result.language || 'eng';
        const pages = this.result.pages || 0;
        const availableFields = this.result.available_fields || [];
        
        const infoHtml = `
            <div class="card">
                <h3 class="card-title">Document Information</h3>
                <p><strong>Language:</strong> ${language.toUpperCase()}</p>
                <p><strong>Pages:</strong> ${pages}</p>
                <p><strong>Available Fields:</strong> ${availableFields.length}</p>
            </div>
        `;
        
        // Display extracted fields
        const fieldsHtml = this.buildFieldsHtml();
        
        // Display raw text
        const rawText = this.result.raw_text || '';
        const rawTextHtml = `
            <div class="card">
                <h3 class="card-title">Raw Extracted Text</h3>
                <textarea readonly style="width: 100%; min-height: 200px; padding: 1rem; border: 1px solid var(--border-color); border-radius: 6px; font-family: monospace;">${this.escapeHtml(rawText)}</textarea>
            </div>
        `;
        
        container.innerHTML = infoHtml + fieldsHtml + rawTextHtml;
    }
    
    buildFieldsHtml() {
        // Debug: Log fields
        console.log('Fields in result:', this.result.fields);
        console.log('Fields type:', typeof this.result.fields);
        console.log('Fields keys:', this.result.fields ? Object.keys(this.result.fields) : 'null');
        
        const fields = this.result.fields || {};
        if (!fields || Object.keys(fields).length === 0) {
            return `
                <div class="card">
                    <h3 class="card-title">Extracted Fields</h3>
                    <p>No fields were extracted from this document.</p>
                    <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.5rem;">
                        Raw text length: ${(this.result.raw_text || '').length} characters
                    </p>
                </div>
            `;
        }
        
        let html = `
            <div class="card">
                <h3 class="card-title">Extracted Fields</h3>
                <p style="margin-bottom: 1rem; color: var(--text-secondary);">
                    Review and edit the extracted fields below. Click "Verify Data" when ready.
                </p>
                <div id="fields-list">
        `;
        
        for (const [fieldName, fieldValue] of Object.entries(fields)) {
            const fieldId = `field-${fieldName}`;
            const displayName = this.formatFieldName(fieldName);
            
            html += `
                <div class="field-item">
                    <div class="field-label">${displayName}:</div>
                    <div class="field-value">
                        <input 
                            type="text" 
                            id="${fieldId}"
                            data-field="${fieldName}"
                            value="${this.escapeHtml(fieldValue)}"
                            class="editable"
                            onchange="extractionDisplay.handleFieldEdit('${fieldName}', this.value)"
                        />
                    </div>
                    <button 
                        class="btn btn-secondary" 
                        onclick="extractionDisplay.clearField('${fieldName}')"
                        style="padding: 0.5rem 1rem;"
                    >
                        Clear
                    </button>
                </div>
            `;
        }
        
        html += `
                </div>
                <div style="margin-top: 1.5rem;">
                    <button class="btn btn-primary" onclick="extractionDisplay.proceedToVerification()">
                        Verify Data
                    </button>
                    <button class="btn btn-secondary" onclick="window.location.href='/'">
                        Upload New Document
                    </button>
                </div>
            </div>
        `;
        
        return html;
    }
    
    formatFieldName(name) {
        return name
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    setupEventListeners() {
        // Store original values
        this.originalFields = { ...this.result.fields };
    }
    
    handleFieldEdit(fieldName, value) {
        this.editedFields[fieldName] = value;
        
        // Update the result
        if (!this.result.fields) {
            this.result.fields = {};
        }
        this.result.fields[fieldName] = value;
    }
    
    clearField(fieldName) {
        const input = document.getElementById(`field-${fieldName}`);
        if (input) {
            input.value = '';
            this.handleFieldEdit(fieldName, '');
        }
    }
    
    proceedToVerification() {
        // Store edited fields
        const allFields = {};
        document.querySelectorAll('[data-field]').forEach(input => {
            const fieldName = input.dataset.field;
            allFields[fieldName] = input.value;
        });
        
        // Update result with all fields
        this.result.fields = allFields;
        sessionStorage.setItem('extraction_result', JSON.stringify(this.result));
        
        // Redirect to verification page
        window.location.href = '/verification';
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
let extractionDisplay;
document.addEventListener('DOMContentLoaded', () => {
    extractionDisplay = new ExtractionDisplay();
});

