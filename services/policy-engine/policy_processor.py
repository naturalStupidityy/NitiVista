import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class PolicyProcessor:
    def __init__(self, ocr_engine, layout_classifier, vector_store):
        self.ocr_engine = ocr_engine
        self.layout_classifier = layout_classifier
        self.vector_store = vector_store
        
    async def process_policy(self, file_path: str, policy_id: str) -> Dict:
        """Main policy processing pipeline"""
        
        try:
            logger.info(f"Starting policy processing pipeline for {policy_id}")
            
            # Step 1: OCR Processing
            ocr_result = await self.ocr_engine.extract_text(file_path)
            logger.info(f"OCR completed for {policy_id}")
            
            # Step 2: Layout Analysis and Section Classification
            sections = await self.layout_classifier.classify_sections(ocr_result)
            logger.info(f"Layout classification completed for {policy_id}")
            
            # Step 3: Extract structured data
            structured_data = self.extract_structured_data(sections, ocr_result)
            logger.info(f"Structured data extraction completed for {policy_id}")
            
            # Step 4: Generate vector embeddings
            vector_embeddings = await self.vector_store.create_embeddings(
                structured_data, policy_id
            )
            logger.info(f"Vector embeddings created for {policy_id}")
            
            # Step 5: Compile final result
            result = {
                "policy_id": policy_id,
                "processing_timestamp": datetime.now().isoformat(),
                "file_path": file_path,
                "ocr_confidence": ocr_result.get("confidence", 0.95),
                "structured_data": structured_data,
                "sections_detected": len(sections),
                "vector_embeddings": vector_embeddings,
                "processing_summary": {
                    "total_pages": ocr_result.get("pages", 1),
                    "total_words": len(ocr_result.get("text", "").split()),
                    "sections_found": [section["type"] for section in sections],
                    "exclusions_found": len(structured_data.get("exclusions", [])),
                    "key_terms_extracted": len(structured_data.get("key_terms", []))
                }
            }
            
            # Detect policy type and provider
            result["policy_type"] = self.detect_policy_type(structured_data)
            result["provider"] = self.detect_provider(ocr_result.get("text", ""))
            
            logger.info(f"Policy processing completed successfully for {policy_id}")
            return result
            
        except Exception as e:
            logger.error(f"Policy processing failed for {policy_id}: {str(e)}")
            raise
    
    def extract_structured_data(self, sections: List[Dict], ocr_result: Dict) -> Dict:
        """Extract structured information from policy document"""
        
        structured_data = {
            "policy_details": {},
            "exclusions": [],
            "terms_conditions": [],
            "coverage_details": [],
            "key_terms": [],
            "contact_info": {}
        }
        
        full_text = ocr_result.get("text", "").lower()
        
        # Extract exclusions
        structured_data["exclusions"] = self.extract_exclusions(full_text)
        
        # Extract key terms
        structured_data["key_terms"] = self.extract_key_terms(full_text)
        
        # Extract coverage details
        structured_data["coverage_details"] = self.extract_coverage_details(full_text)
        
        # Extract contact information
        structured_data["contact_info"] = self.extract_contact_info(full_text)
        
        # Extract policy details
        structured_data["policy_details"] = self.extract_policy_details(full_text)
        
        return structured_data
    
    def extract_exclusions(self, text: str) -> List[str]:
        """Extract policy exclusions"""
        exclusions = []
        
        # Common exclusion patterns
        exclusion_patterns = [
            "pre-existing",
            "cosmetic",
            "dental",
            "pregnancy",
            "alternative therapy",
            "war",
            "nuclear",
            "suicide",
            "intoxication",
            "hazardous activities",
            "drunk driving",
            "wear and tear",
            "consequential loss"
        ]
        
        # Look for exclusion sections
        lines = text.split('\n')
        in_exclusion_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if we're entering exclusion section
            if any(keyword in line_lower for keyword in ["exclusions", "what is not covered", "not covered"]):
                in_exclusion_section = True
                continue
            
            # Check if we're leaving exclusion section
            if in_exclusion_section and any(keyword in line_lower for keyword in ["coverage", "benefits", "terms", "conditions"]):
                in_exclusion_section = False
                continue
            
            # Extract exclusions
            if in_exclusion_section and len(line.strip()) > 10:
                for pattern in exclusion_patterns:
                    if pattern in line_lower:
                        exclusions.append(line.strip())
                        break
        
        # If no exclusions found in dedicated section, search throughout document
        if not exclusions:
            for pattern in exclusion_patterns:
                if pattern in text:
                    # Find the sentence containing this pattern
                    sentences = text.split('.')
                    for sentence in sentences:
                        if pattern in sentence.lower():
                            exclusions.append(sentence.strip() + '.')
                            break
        
        return list(set(exclusions))[:10]  # Remove duplicates, limit to 10
    
    def extract_key_terms(self, text: str) -> List[str]:
        """Extract key insurance terms"""
        key_terms = []
        
        insurance_terms = [
            "deductible",
            "copayment",
            "premium",
            "sum insured",
            "waiting period",
            "grace period",
            "policy term",
            "renewal",
            "claim",
            "beneficiary",
            "nominee",
            "rider",
            "exclusion",
            "pre-existing disease"
        ]
        
        for term in insurance_terms:
            if term in text.lower():
                key_terms.append(term.title())
        
        return key_terms
    
    def extract_coverage_details(self, text: str) -> List[str]:
        """Extract coverage details"""
        coverage_details = []
        
        # Look for coverage sections
        lines = text.split('\n')
        in_coverage_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if we're entering coverage section
            if any(keyword in line_lower for keyword in ["coverage", "what is covered", "benefits"]):
                in_coverage_section = True
                continue
            
            # Check if we're leaving coverage section
            if in_coverage_section and any(keyword in line_lower for keyword in ["exclusions", "terms", "conditions"]):
                in_coverage_section = False
                continue
            
            # Extract coverage details
            if in_coverage_section and len(line.strip()) > 10:
                coverage_details.append(line.strip())
        
        return coverage_details[:15]  # Limit to 15 items
    
    def extract_contact_info(self, text: str) -> Dict:
        """Extract contact information"""
        contact_info = {}
        
        # Extract phone numbers
        import re
        phone_pattern = r'\b\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}\b'
        phones = re.findall(phone_pattern, text)
        if phones:
            contact_info["phone"] = phones[0]
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info["email"] = emails[0]
        
        # Extract website
        website_pattern = r'www\.[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
        websites = re.findall(website_pattern, text)
        if websites:
            contact_info["website"] = websites[0]
        
        return contact_info
    
    def extract_policy_details(self, text: str) -> Dict:
        """Extract basic policy details"""
        details = {}
        
        # Extract policy number
        import re
        policy_num_pattern = r'policy\s+(?:number|no)\.?\s*:?\s*([A-Z0-9-]+)'
        policy_match = re.search(policy_num_pattern, text, re.IGNORECASE)
        if policy_match:
            details["policy_number"] = policy_match.group(1)
        
        # Extract dates
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        dates = re.findall(date_pattern, text)
        if len(dates) >= 2:
            details["start_date"] = dates[0]
            details["end_date"] = dates[1]
        
        return details
    
    def detect_policy_type(self, structured_data: Dict) -> str:
        """Detect policy type from content"""
        text = json.dumps(structured_data).lower()
        
        if any(word in text for word in ["health", "medical", "hospital", "treatment"]):
            return "health"
        elif any(word in text for word in ["life", "death", "sum assured", "maturity"]):
            return "life"
        elif any(word in text for word in ["motor", "vehicle", "car", "bike", "accident"]):
            return "motor"
        elif any(word in text for word in ["travel", "trip", "journey", "passport"]):
            return "travel"
        else:
            return "unknown"
    
    def detect_provider(self, text: str) -> str:
        """Detect insurance provider from text"""
        providers = [
            "LIC", "Life Insurance Corporation",
            "ICICI Prudential", "ICICI Lombard",
            "HDFC Life", "HDFC ERGO",
            "Star Health", "Apollo Munich", "Max Bupa",
            "Bajaj Allianz", "Tata AIG", "Reliance",
            "SBI Life", "Max Life"
        ]
        
        for provider in providers:
            if provider.lower() in text.lower():
                return provider
        
        return "Unknown Provider"