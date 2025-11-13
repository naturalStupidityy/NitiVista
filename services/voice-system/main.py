from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# Import voice generation modules
from voice_generator import VoiceGenerator
from text_simplifier import TextSimplifier
from whatsapp_client import WhatsAppClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NitiVista Voice Generation System", version="1.0.0")

# Initialize components
voice_generator = VoiceGenerator()
text_simplifier = TextSimplifier()
whatsapp_client = WhatsAppClient()

class VoiceRequest(BaseModel):
    text: str
    language: str = "en"
    phone_number: Optional[str] = None
    message_type: str = "voice"  # voice or text
    policy_id: Optional[str] = None

class VoiceResponse(BaseModel):
    request_id: str
    status: str
    message: str
    audio_file_path: Optional[str] = None
    processing_time: Optional[float] = None

class WhatsAppWebhook(BaseModel):
    phone_number: str
    message: str
    message_type: str
    timestamp: datetime

@app.get("/")
async def root():
    return {
        "message": "NitiVista Voice Generation System v1.0.0",
        "status": "operational",
        "supported_languages": ["en", "hi", "mr"]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "voice_generator": "operational",
            "text_simplifier": "operational",
            "whatsapp_client": "operational"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/generate-voice", response_model=VoiceResponse)
async def generate_voice(request: VoiceRequest, background_tasks: BackgroundTasks):
    """Generate voice message from text"""
    
    # Generate unique request ID
    request_id = f"VOICE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(request.text) % 10000:04d}"
    
    try:
        logger.info(f"Starting voice generation for request: {request_id}")
        start_time = datetime.now()
        
        # Step 1: Simplify text if needed
        if request.message_type == "voice":
            simplified_text = await text_simplifier.simplify(
                request.text, 
                target_grade=6, 
                language=request.language
            )
            logger.info(f"Text simplified for {request_id}")
        else:
            simplified_text = request.text
        
        # Step 2: Generate voice
        if request.message_type == "voice":
            audio_file = await voice_generator.generate_voice(
                text=simplified_text,
                language=request.language,
                output_file=f"generated_audio/{request_id}.mp3"
            )
            
            if not audio_file:
                raise HTTPException(status_code=500, detail="Voice generation failed")
            
            logger.info(f"Voice generated successfully for {request_id}")
        
        # Step 3: Send via WhatsApp if phone number provided
        if request.phone_number:
            background_tasks.add_task(
                send_whatsapp_message,
                request.phone_number,
                simplified_text if request.message_type == "text" else None,
                audio_file if request.message_type == "voice" else None,
                request_id
            )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return VoiceResponse(
            request_id=request_id,
            status="completed",
            message=f"Voice message generated successfully in {request.language}",
            audio_file_path=audio_file if request.message_type == "voice" else None,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Voice generation failed for {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

async def send_whatsapp_message(phone_number: str, text: Optional[str], audio_file: Optional[str], request_id: str):
    """Send message via WhatsApp"""
    try:
        if text:
            await whatsapp_client.send_text(phone_number, text)
        elif audio_file:
            await whatsapp_client.send_voice(phone_number, audio_file)
        
        logger.info(f"WhatsApp message sent successfully for {request_id}")
        
    except Exception as e:
        logger.error(f"WhatsApp message failed for {request_id}: {str(e)}")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(webhook_data: WhatsAppWebhook):
    """Handle incoming WhatsApp messages"""
    
    try:
        logger.info(f"Received WhatsApp message from {webhook_data.phone_number}")
        
        # Process the incoming message
        # This would typically integrate with the RAG Q&A system
        
        return {"status": "received", "message_id": f"MSG_{hash(webhook_data.message) % 10000:04d}"}
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@app.get("/voices/{request_id}")
async def get_voice_file(request_id: str):
    """Get generated voice file"""
    
    audio_file = f"generated_audio/{request_id}.mp3"
    
    if os.path.exists(audio_file):
        return FileResponse(audio_file, media_type="audio/mpeg")
    else:
        raise HTTPException(status_code=404, detail="Audio file not found")

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    
    try:
        stats = {
            "total_requests": voice_generator.get_total_requests(),
            "successful_generations": voice_generator.get_successful_generations(),
            "failed_generations": voice_generator.get_failed_generations(),
            "average_processing_time": voice_generator.get_average_processing_time(),
            "supported_languages": voice_generator.get_supported_languages(),
            "system_uptime": voice_generator.get_system_uptime(),
            "queue_size": voice_generator.get_queue_size()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    
    return {
        "languages": [
            {
                "code": "en",
                "name": "English",
                "native_name": "English",
                "voice_quality": "excellent"
            },
            {
                "code": "hi", 
                "name": "Hindi",
                "native_name": "हिन्दी",
                "voice_quality": "good"
            },
            {
                "code": "mr",
                "name": "Marathi", 
                "native_name": "मराठी",
                "voice_quality": "good"
            }
        ],
        "total_languages": 3
    }

@app.post("/simplify-text")
async def simplify_text(text: str, language: str = "en", target_grade: int = 6):
    """Simplify text to target reading grade level"""
    
    try:
        simplified = await text_simplifier.simplify(text, target_grade, language)
        
        return {
            "original_text": text,
            "simplified_text": simplified,
            "language": language,
            "target_grade": target_grade,
            "readability_improvement": await text_simplifier.calculate_improvement(text, simplified)
        }
        
    except Exception as e:
        logger.error(f"Text simplification failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Text simplification failed")

@app.get("/quality/{request_id}")
async def get_quality_metrics(request_id: str):
    """Get quality metrics for a generated voice"""
    
    try:
        metrics = await voice_generator.get_quality_metrics(request_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Quality metrics not found")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get quality metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get quality metrics")

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("generated_audio", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    uvicorn.run(app, host="0.0.0.0", port=8002)