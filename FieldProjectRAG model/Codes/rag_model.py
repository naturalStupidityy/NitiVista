"""
RAG Model Implementation for NitiVista-EN
=========================================

Retrieval-Augmented Generation system for insurance policy Q&A.
Provides intelligent question answering based on policy document content.

Author: Team NitiVista
Date: November 10, 2025
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import hashlib

# External dependencies
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from transformers import (
    pipeline, 
    AutoTokenizer, 
    AutoModelForQuestionAnswering,
    AutoModel,
    AutoConfig
)
import torch
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RAG-Model')

class PolicyRAGSystem:
    """
    Retrieval-Augmented Generation system for insurance policy documents
    """
    
    def __init__(self, 
                 model_name: str = "distilbert-base-cased-distilled-squad",
                 embedding_model: str = "paraphrase-MiniLM-L6-v2",
                 collection_name: str = "insurance_policies",
                 persist_directory: str = "./chroma_db"):
        """
        Initialize the RAG system
        
        Args:
            model_name: QA model name
            embedding_model: Sentence transformer model for embeddings
            collection_name: ChromaDB collection name
            persist_directory: Directory for persistent storage
        """
        self.model_name = model_name
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Initialize models
        self._initialize_models()
        
        # Initialize vector database
        self._initialize_vector_db()
        
        # Load or create collection
        self._setup_collection()
        
        logger.info(f"RAG System initialized with model: {model_name}")
    
    def _initialize_models(self):
        """Initialize transformer models"""
        try:
            # Initialize QA pipeline
            self.qa_pipeline = pipeline(
                "question-answering",
                model=self.model_name,
                tokenizer=self.model_name,
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            
            # Initialize tokenizer for additional processing
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            logger.info("Models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing models: {str(e)}")
            raise
    
    def _initialize_vector_db(self):
        """Initialize ChromaDB vector database"""
        try:
            # Create persistent directory if it doesn't exist
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory
            ))
            
            logger.info("Vector database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing vector DB: {str(e)}")
            raise
    
    def _setup_collection(self):
        """Setup or load the policy collection"""
        try:
            # Try to get existing collection
            try:
                self.collection = self.chroma_client.get_collection(self.collection_name)
                logger.info(f"Loaded existing collection: {self.collection_name}")
            except Exception:
                # Create new collection
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Insurance policy documents for RAG"}
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Error setting up collection: {str(e)}")
            raise
    
    async def add_policy_document(self, 
                                policy_text: str, 
                                metadata: Dict[str, Any],
                                chunk_size: int = 512,
                                chunk_overlap: int = 50) -> str:
        """
        Add a policy document to the RAG system
        
        Args:
            policy_text: Full text of the policy document
            metadata: Metadata about the policy
            chunk_size: Size of text chunks for processing
            chunk_overlap: Overlap between chunks
            
        Returns:
            Document ID for reference
        """
        try:
            # Generate document ID
            doc_id = hashlib.md5(policy_text.encode()).hexdigest()
            
            # Split text into chunks
            chunks = self._split_text_into_chunks(policy_text, chunk_size, chunk_overlap)
            
            # Process chunks
            documents = []
            embeddings = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_{i}"
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_id': i,
                    'chunk_text': chunk[:200] + "..." if len(chunk) > 200 else chunk,
                    'total_chunks': len(chunks)
                })
                
                # Generate embedding
                embedding = self.embedding_model.encode(chunk).tolist()
                
                documents.append(chunk)
                embeddings.append(embedding)
                metadatas.append(chunk_metadata)
                ids.append(chunk_id)
            
            # Add to collection
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added policy document with {len(chunks)} chunks: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error adding policy document: {str(e)}")
            raise
    
    def _split_text_into_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        
        while start < len(text):
            # Find end of chunk
            end = start + chunk_size
            
            # If not the last chunk, try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + chunk_size * 0.8:  # If sentence end is in last 20%
                    end = sentence_end + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move to next chunk with overlap
            start = end - chunk_overlap
            
            # Safety check to prevent infinite loop
            if start >= len(text) or len(chunks) > 1000:
                break
        
        return chunks
    
    async def answer_question(self, 
                            question: str, 
                            policy_id: Optional[str] = None,
                            top_k: int = 5,
                            confidence_threshold: float = 0.3) -> Dict[str, Any]:
        """
        Answer a question using the RAG system
        
        Args:
            question: User's question
            policy_id: Optional specific policy to search
            top_k: Number of relevant chunks to retrieve
            confidence_threshold: Minimum confidence for valid answers
            
        Returns:
            Answer with metadata
        """
        try:
            # Retrieve relevant contexts
            contexts = await self._retrieve_relevant_contexts(question, policy_id, top_k)
            
            if not contexts:
                return {
                    'answer': "I don't have enough information to answer that question. Please upload your policy document first.",
                    'confidence': 0.0,
                    'source': 'None',
                    'question': question,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Generate answer using QA model
            best_answer = None
            best_confidence = 0.0
            
            for context in contexts:
                try:
                    # Use QA pipeline
                    qa_result = self.qa_pipeline(
                        question=question,
                        context=context['text'],
                        handle_impossible_answer=True,
                        max_answer_len=100
                    )
                    
                    if qa_result and qa_result['score'] > best_confidence:
                        best_confidence = qa_result['score']
                        best_answer = {
                            'answer': qa_result['answer'],
                            'confidence': qa_result['score'],
                            'source': context['metadata'],
                            'context': context['text']
                        }
                        
                except Exception as e:
                    logger.warning(f"Error in QA for context: {str(e)}")
                    continue
            
            # If no good answer found, use fallback
            if not best_answer or best_confidence < confidence_threshold:
                # Try to generate answer from context summary
                best_answer = await self._generate_fallback_answer(question, contexts)
            
            # Format final response
            response = {
                'answer': best_answer['answer'],
                'confidence': best_answer['confidence'],
                'source': best_answer.get('source', 'Unknown'),
                'question': question,
                'timestamp': datetime.now().isoformat(),
                'suggested_questions': self._generate_follow_up_questions(question, best_answer['answer'])
            }
            
            logger.info(f"Question answered with confidence {response['confidence']:.3f}")
            return response
            
        except Exception as e:
            logger.error(f"Error in answer_question: {str(e)}")
            return {
                'answer': "Sorry, I encountered an error processing your question. Please try again.",
                'confidence': 0.0,
                'source': 'Error',
                'question': question,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _retrieve_relevant_contexts(self, question: str, policy_id: Optional[str], top_k: int) -> List[Dict]:
        """Retrieve relevant contexts from vector database"""
        try:
            # Query parameters
            query_params = {
                'query_texts': [question],
                'n_results': top_k,
                'include': ['documents', 'metadatas', 'distances']
            }
            
            # Add policy filter if specified
            if policy_id:
                query_params['where'] = {"doc_id": policy_id}
            
            # Execute query
            results = self.collection.query(**query_params)
            
            # Format results
            contexts = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    if doc:  # Check if document exists
                        context = {
                            'text': doc,
                            'metadata': results['metadatas'][0][i] if results['metadatas'] and i < len(results['metadatas'][0]) else {},
                            'distance': results['distances'][0][i] if results['distances'] and i < len(results['distances'][0]) else 0.0,
                            'score': 1.0 - (results['distances'][0][i] if results['distances'] and i < len(results['distances'][0]) else 0.0)
                        }
                        contexts.append(context)
            
            # Sort by relevance score
            contexts.sort(key=lambda x: x['score'], reverse=True)
            
            return contexts[:top_k]
            
        except Exception as e:
            logger.error(f"Error retrieving contexts: {str(e)}")
            return []
    
    async def _generate_fallback_answer(self, question: str, contexts: List[Dict]) -> Dict:
        """Generate fallback answer when QA model fails"""
        try:
            # Combine contexts
            combined_context = " ".join([ctx['text'][:200] for ctx in contexts[:2]])
            
            # Simple pattern matching for common questions
            question_lower = question.lower()
            
            if any(word in question_lower for word in ['cover', 'include', 'what']):
                answer = "Based on your policy document, the coverage includes: " + \
                        combined_context[:150] + "..."
            elif any(word in question_lower for word in ['exclude', 'not cover']):
                answer = "Your policy exclusions include: " + combined_context[:150] + "..."
            elif any(word in question_lower for word in ['claim', 'how']):
                answer = "For claims, please refer to your policy document or contact customer service."
            elif any(word in question_lower for word in ['premium', 'cost', 'price']):
                answer = "Premium information can be found in your policy document."
            else:
                answer = "I found some relevant information in your policy, but please check the full document for complete details."
            
            return {
                'answer': answer,
                'confidence': 0.2,  # Low confidence for fallback
                'source': 'Fallback'
            }
            
        except Exception as e:
            logger.error(f"Error in fallback answer generation: {str(e)}")
            return {
                'answer': "I'm not sure about that. Please check your policy document.",
                'confidence': 0.0,
                'source': 'Error'
            }
    
    def _generate_follow_up_questions(self, original_question: str, answer: str) -> List[str]:
        """Generate suggested follow-up questions"""
        questions = []
        
        # Based on original question type
        question_lower = original_question.lower()
        
        if 'cover' in question_lower:
            questions.extend([
                "What is not covered by my policy?",
                "How much coverage do I have?",
                "Can I add additional coverage?"
            ])
        elif 'premium' in question_lower or 'cost' in question_lower:
            questions.extend([
                "When is my premium due?",
                "How can I pay my premium?",
                "What happens if I miss a payment?"
            ])
        elif 'claim' in question_lower:
            questions.extend([
                "What documents do I need for a claim?",
                "How long does claim processing take?",
                "Can I track my claim status?"
            ])
        else:
            questions.extend([
                "What is my policy number?",
                "When does my policy expire?",
                "How do I contact customer service?"
            ])
        
        return questions[:3]  # Return top 3
    
    async def get_policy_summary(self, policy_id: str) -> Dict[str, Any]:
        """Get summary of a specific policy"""
        try:
            # Get all chunks for the policy
            results = self.collection.get(
                where={"doc_id": policy_id},
                include=['documents', 'metadatas']
            )
            
            if not results['documents']:
                return {
                    'error': 'Policy not found',
                    'policy_id': policy_id
                }
            
            # Extract key information from chunks
            full_text = " ".join(results['documents'])
            
            summary = {
                'policy_id': policy_id,
                'total_chunks': len(results['documents']),
                'document_length': len(full_text),
                'processing_date': results['metadatas'][0].get('processing_date', 'Unknown') if results['metadatas'] else 'Unknown',
                'sample_text': full_text[:500] + "..." if len(full_text) > 500 else full_text
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting policy summary: {str(e)}")
            return {
                'error': str(e),
                'policy_id': policy_id
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            # Get collection count
            count = self.collection.count()
            
            stats = {
                'total_documents': count,
                'collection_name': self.collection_name,
                'model_name': self.model_name,
                'embedding_model': self.embedding_model_name,
                'persist_directory': self.persist_directory,
                'system_status': 'Active',
                'timestamp': datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {str(e)}")
            return {
                'error': str(e),
                'system_status': 'Error'
            }
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy document from the system"""
        try:
            # Get all chunk IDs for the policy
            results = self.collection.get(
                where={"doc_id": policy_id},
                include=['metadatas']
            )
            
            if not results['ids']:
                logger.warning(f"Policy not found for deletion: {policy_id}")
                return False
            
            # Delete all chunks
            self.collection.delete(ids=results['ids'])
            
            logger.info(f"Deleted policy: {policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting policy: {str(e)}")
            return False
    
    async def update_policy(self, policy_id: str, new_text: str, new_metadata: Dict = None) -> bool:
        """Update an existing policy document"""
        try:
            # Delete old version
            await self.delete_policy(policy_id)
            
            # Add new version
            metadata = new_metadata or {}
            metadata['doc_id'] = policy_id
            metadata['updated_date'] = datetime.now().isoformat()
            
            await self.add_policy_document(new_text, metadata)
            
            logger.info(f"Updated policy: {policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating policy: {str(e)}")
            return False


class RAGChatInterface:
    """Chat interface for the RAG system"""
    
    def __init__(self, rag_system: PolicyRAGSystem):
        self.rag_system = rag_system
        self.conversation_history = {}
        logger.info("RAG Chat Interface initialized")
    
    async def chat(self, 
                   user_id: str, 
                   message: str, 
                   policy_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle chat conversation
        
        Args:
            user_id: Unique user identifier
            message: User's message
            policy_id: Optional policy context
            
        Returns:
            Chat response with conversation context
        """
        try:
            # Initialize conversation history for new user
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = {
                    'messages': [],
                    'policy_context': policy_id,
                    'start_time': datetime.now().isoformat()
                }
            
            # Add user message to history
            self.conversation_history[user_id]['messages'].append({
                'role': 'user',
                'content': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Process the message
            if any(word in message.lower() for word in ['hello', 'hi', 'namaste', 'नमस्ते']):
                response = await self._handle_greeting(user_id, policy_id)
            elif any(word in message.lower() for word in ['help', 'मदद']):
                response = await self._handle_help_request(user_id, policy_id)
            elif any(word in message.lower() for word in ['bye', 'goodbye', 'धन्यवाद']):
                response = await self._handle_goodbye(user_id)
            else:
                # Use RAG for policy-related questions
                response = await self.rag_system.answer_question(
                    question=message,
                    policy_id=policy_id
                )
            
            # Add assistant response to history
            self.conversation_history[user_id]['messages'].append({
                'role': 'assistant',
                'content': response['answer'],
                'timestamp': datetime.now().isoformat()
            })
            
            # Add conversation context
            response['conversation_id'] = user_id
            response['message_count'] = len(self.conversation_history[user_id]['messages'])
            
            return response
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return {
                'answer': "Sorry, I'm having trouble understanding. Can you please rephrase?",
                'confidence': 0.0,
                'source': 'Error',
                'conversation_id': user_id
            }
    
    async def _handle_greeting(self, user_id: str, policy_id: Optional[str]) -> Dict[str, Any]:
        """Handle greeting messages"""
        greeting = """
Hello! I'm NitiVista-EN, your insurance assistant. I can help you understand your insurance policy in simple language.

You can ask me questions like:
• What does my policy cover?
• What is not covered?
• How do I make a claim?
• What is my premium amount?

Just upload your policy document and ask your questions!
        """
        
        return {
            'answer': greeting.strip(),
            'confidence': 1.0,
            'source': 'Greeting',
            'suggested_questions': [
                "What does my policy cover?",
                "How do I make a claim?",
                "What is my premium amount?"
            ]
        }
    
    async def _handle_help_request(self, user_id: str, policy_id: Optional[str]) -> Dict[str, Any]:
        """Handle help requests"""
        help_text = """
I can help you with:

📋 *Policy Understanding*
• What your policy covers and doesn't cover
• Premium amounts and payment details
• Policy validity and renewal information

🏥 *Claims Information*
• How to file a claim
• Required documents for claims
• Claim processing timeline

📞 *Contact Information*
• Customer service numbers
• Branch office details
• Online service portals

To get started, please upload your policy document PDF and I'll explain it in simple language!
        """
        
        return {
            'answer': help_text.strip(),
            'confidence': 1.0,
            'source': 'Help',
            'suggested_questions': [
                "How do I upload my policy?",
                "What languages do you support?",
                "Is my information secure?"
            ]
        }
    
    async def _handle_goodbye(self, user_id: str) -> Dict[str, Any]:
        """Handle goodbye messages"""
        goodbye = """
Thank you for using NitiVista-EN! I hope I was able to help you understand your insurance policy better.

Remember:
• Keep your policy document safe
• Pay premiums on time
• Contact customer service for claims

Feel free to come back anytime you have questions about insurance!

Have a great day! 😊
        """
        
        # Clear conversation history after goodbye
        if user_id in self.conversation_history:
            self.conversation_history[user_id]['ended'] = True
        
        return {
            'answer': goodbye.strip(),
            'confidence': 1.0,
            'source': 'Goodbye'
        }
    
    def get_conversation_history(self, user_id: str) -> Optional[Dict]:
        """Get conversation history for a user"""
        return self.conversation_history.get(user_id)
    
    def clear_conversation_history(self, user_id: str) -> bool:
        """Clear conversation history for a user"""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
            return True
        return False


# Example usage and testing
async def test_rag_system():
    """Test the RAG system with sample data"""
    
    # Initialize RAG system
    rag_system = PolicyRAGSystem()
    
    # Sample policy text
    sample_policy = """
    STAR HEALTH INSURANCE POLICY
    
    Policy Number: SH-2025-123456
    Policy Holder: John Doe
    
    COVERAGE DETAILS:
    - Hospitalization expenses up to ₹5,00,000
    - Pre and post hospitalization (30/60 days)
    - Day care procedures
    - Ambulance charges up to ₹2,000 per claim
    - No room rent restrictions
    
    EXCLUSIONS:
    - Pre-existing diseases (first 2 years)
    - Cosmetic surgery
    - Dental treatment (unless accidental)
    - Pregnancy and childbirth (first 2 years)
    - Substance abuse related treatments
    
    PREMIUM: ₹15,000 annually
    VALIDITY: January 1, 2025 to December 31, 2025
    
    CLAIM PROCESS:
    1. Inform within 48 hours of hospitalization
    2. Submit claim form with medical documents
    3. Pre-authorization for cashless treatment
    4. Reimbursement within 15 days
    
    Contact: 1800-123-4567
    Email: help@starhealth.com
    """
    
    # Add policy to system
    metadata = {
        'policy_number': 'SH-2025-123456',
        'insurer': 'Star Health',
        'policy_holder': 'John Doe',
        'processing_date': datetime.now().isoformat()
    }
    
    doc_id = await rag_system.add_policy_document(sample_policy, metadata)
    print(f"Added policy document with ID: {doc_id}")
    
    # Test questions
    questions = [
        "What does my policy cover?",
        "What is not covered?",
        "How much is my premium?",
        "How do I make a claim?",
        "What is my policy number?",
        "When does my policy expire?",
        "Can I get cashless treatment?",
        "What is the contact number?"
    ]
    
    for question in questions:
        print(f"\n❓ Question: {question}")
        answer = await rag_system.answer_question(question, policy_id=doc_id)
        print(f"🤖 Answer: {answer['answer']}")
        print(f"📊 Confidence: {answer['confidence']:.2f}")
        if answer['suggested_questions']:
            print(f"💡 Suggested: {', '.join(answer['suggested_questions'])}")
    
    # Test chat interface
    print("\n" + "="*50)
    print("CHAT INTERFACE TEST")
    print("="*50)
    
    chat_interface = RAGChatInterface(rag_system)
    
    # Simulate conversation
    user_messages = [
        "Hello",
        "What does my policy cover?",
        "What about exclusions?",
        "Help",
        "Thank you, goodbye"
    ]
    
    user_id = "test_user_123"
    
    for message in user_messages:
        print(f"\n👤 User: {message}")
        response = await chat_interface.chat(user_id, message, policy_id=doc_id)
        print(f"🤖 Assistant: {response['answer'][:200]}...")
    
    # Get system stats
    stats = rag_system.get_system_stats()
    print(f"\n📊 System Stats: {stats}")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_rag_system())