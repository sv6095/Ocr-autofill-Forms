"""
Configuration and utilities for template matching.
Allows loading/saving templates and managing custom field definitions.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from ocr.extraction.template_matcher import TemplateMatcher, FieldTemplate, get_template_matcher
from app.config import BASE_DIR

TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)
DEFAULT_TEMPLATES_FILE = TEMPLATES_DIR / "field_templates.json"


def save_templates_to_file(file_path: Optional[str] = None):
    """Save current templates to file."""
    if file_path is None:
        file_path = str(DEFAULT_TEMPLATES_FILE)
    
    matcher = get_template_matcher()
    matcher.save_templates(file_path)
    print(f"Templates saved to: {file_path}")


def load_templates_from_file(file_path: Optional[str] = None):
    """Load templates from file."""
    if file_path is None:
        file_path = str(DEFAULT_TEMPLATES_FILE)
    
    if not Path(file_path).exists():
        print(f"Template file not found: {file_path}")
        return False
    
    matcher = get_template_matcher()
    matcher.load_templates(file_path)
    print(f"Templates loaded from: {file_path}")
    return True


def add_document_type_template(
    doc_type: str,
    field_definitions: Dict[str, Dict]
):
    """
    Add field templates for a specific document type.
    
    Args:
        doc_type: Document type name (e.g., "aadhaar", "passport")
        field_definitions: Dictionary mapping field names to their definitions
            Example: {
                "aadhaar_number": {
                    "patterns": [r"aadhaar\s*[:]\s*"],
                    "value_patterns": [r"(\d{4}\s?\d{4}\s?\d{4})"],
                    "synonyms": ["uid", "aadhar"]
                }
            }
    """
    matcher = get_template_matcher()
    
    for field_name, definition in field_definitions.items():
        template = FieldTemplate(
            name=field_name,
            patterns=definition.get("patterns", []),
            value_patterns=definition.get("value_patterns", []),
            synonyms=definition.get("synonyms", []),
            required=definition.get("required", False),
            confidence_threshold=definition.get("confidence_threshold", 0.7)
        )
        matcher.add_template(template)
    
    print(f"Added {len(field_definitions)} field templates for document type: {doc_type}")


def export_template_schema() -> Dict:
    """Export current template schema for documentation."""
    matcher = get_template_matcher()
    schema = {
        "fields": {},
        "total_fields": len(matcher.templates)
    }
    
    for field_name, template in matcher.templates.items():
        schema["fields"][field_name] = {
            "patterns_count": len(template.patterns),
            "value_patterns_count": len(template.value_patterns),
            "synonyms": template.synonyms,
            "required": template.required
        }
    
    return schema

