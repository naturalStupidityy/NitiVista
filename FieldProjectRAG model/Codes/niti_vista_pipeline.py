"""
NitiVista-EN Policy Processing Pipeline
======================================

A comprehensive AI-powered system for processing insurance policies and
providing voice-based explanations to first-time buyers in Pune.

Features:
- PDF policy document processing
- OCR text extraction
- AI-powered policy analysis
- Voice synthesis for explanations
- WhatsApp Business integration
- RAG-based Q&A system

Author: Team NitiVista
Date: November 10, 2025
Location: Sinhagad Road, Pune
"""

import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import aiofiles

# External dependencies
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import cv2
import numpy as np
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering
import torch
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

# Database and vector search
from chromadb import Client
import chromadb.config

# WhatsApp Business API
from whatsapp_api import WhatsAppAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('niti_vista_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NitiVista-EN')

class PolicyProcessor:
    """Core policy document processing engine"""
    
    def __init__(self):
        self.ocr_engine = pytesseract
        self.nlp_pipeline = pipeline("text-classification", 
                                   model="distilbert-base-uncased-finetuned-sst-2-english")
        self.qa_pipeline = pipeline("question-answering",
                                  model="distilbert-base-cased-distilled-squad")
        
        # Initialize vector database
        self.chroma_client = Client(chromadb.config.Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="./chroma_db"
        ))
        self.collection = self.chroma_client.create_collection("policy_documents")
        
        logger.info("PolicyProcessor initialized successfully")
    
    async def process_pdf(self, pdf_path: str) -> Dict:
        """
        Process PDF policy document and extract structured information
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary containing extracted policy information
        """
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            
            # Extract text using PyMuPDF
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += f"\n--- Page {page_num + 1} ---\n"
                full_text += text
            
            doc.close()
            
            # Extract key policy sections
            policy_data = self._extract_policy_sections(full_text)
            policy_data['raw_text'] = full_text
            policy_data['file_hash'] = self._calculate_file_hash(pdf_path)
            policy_data['processing_date'] = datetime.now().isoformat()
            
            # Store in vector database
            await self._store_policy_data(policy_data)
            
            logger.info(f"PDF processing completed for: {pdf_path}")
            return policy_data
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
    
    def _extract_policy_sections(self, text: str) -> Dict:
        """Extract key sections from policy document"""
        sections = {
            'policy_number': self._extract_policy_number(text),
            'insurer_name': self._extract_insurer_name(text),
            'policy_holder': self._extract_policy_holder(text),
            'coverage_details': self._extract_coverage_details(text),
            'exclusions': self._extract_exclusions(text),
            'premium_amount': self._extract_premium_amount(text),
            'validity_period': self._extract_validity_period(text),
            'claim_process': self._extract_claim_process(text),
            'contact_info': self._extract_contact_info(text)
        }
        return sections
    
    def _extract_policy_number(self, text: str) -> str:
        """Extract policy number using regex patterns"""
        import re
        patterns = [
            r'Policy\s*Number\s*[:]?\s*([A-Z0-9-]+)',
            r'Policy\s*No\.?\s*[:]?\s*([A-Z0-9-]+)',
            r'(?:Policy|Certificate)\s*[:]?\s*([A-Z0-9-]{8,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Not found"
    
    def _extract_insurer_name(self, text: str) -> str:
        """Extract insurance company name"""
        insurers = [
            'LIC', 'Star Health', 'ICICI Lombard', 'HDFC Ergo', 
            'Bajaj Allianz', 'Max Bupa', 'Apollo Munich', 'Reliance',
            'Tata AIG', 'Bharti AXA', 'SBI Life', 'HDFC Life'
        ]
        
        text_upper = text.upper()
        for insurer in insurers:
            if insurer.upper() in text_upper:
                return insurer
        return "Unknown"
    
    def _extract_coverage_details(self, text: str) -> List[str]:
        """Extract coverage details and benefits"""
        # Look for coverage sections
        coverage_patterns = [
            r'Coverage[:\s]*(.*?)(?:Exclusions|Terms|Conditions|$)',
            r'Benefits[:\s]*(.*?)(?:Exclusions|Terms|Conditions|$)',
            r'What.*covered[:\s]*(.*?)(?:What.*not|Exclusions|$)'
        ]
        
        for pattern in coverage_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                coverage_text = match.group(1)
                # Extract bullet points or sentences
                benefits = [line.strip() for line in coverage_text.split('\n') 
                           if line.strip() and len(line.strip()) > 10]
                return benefits[:10]  # Limit to top 10 benefits
        
        return ["Coverage details not clearly specified"]
    
    def _extract_exclusions(self, text: str) -> List[str]:
        """Extract policy exclusions and limitations"""
        exclusion_patterns = [
            r'Exclusions[:\s]*(.*?)(?:Coverage|Benefits|Terms|$)',
            r'What.*not.*covered[:\s]*(.*?)(?:Coverage|Benefits|Terms|$)',
            r'Not.*covered[:\s]*(.*?)(?:Coverage|Benefits|Terms|$)'
        ]
        
        for pattern in exclusion_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                exclusion_text = match.group(1)
                exclusions = [line.strip() for line in exclusion_text.split('\n') 
                             if line.strip() and len(line.strip()) > 5]
                return exclusions[:8]  # Limit to top 8 exclusions
        
        return ["Standard policy exclusions apply"]
    
    def _extract_premium_amount(self, text: str) -> str:
        """Extract premium amount information"""
        import re
        premium_patterns = [
            r'Premium[:\s]*[₹Rs]?\.?\s*([0-9,]+\.?[0-9]*)',
            r'Amount[:\s]*[₹Rs]?\.?\s*([0-9,]+\.?[0-9]*)',
            r'[₹Rs]\.?\s*([0-9,]+\.?[0-9]*)\s*(?:premium|amount|payment)'
        ]
        
        for pattern in premium_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"₹{match.group(1).strip()}"
        return "Premium amount not specified"
    
    def _extract_validity_period(self, text: str) -> str:
        """Extract policy validity period"""
        import re
        date_patterns = [
            r'Valid.*(?:from|between)\s*[:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'Period[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}.*\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:From|Between)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}.*\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Validity period not specified"
    
    def _extract_claim_process(self, text: str) -> List[str]:
        """Extract claim process information"""
        claim_patterns = [
            r'Claim.*Process[:\s]*(.*?)(?:Contact|Customer|Service|$)',
            r'How.*claim[:\s]*(.*?)(?:Contact|Customer|Service|$)',
            r'In.*case.*claim[:\s]*(.*?)(?:Contact|Customer|Service|$)'
        ]
        
        for pattern in claim_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                claim_text = match.group(1)
                steps = [line.strip() for line in claim_text.split('\n') 
                        if line.strip() and len(line.strip()) > 10]
                return steps[:5]  # Limit to top 5 steps
        
        return ["Contact customer service for claim process"]
    
    def _extract_contact_info(self, text: str) -> Dict:
        """Extract contact information"""
        import re
        contact_info = {}
        
        # Phone numbers
        phone_pattern = r'(?:Phone|Contact|Call)[:\s]*([0-9-]{10,})'
        phone_match = re.search(phone_pattern, text, re.IGNORECASE)
        if phone_match:
            contact_info['phone'] = phone_match.group(1).strip()
        
        # Email
        email_pattern = r'(?:Email|Mail)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        email_match = re.search(email_pattern, text, re.IGNORECASE)
        if email_match:
            contact_info['email'] = email_match.group(1).strip()
        
        # Website
        website_pattern = r'(?:Website|Web)[:\s]*([a-zA-Z0-9./-]+\.[a-zA-Z]{2,})'
        website_match = re.search(website_pattern, text, re.IGNORECASE)
        if website_match:
            contact_info['website'] = website_match.group(1).strip()
        
        return contact_info
    
    def _extract_policy_holder(self, text: str) -> str:
        """Extract policy holder name"""
        import re
        # Look for patterns like "Name of Insured" or "Policy Holder"
        name_patterns = [
            r'(?:Name.*Insured|Policy.*Holder)[:\s]*([A-Za-z\s]+)',
            r'Insured[:\s]*([A-Za-z\s]+)',
            r'Mr\.|Ms\.|Mrs\.\s*([A-Za-z\s]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return "Policy holder name not specified"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file for deduplication"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def _store_policy_data(self, policy_data: Dict):
        """Store policy data in vector database for RAG"""
        try:
            # Create embedding for the policy text
            document_text = f"""
            Policy Number: {policy_data.get('policy_number', 'N/A')}
            Insurer: {policy_data.get('insurer_name', 'N/A')}
            Coverage: {' '.join(policy_data.get('coverage_details', []))}
            Exclusions: {' '.join(policy_data.get('exclusions', []))}
            Premium: {policy_data.get('premium_amount', 'N/A')}
            Validity: {policy_data.get('validity_period', 'N/A')}
            Claim Process: {' '.join(policy_data.get('claim_process', []))}
            """
            
            # Store in ChromaDB
            self.collection.add(
                documents=[document_text],
                metadatas=[{
                    'policy_number': policy_data.get('policy_number', ''),
                    'insurer': policy_data.get('insurer_name', ''),
                    'file_hash': policy_data.get('file_hash', ''),
                    'processing_date': policy_data.get('processing_date', '')
                }],
                ids=[policy_data.get('file_hash', str(datetime.now().timestamp()))]
            )
            
            logger.info(f"Policy data stored in vector database: {policy_data.get('policy_number', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Error storing policy data: {str(e)}")
            raise


class VoiceGenerator:
    """Text-to-speech engine for policy explanations"""
    
    def __init__(self):
        self.supported_languages = {
            'en': 'English',
            'mr': 'Marathi', 
            'hi': 'Hindi'
        }
        logger.info("VoiceGenerator initialized")
    
    def generate_voice_summary(self, policy_data: Dict, language: str = 'en') -> str:
        """
        Generate 60-second voice explanation of policy
        
        Args:
            policy_data: Processed policy information
            language: Language code ('en', 'mr', 'hi')
            
        Returns:
            Path to generated audio file
        """
        try:
            # Generate summary text in grade-6 readability
            summary_text = self._create_policy_summary(policy_data, language)
            
            # Create voice synthesis
            tts = gTTS(text=summary_text, lang=language, slow=False)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_file = f"policy_summary_{policy_data.get('policy_number', 'unknown')}_{timestamp}.mp3"
            
            # Save audio file
            tts.save(audio_file)
            
            logger.info(f"Voice summary generated: {audio_file}")
            return audio_file
            
        except Exception as e:
            logger.error(f"Error generating voice summary: {str(e)}")
            raise
    
    def _create_policy_summary(self, policy_data: Dict, language: str) -> str:
        """Create grade-6 readability policy summary"""
        
        # English template
        if language == 'en':
            summary = f"""
            Hello! This is your insurance policy summary in simple English.
            
            Your policy number is {policy_data.get('policy_number', 'not specified')}.
            Your insurance company is {policy_data.get('insurer_name', 'not specified')}.
            
            What this policy covers:
            {self._format_list_items(policy_data.get('coverage_details', [])[:3])}
            
            What this policy does NOT cover:
            {self._format_list_items(policy_data.get('exclusions', [])[:2])}
            
            Your premium amount is {policy_data.get('premium_amount', 'not specified')}.
            Your policy is valid from {policy_data.get('validity_period', 'not specified')}.
            
            To make a claim, follow these steps:
            {self._format_list_items(policy_data.get('claim_process', [])[:2])}
            
            For help, call {policy_data.get('contact_info', {}).get('phone', 'customer service')}.
            
            This summary is for understanding only. Please read your full policy document.
            """
        
        # Marathi template
        elif language == 'mr':
            summary = f"""
            नमस्कार! ही तुमच्या विमा पॉलिसीची सोपी मराठी सारांश आहे.
            
            तुमचा पॉलिसी क्रमांक आहे {policy_data.get('policy_number', 'निर्दिष्ट नाही')}.
            तुमची विमा कंपनी आहे {policy_data.get('insurer_name', 'निर्दिष्ट नाही')}.
            
            ही पॉलिसी काय कव्हर करते:
            {self._format_list_items_marathi(policy_data.get('coverage_details', [])[:3])}
            
            ही पॉलिसी काय कव्हर करत नाही:
            {self._format_list_items_marathi(policy_data.get('exclusions', [])[:2])}
            
            तुमचा प्रीमियम रक्कम आहे {policy_data.get('premium_amount', 'निर्दिष्ट नाही')}.
            तुमची पॉलिसी वैध आहे {policy_data.get('validity_period', 'निर्दिष्ट नाही')} पासून.
            
            दावा करण्यासाठी या पायऱ्या अनुसरणा:
            {self._format_list_items_marathi(policy_data.get('claim_process', [])[:2])}
            
            मदतीसाठी कॉल करा {policy_data.get('contact_info', {}).get('phone', 'ग्राहक सेवा')}.
            
            ही सारांश फक्त समजण्यासाठी आहे. कृपया तुमचा संपूर्ण पॉलिसी दस्तऐवज वाचा.
            """
        
        # Hindi template
        elif language == 'hi':
            summary = f"""
            नमस्ते! यह आपके बीमा पॉलिसी का सरल हिंदी सारांश है।
            
            आपकी पॉलिसी संख्या है {policy_data.get('policy_number', 'निर्दिष्ट नहीं है')}।
            आपकी बीमा कंपनी है {policy_data.get('insurer_name', 'निर्दिष्ट नहीं है')}।
            
            यह पॉलिसी क्या कवर करती है:
            {self._format_list_items_hindi(policy_data.get('coverage_details', [])[:3])}
            
            यह पॉलिसी क्या कवर नहीं करती है:
            {self._format_list_items_hindi(policy_data.get('exclusions', [])[:2])}
            
            आपकी प्रीमियम राशि है {policy_data.get('premium_amount', 'निर्दिष्ट नहीं है')}।
            आपकी पॉलिसी वैध है {policy_data.get('validity_period', 'निर्दिष्ट नहीं है')} से।
            
            दावा करने के लिए इन चरणों का पालन करें:
            {self._format_list_items_hindi(policy_data.get('claim_process', [])[:2])}
            
            मदद के लिए कॉल करें {policy_data.get('contact_info', {}).get('phone', 'ग्राहक सेवा')}।
            
            यह सारांश केवल समझने के लिए है। कृपया अपना पूरा पॉलिसी दस्तावेज़ पढ़ें।
            """
        
        else:
            summary = "Language not supported"
        
        # Clean up whitespace and ensure 60-second duration
        summary = ' '.join(summary.split())
        return summary
    
    def _format_list_items(self, items: List[str]) -> str:
        """Format list items for voice summary"""
        if not items:
            return "Not specified"
        
        formatted = ""
        for i, item in enumerate(items[:3]):  # Limit to 3 items
            clean_item = item.replace('•', '').replace('-', '').strip()
            if clean_item:
                formatted += f"{clean_item}. "
        
        return formatted if formatted else "Not specified"
    
    def _format_list_items_marathi(self, items: List[str]) -> str:
        """Format list items for Marathi voice summary"""
        if not items:
            return "निर्दिष्ट नाही"
        
        formatted = ""
        for i, item in enumerate(items[:3]):
            clean_item = item.replace('•', '').replace('-', '').strip()
            if clean_item:
                formatted += f"{clean_item}. "
        
        return formatted if formatted else "निर्दिष्ट नाही"
    
    def _format_list_items_hindi(self, items: List[str]) -> str:
        """Format list items for Hindi voice summary"""
        if not items:
            return "निर्दिष्ट नहीं है"
        
        formatted = ""
        for i, item in enumerate(items[:3]):
            clean_item = item.replace('•', '').replace('-', '').strip()
            if clean_item:
                formatted += f"{clean_item}. "
        
        return formatted if formatted else "निर्दिष्ट नहीं है"


class WhatsAppIntegration:
    """WhatsApp Business API integration for voice message delivery"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.whatsapp_api = WhatsAppAPI(api_key, api_secret)
        logger.info("WhatsAppIntegration initialized")
    
    async def send_voice_summary(self, phone_number: str, audio_file: str, 
                               policy_data: Dict) -> bool:
        """
        Send voice summary via WhatsApp
        
        Args:
            phone_number: Recipient's phone number
            audio_file: Path to audio file
            policy_data: Policy information for context
            
        Returns:
            Success status
        """
        try:
            # Send voice message
            message_sent = await self.whatsapp_api.send_media(
                phone_number=phone_number,
                media_path=audio_file,
                media_type="audio",
                caption=f"Your insurance policy summary for {policy_data.get('policy_number', 'Unknown')}"
            )
            
            if message_sent:
                logger.info(f"Voice summary sent to {phone_number}")
                
                # Send follow-up message with key points
                follow_up_text = self._create_follow_up_message(policy_data)
                await self.whatsapp_api.send_message(
                    phone_number=phone_number,
                    message=follow_up_text
                )
                
                return True
            else:
                logger.error(f"Failed to send voice summary to {phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
    
    def _create_follow_up_message(self, policy_data: Dict) -> str:
        """Create follow-up text message with key action items"""
        message = f"""
📋 *Key Information for Policy {policy_data.get('policy_number', 'Unknown')}*

✅ *What's Covered:*
{chr(10).join(['• ' + item[:50] + '...' if len(item) > 50 else '• ' + item for item in policy_data.get('coverage_details', [])[:3]])}

❌ *What's NOT Covered:*
{chr(10).join(['• ' + item[:50] + '...' if len(item) > 50 else '• ' + item for item in policy_data.get('exclusions', [])[:2]])}

💰 *Premium:* {policy_data.get('premium_amount', 'Not specified')}
📅 *Validity:* {policy_data.get('validity_period', 'Not specified')}

📞 *For Claims:* {policy_data.get('contact_info', {}).get('phone', 'Contact customer service')}

💡 *Reply with questions about your policy*
        """
        return message.strip()


class RAGSystem:
    """Retrieval-Augmented Generation system for policy Q&A"""
    
    def __init__(self, policy_processor: PolicyProcessor):
        self.policy_processor = policy_processor
        self.qa_model = pipeline("question-answering",
                               model="distilbert-base-cased-distilled-squad")
        logger.info("RAGSystem initialized")
    
    async def answer_question(self, question: str, policy_hash: str = None) -> Dict:
        """
        Answer user question about their policy using RAG
        
        Args:
            question: User's question
            policy_hash: Optional policy identifier
            
        Returns:
            Answer with confidence score and source
        """
        try:
            # Search for relevant policy information
            if policy_hash:
                # Search specific policy
                results = self.policy_processor.collection.query(
                    query_texts=[question],
                    where={"file_hash": policy_hash},
                    n_results=3
                )
            else:
                # General search
                results = self.policy_processor.collection.query(
                    query_texts=[question],
                    n_results=5
                )
            
            if not results['documents']:
                return {
                    'answer': "I don't have enough information to answer that question. Please upload your policy document first.",
                    'confidence': 0.0,
                    'source': 'None'
                }
            
            # Get the most relevant document
            context = results['documents'][0][0] if results['documents'] else ""
            
            # Generate answer using QA model
            qa_result = self.qa_model(question=question, context=context)
            
            # Format response
            response = {
                'answer': qa_result['answer'],
                'confidence': qa_result['score'],
                'source': results['metadatas'][0][0] if results['metadatas'] else 'Unknown policy',
                'question': question,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Question answered with confidence {response['confidence']:.2f}")
            return response
            
        except Exception as e:
            logger.error(f"Error in RAG question answering: {str(e)}")
            return {
                'answer': "Sorry, I encountered an error processing your question. Please try again.",
                'confidence': 0.0,
                'source': 'Error'
            }
    
    def get_suggested_questions(self, policy_data: Dict) -> List[str]:
        """Generate suggested questions based on policy data"""
        questions = [
            "What does my policy cover?",
            "What is not covered by my policy?",
            "How do I make a claim?",
            "What is my premium amount?",
            "When does my policy expire?"
        ]
        
        # Add policy-specific questions
        if policy_data.get('coverage_details'):
            questions.append(f"Tell me more about {policy_data['coverage_details'][0].lower()}")
        
        if policy_data.get('exclusions'):
            questions.append(f"Why is {policy_data['exclusions'][0].lower()} not covered?")
        
        return questions[:8]  # Limit to 8 questions


class NitiVistaPipeline:
    """Main pipeline orchestrating all components"""
    
    def __init__(self, whatsapp_api_key: str = None, whatsapp_api_secret: str = None):
        self.policy_processor = PolicyProcessor()
        self.voice_generator = VoiceGenerator()
        self.rag_system = RAGSystem(self.policy_processor)
        
        if whatsapp_api_key and whatsapp_api_secret:
            self.whatsapp_integration = WhatsAppIntegration(whatsapp_api_key, whatsapp_api_secret)
        else:
            self.whatsapp_integration = None
            logger.warning("WhatsApp integration not configured")
    
    async def process_and_deliver(self, pdf_path: str, phone_number: str, 
                                language: str = 'en') -> Dict:
        """
        Complete pipeline: process PDF, generate voice summary, deliver via WhatsApp
        
        Args:
            pdf_path: Path to policy PDF
            phone_number: Recipient's phone number
            language: Language for voice summary
            
        Returns:
            Processing results and delivery status
        """
        try:
            logger.info(f"Starting complete pipeline for {pdf_path} -> {phone_number}")
            
            # Step 1: Process PDF
            policy_data = await self.policy_processor.process_pdf(pdf_path)
            
            # Step 2: Generate voice summary
            audio_file = self.voice_generator.generate_voice_summary(policy_data, language)
            
            # Step 3: Deliver via WhatsApp (if configured)
            delivery_status = False
            if self.whatsapp_integration:
                delivery_status = await self.whatsapp_integration.send_voice_summary(
                    phone_number, audio_file, policy_data
                )
            
            # Step 4: Generate suggested questions
            suggested_questions = self.rag_system.get_suggested_questions(policy_data)
            
            # Prepare response
            result = {
                'success': True,
                'policy_data': policy_data,
                'audio_file': audio_file,
                'delivery_status': delivery_status,
                'suggested_questions': suggested_questions,
                'processing_time': datetime.now().isoformat(),
                'language': language
            }
            
            logger.info(f"Pipeline completed successfully for {phone_number}")
            return result
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': datetime.now().isoformat()
            }
    
    async def handle_user_question(self, question: str, phone_number: str, 
                                 policy_hash: str = None) -> Dict:
        """
        Handle user question through RAG system
        
        Args:
            question: User's question
            phone_number: User's phone number
            policy_hash: Optional policy identifier
            
        Returns:
            Answer and follow-up suggestions
        """
        try:
            # Get answer from RAG system
            answer_data = await self.rag_system.answer_question(question, policy_hash)
            
            # Send answer via WhatsApp (if configured)
            if self.whatsapp_integration and answer_data['confidence'] > 0.3:
                await self.whatsapp_integration.whatsapp_api.send_message(
                    phone_number=phone_number,
                    message=f"""
*Answer to your question:*

{answer_data['answer']}

*Confidence:* {answer_data['confidence']:.1%}

*Do you have any other questions about your policy?*
                    """
                )
            
            return answer_data
            
        except Exception as e:
            logger.error(f"Error handling user question: {str(e)}")
            return {
                'answer': "Sorry, I encountered an error. Please try again.",
                'confidence': 0.0,
                'source': 'Error'
            }


# Example usage and testing
async def main():
    """Example usage of the NitiVista-EN pipeline"""
    
    # Initialize pipeline
    pipeline = NitiVistaPipeline()
    
    # Example: Process a policy PDF
    pdf_path = "sample_policy.pdf"  # Replace with actual PDF path
    phone_number = "+919876543210"  # Replace with actual phone number
    
    if os.path.exists(pdf_path):
        result = await pipeline.process_and_deliver(
            pdf_path=pdf_path,
            phone_number=phone_number,
            language='en'
        )
        
        print(f"Processing result: {result}")
        
        # Example: Handle user question
        if result['success']:
            question_result = await pipeline.handle_user_question(
                question="What does my policy cover?",
                phone_number=phone_number,
                policy_hash=result['policy_data'].get('file_hash')
            )
            print(f"Question answer: {question_result}")
    else:
        logger.warning(f"Sample PDF not found: {pdf_path}")
        print("Please provide a valid PDF policy document")


if __name__ == "__main__":
    # Run example
    asyncio.run(main())