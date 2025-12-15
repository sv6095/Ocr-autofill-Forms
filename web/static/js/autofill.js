// Auto-Fill Form JavaScript
let currentFile = null;
let currentLanguage = 'eng';
let extractedData = null;
let verificationResults = null;

// Field mapping: form field ID -> possible extracted field names
const fieldMapping = {
    'name': ['name', 'full_name', 'applicant_name', 'person_name'],
    'address': ['address', 'addr', 'residential_address', 'home_address'],
    'phone': ['phone', 'mobile', 'contact_number', 'phone_number', 'telephone'],
    'email': ['email', 'e-mail', 'email_address'],
    'date_of_birth': ['date_of_birth', 'dob', 'birth_date', 'birthdate'],
    'id_number': ['id_number', 'id', 'id_no', 'document_number', 'identification_number'],
    'aadhaar_number': ['aadhaar_number', 'aadhaar', 'aadhar', 'uid'],
    'pan_number': ['pan_number', 'pan', 'pan_card'],
    'passport_number': ['passport_number', 'passport', 'passport_no'],
    'license_number': ['license_number', 'license', 'licence', 'driving_license', 'dl', 'drl'],
    'gender': ['gender', 'sex'],
    'nationality': ['nationality', 'country'],
    'occupation': ['occupation', 'profession', 'job', 'work'],
    'city': ['city'],
    'state': ['state', 'province'],
    'zip_code': ['zip_code', 'zip', 'postal_code', 'pincode'],
    'emergency_contact': ['emergency_contact', 'emergency', 'emergency_phone'],
    'blood_group': ['blood_group', 'blood_type', 'blood'],
    'marital_status': ['marital_status', 'marriage_status'],
    'father_name': ['father_name', 'father', 'fathers_name']
};

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initializeUpload();
    initializeLanguageSelector();
    initializeTabs();
    initializeButtons();
});

// Initialize file upload
function initializeUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const extractBtn = document.getElementById('extract-btn');
    const verifyBtn = document.getElementById('verify-btn');
    const previewContainer = document.getElementById('document-preview-container');
    const preview = document.getElementById('document-preview');

    // Click to upload
    uploadArea.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        // Validate file type
        const validTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
        if (!validTypes.includes(file.type)) {
            showAlert('Please upload a PDF, JPEG, or PNG file.', 'error');
            return;
        }

        // Validate file size (50MB)
        if (file.size > 50 * 1024 * 1024) {
            showAlert('File size must be less than 50MB.', 'error');
            return;
        }

        currentFile = file;
        
        // Show file info
        fileInfo.innerHTML = `
            <div class="alert alert-info">
                <strong>Selected:</strong> ${file.name} (${formatFileSize(file.size)})
            </div>
        `;

        // Show preview for images
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            previewContainer.style.display = 'none';
        }

        // Enable buttons
        extractBtn.disabled = false;
        verifyBtn.disabled = false;
    }
}

// Initialize language selector
function initializeLanguageSelector() {
    const langButtons = document.querySelectorAll('.lang-btn');
    langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            langButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentLanguage = btn.dataset.lang;
        });
    });
}

// Initialize tabs
function initializeTabs() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            // Update tab buttons
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Update tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${targetTab}-tab`) {
                    content.classList.add('active');
                }
            });
        });
    });
}

// Initialize buttons
function initializeButtons() {
    const extractBtn = document.getElementById('extract-btn');
    const verifyBtn = document.getElementById('verify-btn');
    const clearBtn = document.getElementById('clear-btn');

    extractBtn.addEventListener('click', handleExtract);
    verifyBtn.addEventListener('click', handleVerify);
    clearBtn.addEventListener('click', handleClear);
}

// Handle extraction and auto-fill
async function handleExtract() {
    if (!currentFile) {
        showAlert('Please select a file first.', 'error');
        return;
    }

    const extractBtn = document.getElementById('extract-btn');
    const extractBtnText = document.getElementById('extract-btn-text');
    const extractLoading = document.getElementById('extract-loading');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    // Show loading
    extractBtn.disabled = true;
    extractBtnText.textContent = 'Extracting...';
    extractLoading.style.display = 'inline-block';
    progressContainer.style.display = 'block';
    progressFill.style.width = '20%';
    progressText.textContent = 'Uploading document...';

    try {
        // Create form data
        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('language', currentLanguage);
        formData.append('run_table_ocr', 'true');
        formData.append('enable_multistage', 'true');
        formData.append('handwriting_mode', 'auto');

        progressFill.style.width = '40%';
        progressText.textContent = 'Processing OCR...';

        // Call API
        const response = await fetch('/api/ocr/extract', {
            method: 'POST',
            body: formData
        });

        progressFill.style.width = '70%';
        progressText.textContent = 'Extracting fields...';

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Extraction failed');
        }

        const data = await response.json();
        extractedData = data;

        progressFill.style.width = '90%';
        progressText.textContent = 'Auto-filling form...';

        // Auto-fill form with confidence scores
        autoFillForm(data.fields || {}, data.field_confidences || {});

        progressFill.style.width = '100%';
        progressText.textContent = 'Complete!';

        // Show extracted text
        const extractedTextDiv = document.getElementById('extracted-text');
        if (data.raw_text) {
            extractedTextDiv.textContent = data.raw_text;
            extractedTextDiv.style.display = 'block';
        }

        // Show success message with confidence info
        const fieldCount = Object.keys(data.fields || {}).length;
        const avgConfidence = data.field_confidences ? 
            (Object.values(data.field_confidences).reduce((a, b) => a + b, 0) / fieldCount * 100).toFixed(1) : 
            'N/A';
        showAlert(`Successfully extracted ${fieldCount} fields from document. Average confidence: ${avgConfidence}%`, 'success');

        // Hide progress after delay
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 2000);

    } catch (error) {
        console.error('Extraction error:', error);
        showAlert(`Extraction failed: ${error.message}`, 'error');
        progressContainer.style.display = 'none';
    } finally {
        extractBtn.disabled = false;
        extractBtnText.textContent = 'Extract & Auto-Fill';
        extractLoading.style.display = 'none';
    }
}

// Auto-fill form fields with confidence scores
function autoFillForm(fields, confidences = {}) {
    // Normalize field names (lowercase, replace spaces/underscores)
    const normalizedFields = {};
    const normalizedConfidences = {};
    
    Object.keys(fields).forEach(key => {
        const normalized = key.toLowerCase().replace(/[\s_-]/g, '_');
        normalizedFields[normalized] = fields[key];
        if (confidences[key] !== undefined) {
            normalizedConfidences[normalized] = confidences[key];
        }
    });

    // Fill each form field
    Object.keys(fieldMapping).forEach(formFieldId => {
        const input = document.getElementById(formFieldId);
        if (!input) return;

        // Try to find matching extracted field
        let value = null;
        let confidence = null;
        let matchedKey = null;
        
        for (const possibleName of fieldMapping[formFieldId]) {
            const normalized = possibleName.toLowerCase().replace(/[\s_-]/g, '_');
            if (normalizedFields[normalized]) {
                value = normalizedFields[normalized];
                confidence = normalizedConfidences[normalized];
                matchedKey = normalized;
                break;
            }
        }

        // Also check direct match
        if (!value && normalizedFields[formFieldId]) {
            value = normalizedFields[formFieldId];
            confidence = normalizedConfidences[formFieldId];
            matchedKey = formFieldId;
        }

        // Fill the field if value found
        if (value) {
            input.value = value;
            input.classList.add('auto-filled');
            
            // Add confidence badge
            if (confidence !== null && confidence !== undefined) {
                // Remove existing confidence badge if any
                const existingBadge = input.parentElement.querySelector('.confidence-badge');
                if (existingBadge) {
                    existingBadge.remove();
                }
                
                // Create confidence badge
                const badge = document.createElement('span');
                badge.className = 'confidence-badge';
                badge.textContent = `${(confidence * 100).toFixed(0)}%`;
                badge.title = `Confidence: ${(confidence * 100).toFixed(1)}%`;
                
                // Color code based on confidence
                if (confidence >= 0.8) {
                    badge.classList.add('confidence-high');
                } else if (confidence >= 0.6) {
                    badge.classList.add('confidence-medium');
                } else {
                    badge.classList.add('confidence-low');
                }
                
                // Insert badge after input
                input.parentElement.appendChild(badge);
            }
            
            // Remove auto-filled class after user edits
            input.addEventListener('input', function() {
                this.classList.remove('auto-filled');
                const badge = this.parentElement.querySelector('.confidence-badge');
                if (badge) badge.remove();
            }, { once: true });
        }
    });
}

// Handle verification
async function handleVerify() {
    if (!currentFile) {
        showAlert('Please select a file first.', 'error');
        return;
    }

    // Collect form data
    const formData = new FormData();
    formData.append('file', currentFile);
    formData.append('language', currentLanguage);
    formData.append('run_table_ocr', 'true');
    formData.append('handwriting_mode', 'auto');

    // Get all form field values
    const fields = {};
    Object.keys(fieldMapping).forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (input && input.value.trim()) {
            fields[fieldId] = input.value.trim();
        }
    });

    formData.append('fields_json', JSON.stringify(fields));

    const verifyBtn = document.getElementById('verify-btn');
    const verifyBtnText = document.getElementById('verify-btn-text');
    const verifyLoading = document.getElementById('verify-loading');

    // Show loading
    verifyBtn.disabled = true;
    verifyBtnText.textContent = 'Verifying...';
    verifyLoading.style.display = 'inline-block';

    try {
        // Call verification API
        const response = await fetch('/api/ocr/verify', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Verification failed');
        }

        const data = await response.json();
        verificationResults = data;

        // Display verification results
        displayVerificationResults(data);

        showAlert('Verification complete!', 'success');

    } catch (error) {
        console.error('Verification error:', error);
        showAlert(`Verification failed: ${error.message}`, 'error');
    } finally {
        verifyBtn.disabled = false;
        verifyBtnText.textContent = 'Verify Data';
        verifyLoading.style.display = 'none';
    }
}

// Display verification results
function displayVerificationResults(data) {
    const resultsContainer = document.getElementById('verification-results');
    const emptyContainer = document.getElementById('verification-empty');
    const statsContainer = document.getElementById('verification-stats');

    if (!data.field_results || data.field_results.length === 0) {
        emptyContainer.style.display = 'block';
        resultsContainer.innerHTML = '';
        statsContainer.style.display = 'none';
        return;
    }

    emptyContainer.style.display = 'none';
    statsContainer.style.display = 'grid';

    // Calculate statistics
    let matchCount = 0;
    let partialCount = 0;
    let mismatchCount = 0;
    let totalSimilarity = 0;

    data.field_results.forEach(result => {
        if (result.status === 'match') matchCount++;
        else if (result.status === 'partial') partialCount++;
        else if (result.status === 'mismatch') mismatchCount++;
        totalSimilarity += result.similarity || 0;
    });

    const avgConfidence = data.field_results.length > 0 
        ? Math.round((totalSimilarity / data.field_results.length) * 100) 
        : 0;

    // Update stats
    document.getElementById('match-count').textContent = matchCount;
    document.getElementById('partial-count').textContent = partialCount;
    document.getElementById('mismatch-count').textContent = mismatchCount;
    document.getElementById('confidence-score').textContent = `${avgConfidence}%`;

    // Display field results
    resultsContainer.innerHTML = '';

    data.field_results.forEach(result => {
        const item = document.createElement('div');
        item.className = `verification-item ${result.status}`;

        const statusLabels = {
            'match': '✓ Match',
            'partial': '⚠ Partial',
            'mismatch': '✗ Mismatch',
            'not_found': '? Not Found'
        };

        const statusColors = {
            'match': 'var(--success-color)',
            'partial': 'var(--warning-color)',
            'mismatch': 'var(--error-color)',
            'not_found': 'var(--secondary-color)'
        };

        item.innerHTML = `
            <div class="verification-header">
                <span class="verification-field-name">${formatFieldName(result.field)}</span>
                <span class="status-badge status-${result.status}">${statusLabels[result.status] || result.status}</span>
            </div>
            <div class="verification-values">
                <div class="verification-value">
                    <div class="verification-label">Submitted Value</div>
                    <div class="verification-text">${escapeHtml(result.submitted || 'N/A')}</div>
                </div>
                <div class="verification-value">
                    <div class="verification-label">Extracted Value</div>
                    <div class="verification-text">${escapeHtml(result.extracted || 'N/A')}</div>
                </div>
            </div>
            ${result.similarity !== undefined ? `
                <div class="similarity-score">
                    Similarity: ${Math.round(result.similarity * 100)}%
                </div>
            ` : ''}
        `;

        resultsContainer.appendChild(item);
    });

    // Update form field styles based on verification
    data.field_results.forEach(result => {
        const input = document.getElementById(result.field);
        if (input) {
            input.classList.remove('verified', 'warning', 'error');
            if (result.status === 'match') {
                input.classList.add('verified');
            } else if (result.status === 'partial') {
                input.classList.add('warning');
            } else if (result.status === 'mismatch') {
                input.classList.add('error');
            }
        }
    });
}

// Handle clear form
function handleClear() {
    if (confirm('Are you sure you want to clear all form fields?')) {
        const form = document.getElementById('autofill-form');
        form.reset();
        
        // Remove all classes
        document.querySelectorAll('.form-field input, .form-field select, .form-field textarea').forEach(input => {
            input.classList.remove('auto-filled', 'verified', 'warning', 'error');
        });

        // Clear verification results
        document.getElementById('verification-results').innerHTML = '';
        document.getElementById('verification-empty').style.display = 'block';
        document.getElementById('verification-stats').style.display = 'none';
        document.getElementById('extracted-text').style.display = 'none';
        
        // Clear file
        currentFile = null;
        extractedData = null;
        verificationResults = null;
        
        document.getElementById('file-info').innerHTML = '';
        document.getElementById('document-preview-container').style.display = 'none';
        document.getElementById('extract-btn').disabled = true;
        document.getElementById('verify-btn').disabled = true;
        
        showAlert('Form cleared.', 'success');
    }
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatFieldName(fieldName) {
    return fieldName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showAlert(message, type = 'info') {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert-toast');
    existingAlerts.forEach(alert => alert.remove());

    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-toast`;
    alert.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        min-width: 300px;
        max-width: 500px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    `;
    alert.textContent = message;

    document.body.appendChild(alert);

    // Auto remove after 5 seconds
    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity 0.3s';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

