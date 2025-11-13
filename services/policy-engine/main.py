from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# Import our processing modules
from policy_processor import PolicyProcessor
from ocr_engine import OCREngine
from layout_classifier import LayoutClassifier
from vector_store import VectorStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NitiVista Policy Processing Engine", version="1.0.0")

# Initialize components
ocr_engine = OCREngine()
layout_classifier = LayoutClassifier()
vector_store = VectorStore()
policy_processor = PolicyProcessor(ocr_engine, layout_classifier, vector_store)

class ProcessingStatus(BaseModel):
    status: str
    message: str
    policy_id: Optional[str] = None
    processing_time: Optional[float] = None

class PolicyResponse(BaseModel):
    policy_id: str
    provider: str
    policy_type: str
    structured_data: Dict
    vector_embeddings: bool
    processing_timestamp: datetime

@app.get("/")
async def root():
    return {"message": "NitiVista Policy Processing Engine v1.0.0", "status": "operational"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "ocr_engine": "operational",
            "layout_classifier": "operational", 
            "vector_store": "operational"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/upload-policy", response_model=ProcessingStatus)
async def upload_policy(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process an insurance policy document"""
    
    if not file.filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Only PDF, PNG, JPG files are supported")
    
    # Create unique policy ID
    policy_id = f"POL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(file.filename) % 10000:04d}"
    
    # Save uploaded file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{policy_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"File uploaded: {file.filename} -> {file_path}")
        
        # Process in background
        background_tasks.add_task(process_policy_async, policy_id, file_path)
        
        return ProcessingStatus(
            status="processing",
            message="Policy uploaded successfully. Processing in background.",
            policy_id=policy_id
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def process_policy_async(policy_id: str, file_path: str):
    """Process policy document asynchronously"""
    try:
        start_time = datetime.now()
        logger.info(f"Starting processing for policy: {policy_id}")
        
        # Process the policy
        result = await policy_processor.process_policy(file_path, policy_id)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Processing completed for policy: {policy_id} in {processing_time:.2f}s")
        
        # Store result
        await store_processing_result(policy_id, result, processing_time)
        
    except Exception as e:
        logger.error(f"Processing failed for policy {policy_id}: {str(e)}")
        await store_error_result(policy_id, str(e))

@app.get("/policy-status/{policy_id}")
async def get_policy_status(policy_id: str):
    """Get processing status of a policy"""
    
    status_file = f"processing_status/{policy_id}_status.json"
    
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            status = json.load(f)
        return status
    else:
        raise HTTPException(status_code=404, detail="Policy not found or still processing")

@app.get("/policy/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str):
    """Get processed policy data"""
    
    result_file = f"processed_policies/{policy_id}_result.json"
    
    if os.path.exists(result_file):
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        return PolicyResponse(
            policy_id=policy_id,
            provider=result.get('provider', 'Unknown'),
            policy_type=result.get('policy_type', 'Unknown'),
            structured_data=result.get('structured_data', {}),
            vector_embeddings=result.get('vector_embeddings', False),
            processing_timestamp=datetime.fromisoformat(result.get('timestamp', datetime.now().isoformat()))
        )
    else:
        raise HTTPException(status_code=404, detail="Policy not found")

@app.get("/policies")
async def list_policies(skip: int = 0, limit: int = 10):
    """List processed policies"""
    
    processed_dir = "processed_policies"
    if not os.path.exists(processed_dir):
        return {"policies": [], "total": 0}
    
    policy_files = [f for f in os.listdir(processed_dir) if f.endswith('_result.json')]
    total = len(policy_files)
    
    policies = []
    for file in policy_files[skip:skip+limit]:
        with open(os.path.join(processed_dir, file), 'r') as f:
            policy_data = json.load(f)
            policies.append({
                "policy_id": policy_data.get('policy_id'),
                "provider": policy_data.get('provider'),
                "policy_type": policy_data.get('policy_type'),
                "processing_date": policy_data.get('timestamp')
            })
    
    return {"policies": policies, "total": total}

@app.delete("/policy/{policy_id}")
async def delete_policy(policy_id: str):
    """Delete a processed policy"""
    
    files_to_delete = [
        f"processed_policies/{policy_id}_result.json",
        f"processing_status/{policy_id}_status.json",
        f"uploads/{policy_id}_*"
    ]
    
    deleted = False
    for pattern in files_to_delete:
        import glob
        for file in glob.glob(pattern):
            if os.path.exists(file):
                os.remove(file)
                deleted = True
    
    if deleted:
        return {"message": "Policy deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Policy not found")

async def store_processing_result(policy_id: str, result: Dict, processing_time: float):
    """Store processing result"""
    
    # Ensure directories exist
    os.makedirs("processed_policies", exist_ok=True)
    os.makedirs("processing_status", exist_ok=True)
    
    # Store result
    result_file = f"processed_policies/{policy_id}_result.json"
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Update status
    status = {
        "policy_id": policy_id,
        "status": "completed",
        "processing_time": processing_time,
        "timestamp": datetime.now().isoformat(),
        "result_file": result_file
    }
    
    status_file = f"processing_status/{policy_id}_status.json"
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)

async def store_error_result(policy_id: str, error: str):
    """Store error result"""
    
    os.makedirs("processing_status", exist_ok=True)
    
    status = {
        "policy_id": policy_id,
        "status": "failed",
        "error": error,
        "timestamp": datetime.now().isoformat()
    }
    
    status_file = f"processing_status/{policy_id}_status.json"
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)