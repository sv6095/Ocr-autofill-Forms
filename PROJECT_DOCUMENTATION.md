# OCR Autofill & Verification Tool - Comprehensive Documentation

## 1. Architectural Design & Workflow

### 1.1 Overview
This project is an advanced intelligent Document Processing (IDP) solution designed to automatically extract text from documents (PDFs, Images), identify key-value fields using template matching, and verify extracted data against user-submitted values. It features a hybrid OCR engine approach combining **TrOCR** (Transformer-based OCR) for high-accuracy handwriting recognition and **Tesseract** for printed text.

### 1.2 Architectural Components

The system follows a modular microservices-like architecture within a monolithic FastAPI application:

1.  **API Layer (FastAPI)**:
    *   Handles HTTP requests for extraction and verification.
    *   Manages file uploads and input validation.
    *   Authentication (token-based).

2.  **Core Processing Engine**:
    *   **Pre-processor**: Handles image conversion (PDF to Image), resizing, de-skewing, and contrast adjustment.
    *   **OCR Router**: Intelligently routes image segments to the appropriate OCR engine:
        *   **TrOCR (Microsoft)**: Used for handwritten text and low-quality data.
        *   **Tesseract 5.x**: Used for standard printed text headers and high-contrast forms.
    *   **Table Recognition**: Parses tabular data structure.

3.  **Logic Layer**:
    *   **Field Mapper (Template Matching)**: Uses Regex-based templates to identify fields. Supports partial data mapping (only extracts present fields) and synonym recognition.
    *   **Comparator (Verification)**: Compares OCR results with user-provided JSON data using multiple similarity metrics.

4.  **Frontend (Web Interface)**:
    *   **Tech Stack**: HTML5, Vanilla JS, CSS (Responsive, Glassmorphism).
    *   **Structure**:
        ```
        web/
        ├── static/
        │   ├── css/    # Modern styling with RTL support
        │   └── js/     # Logic for upload, extraction, verification
        └── templates/  # Jinja2 templates (index, extraction, verification)
        ```

### 1.3 Data Flow Structure

1.  **Input**: User uploads a document (PDF/Image) via Web UI or API.
2.  **Ingestion**: File validation (size/type) -> PDF conversion (Poppler).
3.  **Extraction Pipeline**:
    *   **Segmentation**: Text block detection.
    *   **OCR Execution**: Tesseract (Layout) + TrOCR (Handwriting).
    *   **Text Merging**: Consolidation of results.
4.  **Interpretation**: `FieldMapper` identifies keys based on templates.
5.  **Output**: JSON response with extracted text and structured fields.
6.  **Verification**: User reviews/edits fields -> SysOutput: JSON response containing raw text, structured fields, and confidence scores.

---

## 2. Detailed Implementation Logic

This section details the internal workings of the core modules.

### 2.1 OCR Extraction Engine (`ocr/extraction/extractor.py`)
The extraction process is orchestrated by `perform_extraction`.

1.  **File Validation & Ingestion**:
    *   Detects file type (PDF header markers or Image magic bytes).
    *   **PDFs**: Converted to images using `pdf_utils.pdf_to_images` (requires Poppler).
    *   **Images**: Loaded via Pillow; multi-frame images (TIFF/GIF) are split into pages.

2.  **Pre-processing Pipeline**:
    *   Each page image undergoes `preprocess_pipeline`: deskewing, binarization, denoising, and upscaling (for small text).
    *   **Text Type Detection**: Heuristics classify regions as "Handwritten" or "Printed".

3.  **Engine Selection & Execution**:
    *   **English**:
        *   **Primary**: TrOCR (Handwritten model) is attempted first for maximum accuracy.
        *   **Fallback**: If results are poor, it falls back to TrOCR (Printed), then Tesseract.
    *   **Other Languages (Hindi/Arabic)**:
        *   Routes directly to Tesseract with specific language packs (`hin`, `ara`).
    *   **Table Detection**: Separate pass to identify table structures and extract cell content.
    *   **Concurrency**: Pages are processed in parallel using a `ThreadPoolExecutor` to maximize throughput.

### 2.2 Intelligent Field Mapping (`ocr/extraction/field_mapper.py`)
Raw text from OCR is unstructured. The `FieldMapper` structures this data.

1.  **Template Definitions**:
    *   A dictionary `FIELD_TEMPLATES` defines regex patterns for 20+ fields.
    *   *Example*: Phone numbers use patterns like `r"(?:phone|mobile)\s*:?\s*(\d{10})"` and synonyms like `["contact"]`.

2.  **Mapping Process**:
    *   **Pattern Matching**: Scans text for defined regex templates.
    *   **Confidence Scoring**: Assigns scores based on match quality (e.g., valid email format gets +0.1, known OCR errors get -0.2).
    *   **Partial Extraction**: Only fields found in the document are returned; missing fields are omitted (Sparse Object).
    *   **Generic Extraction**: Heuristic fallback to catch "Label: Value" pairs not explicitly defined.

### 2.3 logic Verification Layer (`ocr/verification/comparator.py`)
This module validates user inputs against OCR data.

1.  **Field-Specific Similarity**:
    Instead of generic string matching, different strategies are applied based on field type:
    *   **Names**: Uses `partial_ratio` and `token_sort_ratio` to handle "John Doe" vs "Doe, John" or Middle names.
    *   **Addresses**: Uses `token_set_ratio` to ignore word order and duplicate tokens.
    *   **Numbers (ID/Phone)**: Strict digit-only comparison, ignoring dashes/spaces.

2.  **Scoring & Thresholds**:
    *   **Match**: Similarity ≥ 0.9 (Green)
    *   **Partial**: Similarity ≥ 0.6 (Yellow)
    *   **Mismatch**: Similarity < 0.6 (Red)

3.  **Result**: Returns a field-by-field report and a weighted overall confidence score.

---

## 3. Core Features & Capabilities

### 3.1 Supported Fields (Autofill)
The system is pre-configured to automatically identify and extract the following **20 Form Fields**:

1.  **Full Name**: (`name`, `full_name`, `applicant_name`)
2.  **Address**: Complete address block
3.  **Phone Number**: Mobile/Contact numbers
4.  **Email**: Email addresses
5.  **Date of Birth**: DD-MM-YYYY, YYYY-MM-DD, etc.
6.  **ID Number**: Generic ID numbers
7.  **Aadhaar Number**: Indian UID
8.  **PAN Number**: Indian Tax ID
9.  **Passport Number**
10. **License Number**: Driving License
11. **Gender**
12. **Nationality**
13. **Occupation**
14. **City**
15. **State**
16. **Zip Code**
17. **Emergency Contact**
18. **Blood Group**
19. **Marital Status**
20. **Father's Name**

### 3.2 Visual Indicators
The Web UI provides immediate visual feedback:
*   **Field Status**:
    *   **Blue Background**: Auto-filled field (from OCR).
    *   **Green Border**: Verified Match.
    *   **Yellow Border**: Partial Match (Review needed).
    *   **Red Border**: Mismatch/Error.
*   **Verification Badges**:
    *   **Match (✓)**: Perfect match (Green).
    *   **Partial (⚠)**: High similarity (Yellow).
    *   **Mismatch (✗)**: Significant difference (Red).
    *   **Not Found (?)**: Field missing in document.

---

## 4. Integration, Installation & Usage

### 4.1 Prerequisites
*   **OS**: Windows (current setup) or Linux.
*   **Python**: 3.8+.
*   **Tesseract OCR**: Installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` (Windows).
*   **Poppler**: Required for PDF processing.

### 4.2 Installation Steps

1.  **Clone Requirements**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the Server**:
    ```bash
    uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
    ```
    *Note: `--reload` enables auto-restart on code changes.*

### 4.3 Accessing the Interface
*   **Home/Upload**: `http://localhost:8000/`
*   **Extraction Results**: `http://localhost:8000/extraction`
*   **Verification**: `http://localhost:8000/verification`
*   **API Docs**: `http://localhost:8000/docs`

### 4.4 Troubleshooting
*   **Port 8000 Included**: If busy, run on a different port:
    ```bash
    uvicorn api.app:app --reload --port 8001
    ```
*   **Static Files Not Loading**: Ensure `web/static` directory exists and permissions are correct.
*   **Templates Not Found**: Ensure `jinja2` is installed and `web/templates` exists.

---

## 5. API Documentation

### 5.1 Extract Text
**Endpoint**: `POST /api/ocr/extract`
*   **Purpose**: Upload document -> Get extracted fields.
*   **Inputs**: `file` (PDF/Img), `language` (eng/hin/ara), `handwriting_mode`.
*   **Output**: JSON with `raw_text`, `fields` (key-value), `confidence`.

### 5.2 Verify Data
**Endpoint**: `POST /api/ocr/verify`
*   **Purpose**: Verify user-corrected data against document reality.
*   **Inputs**: `file`, `fields_json` (e.g., `{"name": "John"}`).
*   **Output**: JSON with `overall_confidence`, `field_results` (status: match/partial/mismatch).

---

## 6. Test Scenarios & Strategy

We use the **Voxel51** dataset (`form_understanding_in_noisy_scanned_documents_plus`) to benchmark performance.

### 6.1 Running Tests
```bash
python test_with_huggingface_dataset.py --max_samples 50 --output results.json
```

### 6.2 Test Scenarios
| ID | Scenario | Details | Expected |
| --- | --- | --- | --- |
| **TS_01** | **Clean Digital Form** | High-res PDF | >95% Acc, Perfect Mapping |
| **TS_02** | **Handwritten Note** | Cursive, Scanned | TrOCR Active, >85% Acc |
| **TS_03** | **Noisy/Skewed** | Rotated/Blurry Image | Auto-deskew, Text recovered |
| **TS_04** | **Language Support** | Hindi/Arabic Docs | Correct Language routing |
| **TS_05** | **Partial Data** | Form with empty fields | Only present fields extracted |

### 6.3 Benchmarking
The test script compares multiple engines:
*   **Auto**: Best engine selected per region.
*   **TrOCR**: Printed & Handwritten models.
*   **Tesseract**: Baseline comparison.

