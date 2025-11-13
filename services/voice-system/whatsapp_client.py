import logging
import os
import json
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self):
        # WhatsApp Business API configuration
        self.api_url = "https://graph.facebook.com/v18.0"
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1234567890")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "demo_token")
        
        # Rate limiting
        self.rate_limit = 950  # Messages per day limit
        self.messages_sent_today = 0
        self.last_reset_date = datetime.now().date()
        
        # Message templates
        self.templates = {
            "welcome": {
                "en": "Welcome to NitiVista! I can help you understand your insurance policy in simple language. What would you like to know?",
                "hi": "नितिविस्टा में आपका स्वागत है! मैं आपकी बीमा पॉलिसी को सरल भाषा में समझाने में मदद कर सकता हूं। आप क्या जानना चाहेंगे?",
                "mr": "नितिविस्टामध्ये तुमचे स्वागत आहे! मी तुमची विमा पॉलिसी सोप्या भाषेत समजावण्यात मदत करू शकतो. तुम्हाला काय माहिती हवी आहे?"
            },
            "help": {
                "en": "I can help you with:\n• Understanding policy terms\n• Finding exclusions\n• Claim procedures\n• Premium details\n\nJust ask your question!",
                "hi": "मैं आपकी मदद कर सकता हूं:\n• पॉलिसी शब्दों को समझने में\n• अपवाद खोजने में\n• दावा प्रक्रिया में\n• प्रीमियम विवरण में\n\nबस अपना प्रश्न पूछें!",
                "mr": "मी तुमच्या मदतीला येऊ शकतो:\n• पॉलिसी शब्द समजण्यात\n• अपवाद शोधण्यात\n• दावा प्रक्रियेत\n• प्रीमियम तपशीलात\n\nफक्त तुमचा प्रश्न विचारा!"
            },
            "processing": {
                "en": "I'm processing your question about insurance. I'll send you a voice explanation shortly!",
                "hi": "मैं आपके बीमा संबंधी प्रश्न को संसाधित कर रहा हूं। मैं शीघ्र ही आपको वॉइस स्पष्टीकरण भेजूंगा!",
                "mr": "मी तुमच्या विमा संबंधित प्रश्नावर प्रक्रिया करत आहे. मी लवकरच तुम्हाला व्हॉईस स्पष्टीकरण पाठवतो!"
            }
        }
        
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Load message history
        self.message_history = self._load_message_history()
    
    async def send_text(self, phone_number: str, message: str, template_key: Optional[str] = None) -> bool:
        """Send text message via WhatsApp"""
        
        try:
            # Check rate limit
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded, cannot send message")
                return False
            
            # Use template if provided
            if template_key and template_key in self.templates:
                # For demo, just use the message as-is
                pass
            
            # Simulate API call
            logger.info(f"Sending text message to {phone_number}: {message[:50]}...")
            
            # In real implementation, this would call WhatsApp Business API
            # For demo, we'll just log and simulate success
            
            # Simulate API response
            await asyncio.sleep(0.5)  # Simulate network delay
            
            # Record message
            self._record_message(phone_number, "text", message)
            
            # Update rate limit counter
            self.messages_sent_today += 1
            
            logger.info(f"Text message sent successfully to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send text message: {str(e)}")
            return False
    
    async def send_voice(self, phone_number: str, audio_file_path: str) -> bool:
        """Send voice message via WhatsApp"""
        
        try:
            # Check rate limit
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded, cannot send message")
                return False
            
            # Check if audio file exists
            if not os.path.exists(audio_file_path):
                logger.error(f"Audio file not found: {audio_file_path}")
                return False
            
            logger.info(f"Sending voice message to {phone_number}: {audio_file_path}")
            
            # Simulate API call
            await asyncio.sleep(1.0)  # Simulate longer delay for file upload
            
            # Record message
            self._record_message(phone_number, "voice", audio_file_path)
            
            # Update rate limit counter
            self.messages_sent_today += 1
            
            logger.info(f"Voice message sent successfully to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send voice message: {str(e)}")
            return False
    
    async def send_template(self, phone_number: str, template_key: str, language: str = "en") -> bool:
        """Send template message"""
        
        try:
            if template_key not in self.templates:
                logger.error(f"Template not found: {template_key}")
                return False
            
            if language not in self.templates[template_key]:
                logger.warning(f"Language {language} not available for template {template_key}, using English")
                language = "en"
            
            message = self.templates[template_key][language]
            
            return await self.send_text(phone_number, message)
            
        except Exception as e:
            logger.error(f"Failed to send template: {str(e)}")
            return False
    
    async def send_interactive_message(self, phone_number: str, message: str, options: List[str]) -> bool:
        """Send interactive message with quick reply options"""
        
        try:
            # Format interactive message
            interactive_text = f"{message}\n\n"
            for i, option in enumerate(options, 1):
                interactive_text += f"{i}. {option}\n"
            
            return await self.send_text(phone_number, interactive_text)
            
        except Exception as e:
            logger.error(f"Failed to send interactive message: {str(e)}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if we can send more messages"""
        
        # Reset daily counter if it's a new day
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.messages_sent_today = 0
            self.last_reset_date = today
        
        return self.messages_sent_today < self.rate_limit
    
    def _record_message(self, phone_number: str, message_type: str, content: str):
        """Record sent message for tracking"""
        
        message_record = {
            "phone_number": phone_number,
            "message_type": message_type,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "timestamp": datetime.now().isoformat(),
            "status": "sent"
        }
        
        # Add to history
        if phone_number not in self.message_history:
            self.message_history[phone_number] = []
        
        self.message_history[phone_number].append(message_record)
        
        # Keep only last 100 messages per number
        if len(self.message_history[phone_number]) > 100:
            self.message_history[phone_number] = self.message_history[phone_number][-100:]
        
        # Save to disk
        self._save_message_history()
    
    def _load_message_history(self) -> Dict:
        """Load message history from disk"""
        
        history_file = "logs/whatsapp_history.json"
        
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load message history: {str(e)}")
        
        return {}
    
    def _save_message_history(self):
        """Save message history to disk"""
        
        try:
            history_file = "logs/whatsapp_history.json"
            with open(history_file, 'w') as f:
                json.dump(self.message_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save message history: {str(e)}")
    
    def get_message_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        """Get message history for a phone number"""
        
        history = self.message_history.get(phone_number, [])
        return history[-limit:] if history else []
    
    def get_stats(self) -> Dict:
        """Get WhatsApp client statistics"""
        
        total_messages = sum(len(messages) for messages in self.message_history.values())
        
        message_types = {"text": 0, "voice": 0, "template": 0}
        for messages in self.message_history.values():
            for message in messages:
                msg_type = message.get("message_type", "text")
                if msg_type in message_types:
                    message_types[msg_type] += 1
        
        return {
            "total_messages_sent": total_messages,
            "unique_phone_numbers": len(self.message_history),
            "rate_limit_used": self.messages_sent_today,
            "rate_limit_total": self.rate_limit,
            "message_types": message_types,
            "last_reset_date": self.last_reset_date.isoformat()
        }
    
    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format"""
        
        # Simple validation - should start with country code
        # In real implementation, this would be more sophisticated
        
        import re
        pattern = r'^\+?[1-9]\d{1,14}$'
        
        return bool(re.match(pattern, phone_number))
    
    async def get_delivery_status(self, message_id: str) -> Dict:
        """Get delivery status of a message"""
        
        # In real implementation, this would check with WhatsApp API
        # For demo, return simulated status
        
        return {
            "message_id": message_id,
            "status": "delivered",
            "delivered_at": datetime.now().isoformat(),
            "read": True,
            "read_at": datetime.now().isoformat()
        }
    
    async def handle_incoming_message(self, webhook_data: Dict) -> Dict:
        """Handle incoming WhatsApp message"""
        
        phone_number = webhook_data.get("phone_number")
        message = webhook_data.get("message")
        message_type = webhook_data.get("message_type")
        
        logger.info(f"Received message from {phone_number}: {message[:50]}...")
        
        # Process the message and generate response
        response = await self._process_incoming_message(phone_number, message, message_type)
        
        return {
            "status": "processed",
            "response": response,
            "phone_number": phone_number,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _process_incoming_message(self, phone_number: str, message: str, message_type: str) -> str:
        """Process incoming message and generate appropriate response"""
        
        message_lower = message.lower().strip()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ["hello", "hi", "नमस्ते", "नमस्कार"]):
            return await self.send_template(phone_number, "welcome", "en")
        
        elif any(word in message_lower for word in ["help", "मदद", "मदत"]):
            return await self.send_template(phone_number, "help", "en")
        
        elif any(word in message_lower for word in ["policy", "पॉलिसी", "विमा"]):
            return await self.send_text(phone_number, "I can help you understand your insurance policy. Please upload your policy document or ask a specific question about your policy.")
        
        elif any(word in message_lower for word in ["claim", "दावा"]):
            return await self.send_text(phone_number, "I can explain the claim process. What type of claim do you want to know about - health, motor, or life insurance?")
        
        else:
            return await self.send_text(phone_number, "I'm processing your question about insurance. I'll send you a detailed voice explanation shortly!")