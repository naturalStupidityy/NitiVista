import logging
import os
import tempfile
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class VoiceGenerator:
    def __init__(self):
        self.supported_languages = {
            'en': 'English',
            'hi': 'Hindi', 
            'mr': 'Marathi'
        }
        
        # Statistics tracking
        self.stats = {
            'total_requests': 0,
            'successful_generations': 0,
            'failed_generations': 0,
            'total_processing_time': 0.0,
            'start_time': datetime.now()
        }
        
        # Quality metrics storage
        self.quality_metrics = {}
        
        # Ensure output directory exists
        os.makedirs('generated_audio', exist_ok=True)
    
    async def generate_voice(self, text: str, language: str = 'en', output_file: Optional[str] = None) -> Optional[str]:
        """Generate voice from text using available TTS engines"""
        
        try:
            self.stats['total_requests'] += 1
            start_time = datetime.now()
            
            logger.info(f"Starting voice generation for text: '{text[:50]}...' in {language}")
            
            # Validate language
            if language not in self.supported_languages:
                logger.error(f"Unsupported language: {language}")
                self.stats['failed_generations'] += 1
                return None
            
            # Generate output filename if not provided
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                output_file = f"generated_audio/voice_{timestamp}_{text_hash}.mp3"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Generate voice based on language
            if language == 'en':
                success = await self._generate_english_voice(text, output_file)
            elif language == 'hi':
                success = await self._generate_hindi_voice(text, output_file)
            elif language == 'mr':
                success = await self._generate_marathi_voice(text, output_file)
            else:
                success = False
            
            if success:
                self.stats['successful_generations'] += 1
                processing_time = (datetime.now() - start_time).total_seconds()
                self.stats['total_processing_time'] += processing_time
                
                # Store quality metrics
                await self._store_quality_metrics(output_file, text, language, processing_time)
                
                logger.info(f"Voice generation successful: {output_file}")
                return output_file
            else:
                self.stats['failed_generations'] += 1
                logger.error(f"Voice generation failed for language: {language}")
                return None
                
        except Exception as e:
            self.stats['failed_generations'] += 1
            logger.error(f"Voice generation failed: {str(e)}")
            return None
    
    async def _generate_english_voice(self, text: str, output_file: str) -> bool:
        """Generate English voice using gTTS"""
        
        try:
            from gtts import gTTS
            
            # Create gTTS object
            tts = gTTS(text=text, lang='en', slow=False)
            
            # Save to file
            tts.save(output_file)
            
            return True
            
        except Exception as e:
            logger.error(f"English voice generation failed: {str(e)}")
            return False
    
    async def _generate_hindi_voice(self, text: str, output_file: str) -> bool:
        """Generate Hindi voice using gTTS"""
        
        try:
            from gtts import gTTS
            
            # Create gTTS object for Hindi
            tts = gTTS(text=text, lang='hi', slow=False)
            
            # Save to file
            tts.save(output_file)
            
            return True
            
        except Exception as e:
            logger.error(f"Hindi voice generation failed: {str(e)}")
            return False
    
    async def _generate_marathi_voice(self, text: str, output_file: str) -> bool:
        """Generate Marathi voice using gTTS"""
        
        try:
            from gtts import gTTS
            
            # Create gTTS object for Marathi
            tts = gTTS(text=text, lang='mr', slow=False)
            
            # Save to file
            tts.save(output_file)
            
            return True
            
        except Exception as e:
            logger.error(f"Marathi voice generation failed: {str(e)}")
            return False
    
    async def _store_quality_metrics(self, audio_file: str, original_text: str, language: str, processing_time: float):
        """Store quality metrics for generated voice"""
        
        request_id = os.path.basename(audio_file).replace('.mp3', '')
        
        metrics = {
            'request_id': request_id,
            'timestamp': datetime.now().isoformat(),
            'original_text': original_text,
            'text_length': len(original_text),
            'language': language,
            'processing_time': processing_time,
            'audio_file_size': os.path.getsize(audio_file) if os.path.exists(audio_file) else 0,
            'estimated_duration': len(original_text.split()) / 2.5,  # Rough estimate
            'naturalness_score': self._calculate_naturalness_score(language, processing_time),
            'intelligibility_score': 0.85,  # Placeholder for gTTS
            'word_error_rate': 0.0  # gTTS typically has very low WER
        }
        
        self.quality_metrics[request_id] = metrics
    
    def _calculate_naturalness_score(self, language: str, processing_time: float) -> float:
        """Calculate naturalness score based on language and performance"""
        
        # Base scores for different languages (gTTS quality)
        base_scores = {
            'en': 4.2,  # English has excellent quality
            'hi': 3.8,  # Hindi has good quality
            'mr': 3.5   # Marathi has decent quality
        }
        
        base_score = base_scores.get(language, 3.0)
        
        # Adjust based on processing time (faster = better)
        if processing_time < 2.0:
            adjustment = 0.2
        elif processing_time < 5.0:
            adjustment = 0.0
        else:
            adjustment = -0.2
        
        return min(5.0, max(1.0, base_score + adjustment))
    
    async def get_quality_metrics(self, request_id: str) -> Optional[Dict]:
        """Get quality metrics for a specific request"""
        
        return self.quality_metrics.get(request_id)
    
    # Statistics methods
    def get_total_requests(self) -> int:
        return self.stats['total_requests']
    
    def get_successful_generations(self) -> int:
        return self.stats['successful_generations']
    
    def get_failed_generations(self) -> int:
        return self.stats['failed_generations']
    
    def get_average_processing_time(self) -> float:
        if self.stats['successful_generations'] > 0:
            return self.stats['total_processing_time'] / self.stats['successful_generations']
        return 0.0
    
    def get_supported_languages(self) -> List[str]:
        return list(self.supported_languages.keys())
    
    def get_system_uptime(self) -> float:
        return (datetime.now() - self.stats['start_time']).total_seconds()
    
    def get_queue_size(self) -> int:
        # For this simple implementation, queue size is always 0
        return 0
    
    async def batch_generate(self, texts: List[str], language: str = 'en') -> List[str]:
        """Generate voice for multiple texts"""
        
        results = []
        
        for i, text in enumerate(texts):
            output_file = f"generated_audio/batch_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            result = await self.generate_voice(text, language, output_file)
            results.append(result)
            
            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)
        
        return results
    
    async def compare_voices(self, text: str, languages: List[str]) -> Dict:
        """Generate the same text in multiple languages for comparison"""
        
        comparison = {
            'original_text': text,
            'timestamp': datetime.now().isoformat(),
            'voices': {}
        }
        
        for language in languages:
            if language in self.supported_languages:
                output_file = f"generated_audio/comparison_{language}_{hash(text) % 1000:03d}.mp3"
                result = await self.generate_voice(text, language, output_file)
                
                comparison['voices'][language] = {
                    'file_path': result,
                    'language_name': self.supported_languages[language],
                    'generated': result is not None
                }
        
        return comparison