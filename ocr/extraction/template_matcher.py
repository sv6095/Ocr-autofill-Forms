"""
Template matching for dynamic field identification.
Supports partial data mapping - identifies available fields dynamically
without expecting fixed schemas.
"""
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import json
from pathlib import Path


@dataclass
class FieldTemplate:
    """Template definition for a field."""
    name: str
    patterns: List[str]  # Regex patterns to match field labels
    value_patterns: List[str] = field(default_factory=list)  # Patterns for field values
    synonyms: List[str] = field(default_factory=list)  # Alternative names
    required: bool = False  # Whether field is required
    confidence_threshold: float = 0.7  # Minimum confidence to accept match


@dataclass
class FieldMatch:
    """Result of field matching."""
    field_name: str
    value: str
    confidence: float
    matched_pattern: str
    position: Optional[Tuple[int, int]] = None  # (line_number, char_position)


class TemplateMatcher:
    """
    Template matcher for dynamic field identification.
    Supports partial matching - only extracts fields that are present.
    """
    
    def __init__(self):
        self.templates: Dict[str, FieldTemplate] = {}
        self.field_aliases: Dict[str, str] = {}  # Maps aliases to canonical names
        self.learned_patterns: Dict[str, List[str]] = defaultdict(list)
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Initialize with common field templates."""
        default_templates = [
            FieldTemplate(
                name="name",
                patterns=[
                    r"(?:^|\n)\s*(?:name|full\s+name|applicant\s+name|person\s+name)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:name|full\s+name)\s*[=]\s*",
                    r"name\s+is\s+",
                ],
                value_patterns=[r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"],
                synonyms=["full_name", "applicant_name", "person_name", "fullname"],
                required=False
            ),
            FieldTemplate(
                name="date_of_birth",
                patterns=[
                    r"(?:^|\n)\s*(?:dob|date\s+of\s+birth|d\.o\.b|birth\s+date|birthdate)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:dob|date\s+of\s+birth)\s*[=]\s*",
                ],
                value_patterns=[
                    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(\d{4}[/-]\d{2}[/-]\d{2})",
                ],
                synonyms=["dob", "birth_date", "birthdate", "date_of_birth"],
                required=False
            ),
            FieldTemplate(
                name="id_number",
                patterns=[
                    r"(?:^|\n)\s*(?:id|id\s+no|id\s+number|document\s+number|identification\s+number)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:id|id\s+no)\s*[=]\s*",
                ],
                value_patterns=[
                    r"([A-Z0-9]{8,20})",
                    r"(\d{8,20})",
                ],
                synonyms=["id", "id_no", "id_number", "document_number", "identification_number"],
                required=False
            ),
            FieldTemplate(
                name="email",
                patterns=[
                    r"(?:^|\n)\s*(?:email|e-mail|email\s+address)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:email|e-mail)\s*[=]\s*",
                ],
                value_patterns=[r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"],
                synonyms=["e-mail", "email_address"],
                required=False
            ),
            FieldTemplate(
                name="phone",
                patterns=[
                    r"(?:^|\n)\s*(?:phone|mobile|contact\s+number|phone\s+number)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:phone|mobile)\s*[=]\s*",
                ],
                value_patterns=[
                    r"(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
                    r"(\d{10})",
                ],
                synonyms=["mobile", "contact_number", "phone_number", "telephone"],
                required=False
            ),
            FieldTemplate(
                name="address",
                patterns=[
                    r"(?:^|\n)\s*(?:address|addr|residential\s+address)\s*[:]\s*",
                    r"(?:^|\n)\s*(?:address|addr)\s*[=]\s*",
                ],
                value_patterns=[r"([A-Za-z0-9\s,.-]{10,})"],
                synonyms=["addr", "residential_address", "home_address"],
                required=False
            ),
            FieldTemplate(
                name="aadhaar_number",
                patterns=[
                    r"(?:^|\n)\s*(?:aadhaar|aadhar|aadhaar\s+number|uid)\s*[:]\s*",
                ],
                value_patterns=[
                    r"(\d{4}\s?\d{4}\s?\d{4})",
                    r"(\d{12})",
                ],
                synonyms=["aadhar", "uid", "aadhaar_number"],
                required=False
            ),
            FieldTemplate(
                name="pan_number",
                patterns=[
                    r"(?:^|\n)\s*(?:pan|pan\s+card|pan\s+number)\s*[:]\s*",
                ],
                value_patterns=[r"([A-Z]{5}\d{4}[A-Z])"],
                synonyms=["pan", "pan_card", "pan_number"],
                required=False
            ),
            FieldTemplate(
                name="passport_number",
                patterns=[
                    r"(?:^|\n)\s*(?:passport|passport\s+no|passport\s+number)\s*[:]\s*",
                ],
                value_patterns=[r"([A-Z0-9]{6,12})"],
                synonyms=["passport", "passport_no"],
                required=False
            ),
            FieldTemplate(
                name="license_number",
                patterns=[
                    r"(?:^|\n)\s*(?:license|licence|driving\s+license|dl\s+no)\s*[:]\s*",
                ],
                value_patterns=[r"([A-Z0-9]{8,20})"],
                synonyms=["driving_license", "dl", "drl"],
                required=False
            ),
        ]
        
        for template in default_templates:
            self.add_template(template)
    
    def add_template(self, template: FieldTemplate):
        """Add a field template."""
        self.templates[template.name] = template
        
        # Register synonyms
        for synonym in template.synonyms:
            self.field_aliases[synonym.lower()] = template.name
    
    def learn_pattern(self, field_name: str, pattern: str):
        """Learn a new pattern for a field from examples."""
        if field_name not in self.templates:
            # Create a new template if it doesn't exist
            self.templates[field_name] = FieldTemplate(
                name=field_name,
                patterns=[],
                synonyms=[]
            )
        
        if pattern not in self.learned_patterns[field_name]:
            self.learned_patterns[field_name].append(pattern)
            self.templates[field_name].patterns.append(pattern)
    
    def match_fields(self, text: str, partial: bool = True) -> Dict[str, FieldMatch]:
        """
        Match fields in text using templates.
        
        Args:
            text: Raw OCR text
            partial: If True, only extract fields that are found (partial matching)
        
        Returns:
            Dictionary of field_name -> FieldMatch
        """
        matches: Dict[str, FieldMatch] = {}
        lines = text.splitlines()
        
        # Try to match each template
        for field_name, template in self.templates.items():
            best_match = None
            best_confidence = 0.0
            
            # Try each pattern
            for pattern in template.patterns:
                # Search for label pattern
                for line_idx, line in enumerate(lines):
                    label_match = re.search(pattern, line, re.IGNORECASE)
                    if label_match:
                        # Found label, now extract value
                        value_start = label_match.end()
                        remaining_text = line[value_start:].strip()
                        
                        # Try value patterns if available
                        if template.value_patterns:
                            for value_pattern in template.value_patterns:
                                value_match = re.search(value_pattern, remaining_text)
                                if value_match:
                                    value = value_match.group(1).strip()
                                    confidence = self._calculate_confidence(
                                        pattern, value_pattern, value, template
                                    )
                                    
                                    if confidence > best_confidence:
                                        best_match = FieldMatch(
                                            field_name=field_name,
                                            value=value,
                                            confidence=confidence,
                                            matched_pattern=pattern,
                                            position=(line_idx, value_start)
                                        )
                                        best_confidence = confidence
                        else:
                            # No value pattern, take rest of line
                            if remaining_text:
                                confidence = self._calculate_confidence(
                                    pattern, None, remaining_text, template
                                )
                                
                                if confidence > best_confidence:
                                    best_match = FieldMatch(
                                        field_name=field_name,
                                        value=remaining_text,
                                        confidence=confidence,
                                        matched_pattern=pattern,
                                        position=(line_idx, value_start)
                                    )
                                    best_confidence = confidence
                        
                        # Also check next line if current line only has label
                        if not remaining_text and line_idx + 1 < len(lines):
                            next_line = lines[line_idx + 1].strip()
                            if next_line:
                                confidence = self._calculate_confidence(
                                    pattern, None, next_line, template
                                )
                                
                                if confidence > best_confidence:
                                    best_match = FieldMatch(
                                        field_name=field_name,
                                        value=next_line,
                                        confidence=confidence,
                                        matched_pattern=pattern,
                                        position=(line_idx + 1, 0)
                                    )
                                    best_confidence = confidence
            
            # Accept match if confidence is above threshold
            if best_match and best_confidence >= template.confidence_threshold:
                matches[field_name] = best_match
        
        # Also extract generic key-value pairs
        if partial:
            generic_matches = self._extract_generic_key_value_pairs(text, matches)
            matches.update(generic_matches)
        
        return matches
    
    def _calculate_confidence(
        self,
        label_pattern: str,
        value_pattern: Optional[str],
        value: str,
        template: FieldTemplate
    ) -> float:
        """Calculate confidence score for a match."""
        confidence = 0.5  # Base confidence
        
        # Boost if value pattern matches
        if value_pattern:
            if re.match(value_pattern, value):
                confidence += 0.3
        
        # Boost if value looks reasonable
        if len(value) > 2:
            confidence += 0.1
        
        # Boost if value doesn't look like noise
        if not re.match(r"^[^\w\s]+$", value):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _extract_generic_key_value_pairs(
        self,
        text: str,
        existing_matches: Dict[str, FieldMatch]
    ) -> Dict[str, FieldMatch]:
        """Extract generic key-value pairs not matched by templates."""
        matches: Dict[str, FieldMatch] = {}
        existing_field_names = {m.field_name for m in existing_matches.values()}
        
        for line_idx, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            
            # Look for key: value pattern
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    
                    if not value:
                        continue
                    
                    # Normalize key
                    normalized_key = self._normalize_key(key)
                    
                    # Check if it's an alias
                    canonical_name = self.field_aliases.get(normalized_key, normalized_key)
                    
                    # Skip if already matched or if it's a known field
                    if canonical_name in existing_field_names:
                        continue
                    
                    # Create match for unknown field
                    if normalized_key and value:
                        matches[normalized_key] = FieldMatch(
                            field_name=normalized_key,
                            value=value,
                            confidence=0.6,  # Lower confidence for generic matches
                            matched_pattern="generic_key_value",
                            position=(line_idx, 0)
                        )
        
        return matches
    
    def _normalize_key(self, key: str) -> str:
        """Normalize field key name."""
        # Remove special characters, convert to lowercase, replace spaces with underscores
        normalized = re.sub(r'[^\w\s]', '', key.lower())
        normalized = re.sub(r'\s+', '_', normalized)
        normalized = normalized.strip('_')
        return normalized
    
    def get_available_fields(self, text: str) -> Set[str]:
        """
        Get set of available field names in text (without extracting values).
        Useful for determining what fields are present in a document.
        
        Args:
            text: Raw OCR text
        
        Returns:
            Set of field names that are likely present
        """
        matches = self.match_fields(text, partial=True)
        return {match.field_name for match in matches.values()}
    
    def extract_partial_fields(self, text: str) -> Dict[str, str]:
        """
        Extract only the fields that are present in the text (partial mapping).
        
        Args:
            text: Raw OCR text
        
        Returns:
            Dictionary of field_name -> field_value (only for fields found)
        """
        matches = self.match_fields(text, partial=True)
        return {name: match.value for name, match in matches.items()}
    
    def save_templates(self, file_path: str):
        """Save templates to JSON file."""
        data = {
            "templates": {
                name: {
                    "name": t.name,
                    "patterns": t.patterns,
                    "value_patterns": t.value_patterns,
                    "synonyms": t.synonyms,
                    "required": t.required,
                    "confidence_threshold": t.confidence_threshold
                }
                for name, t in self.templates.items()
            },
            "learned_patterns": dict(self.learned_patterns),
            "field_aliases": self.field_aliases
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_templates(self, file_path: str):
        """Load templates from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct templates
        for name, template_data in data.get("templates", {}).items():
            template = FieldTemplate(
                name=template_data["name"],
                patterns=template_data["patterns"],
                value_patterns=template_data.get("value_patterns", []),
                synonyms=template_data.get("synonyms", []),
                required=template_data.get("required", False),
                confidence_threshold=template_data.get("confidence_threshold", 0.7)
            )
            self.templates[name] = template
        
        self.learned_patterns = defaultdict(list, data.get("learned_patterns", {}))
        self.field_aliases = data.get("field_aliases", {})


# Global template matcher instance
_default_matcher = None


def get_template_matcher() -> TemplateMatcher:
    """Get the default template matcher instance."""
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = TemplateMatcher()
    return _default_matcher


def match_key_value_pairs(text: str) -> Dict[str, str]:
    """
    Extract key-value pairs from text using template matching.
    
    Args:
        text: Raw OCR text
        
    Returns:
        Dictionary of field_name -> field_value
    """
    matcher = get_template_matcher()
    return matcher.extract_partial_fields(text)
