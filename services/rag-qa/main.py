from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# Import RAG components
from rag_system import RAGSystem
from speech_processor import SpeechProcessor
from vector_retriever import VectorRetriever
from confidence_scorer import ConfidenceScorer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NitiVista RAG Q&A System", version="1.0.0")

# Initialize components
speech_processor = SpeechProcessor()
vector_retriever = VectorRetriever()
confidence_scorer = ConfidenceScorer()
rag_system = RAGSystem(speech_processor, vector_retriever, confidence_scorer)

class QueryRequest(BaseModel):
    query: str
    phone_number: Optional[str] = None
    language: str = "en"
    policy_id: Optional[str] = None
    context: Optional[str] = None

class QueryResponse(BaseModel):
    query_id: str
    answer: str
    confidence: float
    sources: List[Dict]
    processing_time: float
    language: str

class VoiceQueryRequest(BaseModel):
    audio_file: str
    phone_number: str
    language: str = "en"
    policy_id: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "NitiVista RAG Q&A System v1.0.0",
        "status": "operational",
        "supported_languages": ["en", "hi", "mr"]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "rag_system": "operational",
            "speech_processor": "operational",
            "vector_retriever": "operational",
            "confidence_scorer": "operational"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process insurance query using RAG system"""
    
    # Generate unique query ID
    query_id = f"QUERY_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(request.query) % 10000:04d}"
    
    try:
        logger.info(f"Processing query: {request.query[:50]}...")
        start_time = datetime.now()
        
        # Process the query through RAG system
        result = await rag_system.process_query(
            query=request.query,
            language=request.language,
            policy_id=request.policy_id,
            context=request.context
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Format response
        response = QueryResponse(
            query_id=query_id,
            answer=result["answer"],
            confidence=result["confidence"],
            sources=result["sources"],
            processing_time=processing_time,
            language=request.language
        )
        
        logger.info(f"Query processed successfully in {processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

@app.post("/voice-query")
async def process_voice_query(request: VoiceQueryRequest, background_tasks: BackgroundTasks):
    """Process voice query from WhatsApp"""
    
    try:
        logger.info(f"Processing voice query from {request.phone_number}")
        
        # Step 1: Convert speech to text
        transcription = await speech_processor.speech_to_text(
            audio_file=request.audio_file,
            language=request.language
        )
        
        if not transcription:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")
        
        logger.info(f"Transcribed voice query: {transcription[:50]}...")
        
        # Step 2: Process the transcribed query
        query_result = await rag_system.process_query(
            query=transcription,
            language=request.language,
            policy_id=request.policy_id,
            phone_number=request.phone_number
        )
        
        # Step 3: Generate voice response in background
        background_tasks.add_task(
            generate_voice_response,
            query_result,
            request.phone_number,
            request.language
        )
        
        return {
            "status": "processing",
            "message": "Voice query received. Voice response will be sent shortly.",
            "transcription": transcription,
            "confidence": query_result["confidence"]
        }
        
    except Exception as e:
        logger.error(f"Voice query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Voice query processing failed")

async def generate_voice_response(query_result: Dict, phone_number: str, language: str):
    """Generate and send voice response"""
    try:
        # This would integrate with the voice generation system
        logger.info(f"Generating voice response for {phone_number}")
        
        # Simulate voice generation and sending
        await asyncio.sleep(2.0)
        
        logger.info(f"Voice response sent to {phone_number}")
        
    except Exception as e:
        logger.error(f"Voice response generation failed: {str(e)}")

@app.get("/policies/{policy_id}/qa")
async def get_policy_qa(policy_id: str, query: Optional[str] = None):
    """Get Q&A for a specific policy"""
    
    try:
        if query:
            # Answer specific question about policy
            result = await rag_system.answer_policy_question(policy_id, query)
            return result
        else:
            # Get common questions about policy
            common_questions = await rag_system.get_common_policy_questions(policy_id)
            return {"policy_id": policy_id, "common_questions": common_questions}
            
    except Exception as e:
        logger.error(f"Policy Q&A failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Policy Q&A failed")

@app.get("/knowledge-base/search")
async def search_knowledge_base(query: str, limit: int = 5):
    """Search the knowledge base"""
    
    try:
        results = await vector_retriever.search(
            query=query,
            top_k=limit
        )
        
        return {
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
    except Exception as e:
        logger.error(f"Knowledge base search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Knowledge base search failed")

@app.post("/knowledge-base/add")
async def add_to_knowledge_base(content: Dict):
    """Add content to knowledge base"""
    
    try:
        success = await vector_retriever.add_content(
            content=content["content"],
            metadata=content.get("metadata", {}),
            source=content.get("source", "manual")
        )
        
        if success:
            return {"status": "success", "message": "Content added to knowledge base"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add content")
            
    except Exception as e:
        logger.error(f"Failed to add content to knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add content")

@app.get("/confidence/{query_id}")
async def get_confidence_score(query_id: str):
    """Get confidence score for a query"""
    
    try:
        confidence_data = await confidence_scorer.get_confidence_details(query_id)
        
        if not confidence_data:
            raise HTTPException(status_code=404, detail="Confidence data not found")
        
        return confidence_data
        
    except Exception as e:
        logger.error(f"Failed to get confidence score: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get confidence score")

@app.get("/analytics")
async def get_analytics():
    """Get system analytics"""
    
    try:
        analytics = await rag_system.get_analytics()
        
        return {
            "total_queries": analytics.get("total_queries", 0),
            "successful_queries": analytics.get("successful_queries", 0),
            "average_confidence": analytics.get("average_confidence", 0.0),
            "average_processing_time": analytics.get("average_processing_time", 0.0),
            "top_query_types": analytics.get("top_query_types", []),
            "language_distribution": analytics.get("language_distribution", {}),
            "confidence_distribution": analytics.get("confidence_distribution", {})
        }
        
    except Exception as e:
        logger.error(f"Failed to get analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")

@app.get("/feedback/{query_id}")
async def get_query_feedback(query_id: str):
    """Get feedback for a specific query"""
    
    try:
        feedback = await rag_system.get_query_feedback(query_id)
        
        if not feedback:
            raise HTTPException(status_code=404, detail="Query feedback not found")
        
        return feedback
        
    except Exception as e:
        logger.error(f"Failed to get query feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get query feedback")

@app.post("/feedback")
async def submit_feedback(query_id: str, rating: int, comment: Optional[str] = None):
    """Submit feedback for a query"""
    
    try:
        success = await rag_system.submit_feedback(
            query_id=query_id,
            rating=rating,
            comment=comment
        )
        
        if success:
            return {"status": "success", "message": "Feedback submitted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to submit feedback")
            
    except Exception as e:
        logger.error(f"Failed to submit feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

@app.get("/models")
async def get_model_info():
    """Get information about the models being used"""
    
    return {
        "retrieval_model": {
            "name": "ChromaDB Vector Store",
            "description": "Semantic search over policy documents",
            "embedding_dimension": 384
        },
        "generation_model": {
            "name": "DistilBERT + Custom Logic",
            "description": "Insurance domain-specific Q&A generation",
            "max_context_length": 512
        },
        "speech_model": {
            "name": "Google Cloud Speech-to-Text",
            "description": "Multi-language speech recognition",
            "supported_languages": ["en", "hi", "mr"]
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)