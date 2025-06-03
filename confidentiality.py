import re

def anonymize_text(text):
    """
    Dynamically anonymizes PII fields while keeping biomarker sections intact.
    """
    biomarker_sections = detect_biomarker_sections(text)
    
    parts = []
    last_end = 0
    for start, end in biomarker_sections:
        parts.append(text[last_end:start])  # Non-biomarker part
        parts.append(text[start:end])  # Biomarker part (unchanged)
        last_end = end
    
    parts.append(text[last_end:])  # Add remaining text
    
    anonymized_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:  # Non-biomarker part (PII anonymization)
            anonymized_part = anonymize_pii(part)
            anonymized_parts.append(anonymized_part)
        else:  # Biomarker part (unchanged)
            anonymized_parts.append(part)
    
    anonymized_text = " ".join(anonymized_parts)
    return anonymized_text

def detect_biomarker_sections(text):
    """
    Detects biomarker sections dynamically.
    Returns a list of (start, end) indices without overlapping sections.
    """
    biomarker_sections = []
    biomarker_headers = [
        "Biomarkers", "Test Results", "Laboratory Results", "Blood Test",
        "Reference Range", "Units", "Value", "Result"
    ]
    
    for header in biomarker_headers:
        matches = list(re.finditer(rf"{header}\s*[:\-]?", text, re.IGNORECASE))
        for match in matches:
            start_index = match.start()
            end_match = re.search(r"\n\n|\Z", text[start_index:])
            end_index = start_index + (end_match.end() if end_match else len(text))
            
            # Check if this section overlaps with any existing section
            overlap = False
            for i, (existing_start, existing_end) in enumerate(biomarker_sections):
                if not (end_index < existing_start or start_index > existing_end):
                    biomarker_sections[i] = (
                        min(existing_start, start_index),
                        max(existing_end, end_index)
                    )
                    overlap = True
                    break
            
            if not overlap:
                biomarker_sections.append((start_index, end_index))
    
    return biomarker_sections

def anonymize_pii(text):
    """
    Identifies and anonymizes PII fields dynamically.
    """
    pii_patterns = {
        r"(\b(Name|Full Name|Patient Name|Client Name|Person Name)\s*:\s*)([^\n]+)": r"\1XXXX",
        r"(\b(ID|Patient ID|Reference No|ID Number|Case Number)\s*:\s*)\S+": r"\1XXXX",
        r"(\b(Phone|Mobile|Contact|Phone No|Tel|Telephone)\s*:\s*)[+\d().\s-]+": r"\1XXXX",
        r"(\b(Email|Email ID|E-mail)\s*:\s*)\S+@\S+": r"\1XXXX",
        r"(\b(Address|Location|Residence|Home Address|Office Address)\s*:\s*)([^\n]+)": r"\1XXXX",
        r"(\b(DOB|Date of Birth|Birthdate|Birth Date)\s*:\s*)([^\n]+)": r"\1XXXX",
        r"(\b(Date|Report Date|Sample Date)\s*:\s*)([^\n]+)": r"\1XXXX",
        r"(\b(Time|Report Time|Collection Time|Testing Time)\s*:\s*)([^\n]+)": r"\1XXXX",
        r"(\b(Referral|Doctor Name|Physician|Referred By)\s*:\s*Dr\.\s*)([^\n]+)": r"\1XXXX",
    }
    
    for pattern, replacement in pii_patterns.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text