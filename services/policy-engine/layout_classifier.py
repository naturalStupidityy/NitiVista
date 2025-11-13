import logging
import re
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class LayoutClassifier:
    def __init__(self):
        # Define section patterns for different policy types
        self.section_patterns = {
            "health": {
                "coverage": [
                    "coverage", "what is covered", "benefits", "inclusions",
                    "medical expenses", "hospitalization", "treatment"
                ],
                "exclusions": [
                    "exclusions", "what is not covered", "not covered",
                    "limitations", "restrictions"
                ],
                "terms_conditions": [
                    "terms and conditions", "terms & conditions", "policy terms",
                    "conditions", "provisions"
                ],
                "waiting_periods": [
                    "waiting period", "waiting periods", "initial waiting",
                    "pre-existing waiting"
                ],
                "premium": [
                    "premium", "premium details", "payment", "premium payment"
                ],
                "claims": [
                    "claim procedure", "how to claim", "claims process",
                    "claim settlement"
                ]
            },
            "life": {
                "coverage": [
                    "coverage", "sum assured", "death benefit", "maturity benefit",
                    "survival benefit"
                ],
                "exclusions": [
                    "exclusions", "what is not covered", "not covered",
                    "suicide clause", "risk exclusions"
                ],
                "terms_conditions": [
                    "terms and conditions", "policy provisions", "policy terms"
                ],
                "premium": [
                    "premium", "premium payment", "payment frequency",
                    "premium table"
                ],
                "benefits": [
                    "benefits", "policy benefits", "additional benefits",
                    "rider benefits"
                ],
                "nomination": [
                    "nomination", "nominee", "assignment", "beneficiary"
                ]
            },
            "motor": {
                "coverage": [
                    "coverage", "what is covered", "comprehensive coverage",
                    "third party", "own damage"
                ],
                "exclusions": [
                    "exclusions", "what is not covered", "not covered",
                    "limitations", "exceptions"
                ],
                "terms_conditions": [
                    "terms and conditions", "policy terms", "conditions"
                ],
                "idv": [
                    "idv", "insured declared value", "vehicle value",
                    "depreciation"
                ],
                "claims": [
                    "claim procedure", "how to claim", "claims process",
                    "survey", "assessment"
                ],
                "add_on_covers": [
                    "add-on covers", "additional covers", "riders",
                    "zero depreciation", "engine protection"
                ]
            },
            "travel": {
                "coverage": [
                    "coverage", "what is covered", "medical coverage",
                    "trip cancellation", "baggage"
                ],
                "exclusions": [
                    "exclusions", "what is not covered", "not covered",
                    "limitations", "restrictions"
                ],
                "terms_conditions": [
                    "terms and conditions", "policy terms", "conditions"
                ],
                "geographical_scope": [
                    "geographical scope", "coverage area", "countries covered",
                    "worldwide", "schengen"
                ],
                "emergency_assistance": [
                    "emergency assistance", "medical emergency", "evacuation",
                    "repatriation"
                ],
                "claims": [
                    "claim procedure", "how to claim", "claims process",
                    "documentation required"
                ]
            }
        }
        
        # Common section headers across all policy types
        self.common_sections = {
            "definitions": ["definitions", "meaning of terms", "glossary"],
            "contact": ["contact us", "customer care", "helpline", "support"],
            "grievance": ["grievance", "complaints", "dispute resolution"],
            "renewal": ["renewal", "renewal terms", "renewal conditions"]
        }
    
    async def classify_sections(self, ocr_result: Dict) -> List[Dict]:
        """Classify document sections using layout analysis"""
        
        text = ocr_result.get("text", "")
        pages_data = ocr_result.get("pages_data", [])
        
        # First, detect policy type
        policy_type = self._detect_policy_type(text)
        logger.info(f"Detected policy type: {policy_type}")
        
        # Get relevant section patterns
        section_patterns = self.section_patterns.get(policy_type, self.section_patterns["health"])
        
        # Analyze text structure
        sections = await self._analyze_text_structure(text, section_patterns, pages_data)
        
        # Add common sections
        common_sections = await self._find_common_sections(text, pages_data)
        sections.extend(common_sections)
        
        # Sort sections by document order
        sections = sorted(sections, key=lambda x: x.get("start_line", 0))
        
        logger.info(f"Found {len(sections)} sections in document")
        return sections
    
    def _detect_policy_type(self, text: str) -> str:
        """Detect the type of insurance policy"""
        
        text_lower = text.lower()
        
        # Health insurance indicators
        health_indicators = [
            "health insurance", "medical insurance", "hospitalization",
            "medical expenses", "doctor", "treatment", "medicine"
        ]
        
        # Life insurance indicators
        life_indicators = [
            "life insurance", "life cover", "sum assured", "death benefit",
            "maturity benefit", "nominee"
        ]
        
        # Motor insurance indicators
        motor_indicators = [
            "motor insurance", "vehicle insurance", "car insurance",
            "bike insurance", "automobile", "registration number"
        ]
        
        # Travel insurance indicators
        travel_indicators = [
            "travel insurance", "trip insurance", "journey",
            "passport", "visa", "baggage", "flight"
        ]
        
        # Count matches for each type
        health_score = sum(1 for indicator in health_indicators if indicator in text_lower)
        life_score = sum(1 for indicator in life_indicators if indicator in text_lower)
        motor_score = sum(1 for indicator in motor_indicators if indicator in text_lower)
        travel_score = sum(1 for indicator in travel_indicators if indicator in text_lower)
        
        # Determine policy type based on highest score
        scores = {
            "health": health_score,
            "life": life_score,
            "motor": motor_score,
            "travel": travel_score
        }
        
        policy_type = max(scores, key=scores.get)
        
        # If no clear indicators, default to health
        if scores[policy_type] == 0:
            policy_type = "health"
        
        return policy_type
    
    async def _analyze_text_structure(self, text: str, section_patterns: Dict, pages_data: List) -> List[Dict]:
        """Analyze text structure to identify sections"""
        
        sections = []
        lines = text.split('\n')
        
        for section_type, keywords in section_patterns.items():
            section_info = self._find_section(lines, section_type, keywords)
            if section_info:
                sections.append(section_info)
        
        return sections
    
    def _find_section(self, lines: List[str], section_type: str, keywords: List[str]) -> Optional[Dict]:
        """Find a specific section in the text"""
        
        section_info = None
        best_match_score = 0
        best_match_line = -1
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Calculate match score for this line
            match_score = 0
            for keyword in keywords:
                if keyword in line_lower:
                    match_score += 1
            
            # Also consider header formatting (all caps, bold indicators)
            if self._is_likely_header(line):
                match_score += 0.5
            
            # Check if this is the best match so far
            if match_score > best_match_score and match_score >= 1:
                best_match_score = match_score
                best_match_line = i
        
        # Create section info if we found a good match
        if best_match_line >= 0:
            section_info = {
                "type": section_type,
                "title": lines[best_match_line].strip(),
                "start_line": best_match_line,
                "confidence": min(best_match_score / len(keywords), 1.0),
                "content": self._extract_section_content(lines, best_match_line)
            }
        
        return section_info
    
    def _is_likely_header(self, line: str) -> bool:
        """Determine if a line is likely a header"""
        
        line = line.strip()
        
        # Check for all caps
        if line.isupper() and len(line) > 3:
            return True
        
        # Check for common header patterns
        header_patterns = [
            r'^\d+\s*[.\-)\s]',  # Numbered sections
            r'^[A-Z][a-z]+\s*[A-Z][a-z]+',  # Title case
            r'^\s*[-*]\s*[A-Z]',  # Bullet points with caps
        ]
        
        import re
        for pattern in header_patterns:
            if re.match(pattern, line):
                return True
        
        # Check for short lines that could be headers
        if 3 <= len(line) <= 50 and any(char.isalpha() for char in line):
            return True
        
        return False
    
    def _extract_section_content(self, lines: List[str], start_line: int) -> str:
        """Extract content for a section starting from the given line"""
        
        content = []
        
        # Start from the line after the header
        for i in range(start_line + 1, min(len(lines), start_line + 20)):
            line = lines[i].strip()
            
            # Stop if we hit another likely header
            if self._is_likely_header(line) and len(line) < 50:
                break
            
            # Add meaningful content
            if len(line) > 10:  # Minimum content length
                content.append(line)
        
        return " ".join(content)
    
    async def _find_common_sections(self, text: str, pages_data: List) -> List[Dict]:
        """Find common sections that appear in most policy types"""
        
        common_sections = []
        lines = text.split('\n')
        
        for section_type, keywords in self.common_sections.items():
            section_info = self._find_section(lines, section_type, keywords)
            if section_info:
                common_sections.append(section_info)
        
        return common_sections
    
    def get_section_confidence(self, section: Dict) -> float:
        """Get confidence score for a section detection"""
        return section.get("confidence", 0.0)
    
    def get_section_content(self, section: Dict) -> str:
        """Get content of a section"""
        return section.get("content", "")
    
    def get_section_type(self, section: Dict) -> str:
        """Get type of a section"""
        return section.get("type", "unknown")
    
    def export_sections_json(self, sections: List[Dict]) -> str:
        """Export sections to JSON format"""
        
        export_data = {
            "sections": sections,
            "total_sections": len(sections),
            "export_timestamp": "2024-01-01T00:00:00Z",  # This would be current timestamp
            "confidence_summary": {
                "high_confidence": len([s for s in sections if s.get("confidence", 0) > 0.8]),
                "medium_confidence": len([s for s in sections if 0.5 <= s.get("confidence", 0) <= 0.8]),
                "low_confidence": len([s for s in sections if s.get("confidence", 0) < 0.5])
            }
        }
        
        return json.dumps(export_data, indent=2)