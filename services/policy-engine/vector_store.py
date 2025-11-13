import logging
import json
from typing import Dict, List, Optional, Any
import numpy as np
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class VectorStore:
    """Simple vector store implementation for policy embeddings"""
    
    def __init__(self):
        self.embeddings = {}  # Store embeddings by policy_id
        self.chunks = {}      # Store text chunks by chunk_id
        self.index = {}       # Simple search index
        self.storage_dir = "vector_store"
        
        # Create storage directory
        import os
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize embedding model (simplified)
        self.embedding_dim = 384  # Dimension for sentence embeddings
        
    async def create_embeddings(self, structured_data: Dict, policy_id: str) -> bool:
        """Create vector embeddings for policy data"""
        
        try:
            logger.info(f"Creating embeddings for policy: {policy_id}")
            
            all_chunks = []
            chunk_id = 0
            
            # Create chunks from different sections
            for section, content in structured_data.items():
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, str) and len(item.strip()) > 10:
                            chunk = {
                                "chunk_id": f"{policy_id}_chunk_{chunk_id}",
                                "policy_id": policy_id,
                                "section": section,
                                "content": item.strip(),
                                "content_hash": self._hash_content(item.strip()),
                                "timestamp": datetime.now().isoformat()
                            }
                            all_chunks.append(chunk)
                            chunk_id += 1
                
                elif isinstance(content, str) and len(content.strip()) > 10:
                    chunk = {
                        "chunk_id": f"{policy_id}_chunk_{chunk_id}",
                        "policy_id": policy_id,
                        "section": section,
                        "content": content.strip(),
                        "content_hash": self._hash_content(content.strip()),
                        "timestamp": datetime.now().isoformat()
                    }
                    all_chunks.append(chunk)
                    chunk_id += 1
            
            # Generate embeddings for chunks
            embeddings = []
            for chunk in all_chunks:
                embedding = await self._generate_embedding(chunk["content"])
                
                embedding_data = {
                    "chunk_id": chunk["chunk_id"],
                    "policy_id": policy_id,
                    "embedding": embedding.tolist(),  # Convert to list for JSON serialization
                    "section": chunk["section"],
                    "content_length": len(chunk["content"]),
                    "timestamp": chunk["timestamp"]
                }
                
                embeddings.append(embedding_data)
            
            # Store embeddings and chunks
            self.embeddings[policy_id] = embeddings
            
            for chunk in all_chunks:
                self.chunks[chunk["chunk_id"]] = chunk
            
            # Update search index
            await self._update_search_index(policy_id, embeddings)
            
            # Persist to disk
            await self._save_to_disk(policy_id)
            
            logger.info(f"Successfully created {len(embeddings)} embeddings for {policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create embeddings for {policy_id}: {str(e)}")
            return False
    
    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text (simplified implementation)"""
        
        # In a real implementation, this would use a proper embedding model
        # like Sentence-BERT, Word2Vec, or other NLP models
        
        # For this demo, we'll create a simple hash-based embedding
        # that maintains some semantic properties
        
        try:
            # Simple approach: create embedding based on word frequencies and positions
            words = text.lower().split()
            
            # Initialize embedding vector
            embedding = np.zeros(self.embedding_dim)
            
            # Use word hash to distribute across dimensions
            for i, word in enumerate(words[:50]):  # Limit to first 50 words
                word_hash = hash(word) % self.embedding_dim
                embedding[word_hash] += 1.0 / (i + 1)  # Decay by position
            
            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            # Return random embedding as fallback
            return np.random.randn(self.embedding_dim)
    
    def _hash_content(self, content: str) -> str:
        """Generate hash for content"""
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    async def _update_search_index(self, policy_id: str, embeddings: List[Dict]):
        """Update search index with new embeddings"""
        
        if policy_id not in self.index:
            self.index[policy_id] = {}
        
        for embedding_data in embeddings:
            chunk_id = embedding_data["chunk_id"]
            section = embedding_data["section"]
            
            # Index by section
            if section not in self.index[policy_id]:
                self.index[policy_id][section] = []
            
            self.index[policy_id][section].append({
                "chunk_id": chunk_id,
                "content_length": embedding_data["content_length"]
            })
    
    async def search_similar(self, query: str, policy_id: Optional[str] = None, top_k: int = 5) -> List[Dict]:
        """Search for similar content using embeddings"""
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            results = []
            
            # Search in specific policy or all policies
            target_policies = [policy_id] if policy_id else list(self.embeddings.keys())
            
            for policy in target_policies:
                if policy not in self.embeddings:
                    continue
                
                for embedding_data in self.embeddings[policy]:
                    # Calculate similarity (cosine similarity)
                    similarity = self._cosine_similarity(
                        query_embedding,
                        np.array(embedding_data["embedding"])
                    )
                    
                    if similarity > 0.3:  # Threshold
                        chunk_info = self.chunks.get(embedding_data["chunk_id"], {})
                        
                        results.append({
                            "chunk_id": embedding_data["chunk_id"],
                            "policy_id": policy,
                            "section": embedding_data["section"],
                            "content": chunk_info.get("content", ""),
                            "similarity_score": similarity,
                            "content_length": embedding_data["content_length"]
                        })
            
            # Sort by similarity and return top_k
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def get_policy_chunks(self, policy_id: str, section: Optional[str] = None) -> List[Dict]:
        """Get chunks for a specific policy and optionally section"""
        
        chunks = []
        
        for chunk_id, chunk in self.chunks.items():
            if chunk["policy_id"] == policy_id:
                if section is None or chunk["section"] == section:
                    chunks.append(chunk)
        
        return chunks
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete all embeddings for a policy"""
        
        try:
            # Remove from embeddings
            if policy_id in self.embeddings:
                del self.embeddings[policy_id]
            
            # Remove from index
            if policy_id in self.index:
                del self.index[policy_id]
            
            # Remove chunks
            chunks_to_remove = [
                chunk_id for chunk_id, chunk in self.chunks.items()
                if chunk["policy_id"] == policy_id
            ]
            
            for chunk_id in chunks_to_remove:
                del self.chunks[chunk_id]
            
            # Remove from disk
            await self._delete_from_disk(policy_id)
            
            logger.info(f"Deleted all embeddings for policy: {policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete policy embeddings: {str(e)}")
            return False
    
    async def _save_to_disk(self, policy_id: str):
        """Save embeddings to disk"""
        
        try:
            # Save embeddings
            embeddings_file = f"{self.storage_dir}/{policy_id}_embeddings.json"
            with open(embeddings_file, 'w') as f:
                json.dump(self.embeddings.get(policy_id, []), f, indent=2)
            
            # Save chunks
            policy_chunks = {
                chunk_id: chunk for chunk_id, chunk in self.chunks.items()
                if chunk["policy_id"] == policy_id
            }
            
            chunks_file = f"{self.storage_dir}/{policy_id}_chunks.json"
            with open(chunks_file, 'w') as f:
                json.dump(policy_chunks, f, indent=2)
            
            # Save index
            index_file = f"{self.storage_dir}/{policy_id}_index.json"
            with open(index_file, 'w') as f:
                json.dump(self.index.get(policy_id, {}), f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save to disk: {str(e)}")
    
    async def _delete_from_disk(self, policy_id: str):
        """Delete policy files from disk"""
        
        import os
        
        files_to_delete = [
            f"{self.storage_dir}/{policy_id}_embeddings.json",
            f"{self.storage_dir}/{policy_id}_chunks.json",
            f"{self.storage_dir}/{policy_id}_index.json"
        ]
        
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    async def load_from_disk(self, policy_id: str) -> bool:
        """Load embeddings from disk"""
        
        try:
            # Load embeddings
            embeddings_file = f"{self.storage_dir}/{policy_id}_embeddings.json"
            if os.path.exists(embeddings_file):
                with open(embeddings_file, 'r') as f:
                    self.embeddings[policy_id] = json.load(f)
            
            # Load chunks
            chunks_file = f"{self.storage_dir}/{policy_id}_chunks.json"
            if os.path.exists(chunks_file):
                with open(chunks_file, 'r') as f:
                    policy_chunks = json.load(f)
                    self.chunks.update(policy_chunks)
            
            # Load index
            index_file = f"{self.storage_dir}/{policy_id}_index.json"
            if os.path.exists(index_file):
                with open(index_file, 'r') as f:
                    self.index[policy_id] = json.load(f)
            
            logger.info(f"Loaded embeddings for policy: {policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load from disk: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        
        total_embeddings = sum(len(embeddings) for embeddings in self.embeddings.values())
        total_chunks = len(self.chunks)
        total_policies = len(self.embeddings)
        
        return {
            "total_policies": total_policies,
            "total_embeddings": total_embeddings,
            "total_chunks": total_chunks,
            "embedding_dimension": self.embedding_dim,
            "storage_directory": self.storage_dir
        }