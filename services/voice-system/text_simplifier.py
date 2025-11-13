import logging
import re
from typing import Dict, List, Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)

class TextSimplifier:
    def __init__(self):
        # Define complex words and their simple alternatives
        self.complex_words = {
            'en': {
                'comprehensive': 'complete',
                'deductible': 'amount you pay first',
                'pre-existing': 'existing before',
                'hospitalization': 'hospital stay',
                'exclusions': 'things not covered',
                'provisions': 'rules',
                'beneficiary': 'person who gets money',
                'nominee': 'person you choose',
                'maturity': 'when policy ends',
                'premium': 'payment',
                'coverage': 'protection',
                'liability': 'responsibility',
                'indemnity': 'protection',
                'aggregate': 'total',
                'commencement': 'start',
                'termination': 'end',
                'subrogation': 'transfer of rights',
                'arbitration': 'settlement',
                'jurisdiction': 'legal area',
                'notwithstanding': 'despite',
                'whereas': 'because'
            },
            'hi': {
                'समग्र': 'पूरा',
                'कटौती योग्य': 'पहले भुगतान की रकम',
                'पूर्व अस्तित्व': 'पहले से मौजूद',
                'अस्पताल में भर्ती': 'अस्पताल में रहना',
                'अपवाद': 'जो शामिल नहीं है',
                'प्रावधान': 'नियम',
                'लाभार्थी': 'व्यक्ति जिसे पैसा मिलता है',
                'नामांकित व्यक्ति': 'आपके द्वारा चुना गया व्यक्ति',
                'परिपक्वता': 'जब पॉलिसी खत्म होती है',
                'प्रीमियम': 'भुगतान',
                'कवरेज': 'सुरक्षा',
                'देयता': 'जिम्मेदारी',
                'हानि पूर्ति': 'सुरक्षा',
                'कुल': 'कुल योग',
                'प्रारंभ': 'शुरुआत',
                'समाप्ति': 'अंत',
                'अधिकार स्थानांतरण': 'अधिकारों का हस्तांतरण',
                'मध्यस्थता': 'समझौता',
                'अधिकार क्षेत्र': 'कानूनी क्षेत्र'
            },
            'mr': {
                'समग्र': 'संपूर्ण',
                'वजवटण्याजोगी रक्कम': 'आधी द्यायची रक्कम',
                'अस्तित्वात असलेली': 'आधीपासून असलेली',
                'रुग्णालयात दाखल': 'रुग्णालयात राहणे',
                'अपवाद': 'जे समाविष्ट नाही',
                'तरतुदी': 'नियम',
                'लाभार्थी': 'पैसे मिळणारा व्यक्ती',
                'नामनिर्देशित व्यक्ती': 'तुमच्या निवडलेली व्यक्ती',
                'पक्वता': 'जेव्हा पॉलिसी संपते',
                'प्रीमियम': 'देयक',
                'कव्हरेज': 'संरक्षण',
                'जबाबदारी': 'जबाबदारी',
                'हमी': 'संरक्षण',
                'एकूण': 'एकूण रक्कम',
                'सुरुवात': 'सुरुवात',
                'समाप्ती': 'शेवट',
                'हक्क हस्तांतरण': 'हक्कांचे हस्तांतरण',
                'मध्यस्थता': 'समेट',
                'अधिकार क्षेत्र': 'कायदेशीर क्षेत्र'
            }
        }
        
        # Grade level word lists
        self.grade_words = {
            1: ['cat', 'dog', 'run', 'jump', 'house', 'car', 'book', 'water', 'food', 'good'],
            2: ['animal', 'friend', 'school', 'family', 'happy', 'clean', 'help', 'work', 'play', 'love'],
            3: ['important', 'different', 'remember', 'exercise', 'healthy', 'protect', 'money', 'time', 'safe', 'care'],
            4: ['insurance', 'policy', 'doctor', 'hospital', 'payment', 'coverage', 'benefit', 'claim', 'premium', 'protection'],
            5: ['company', 'service', 'provide', 'include', 'exclude', 'condition', 'agreement', 'contract', 'period', 'amount'],
            6: ['comprehensive', 'deductible', 'liability', 'settlement', 'procedure', 'documentation', 'verification', 'approval', 'disbursement', 'termination']
        }
    
    async def simplify(self, text: str, target_grade: int = 6, language: str = 'en') -> str:
        """Simplify text to target grade level"""
        
        try:
            logger.info(f"Simplifying text to grade {target_grade} in {language}")
            
            if language not in self.complex_words:
                logger.warning(f"Language {language} not supported, using English")
                language = 'en'
            
            # Step 1: Replace complex words with simpler alternatives
            simplified_text = await self._replace_complex_words(text, language)
            
            # Step 2: Break long sentences
            simplified_text = await self._break_long_sentences(simplified_text, target_grade)
            
            # Step 3: Remove unnecessary words and phrases
            simplified_text = await self._remove_redundancies(simplified_text)
            
            # Step 4: Add explanations for technical terms
            simplified_text = await self._add_explanations(simplified_text, language)
            
            # Step 5: Format for better readability
            simplified_text = await self._format_for_readability(simplified_text)
            
            logger.info(f"Text simplification completed")
            return simplified_text
            
        except Exception as e:
            logger.error(f"Text simplification failed: {str(e)}")
            return text  # Return original text on failure
    
    async def _replace_complex_words(self, text: str, language: str) -> str:
        """Replace complex words with simpler alternatives"""
        
        word_map = self.complex_words.get(language, self.complex_words['en'])
        
        # Case-insensitive replacement while preserving case
        for complex_word, simple_word in word_map.items():
            # Replace whole words only
            pattern = r'\b' + re.escape(complex_word) + r'\b'
            text = re.sub(pattern, simple_word, text, flags=re.IGNORECASE)
        
        return text
    
    async def _break_long_sentences(self, text: str, target_grade: int) -> str:
        """Break long sentences into shorter ones"""
        
        sentences = self._split_into_sentences(text)
        simplified_sentences = []
        
        for sentence in sentences:
            words = sentence.split()
            
            # Break sentences longer than target grade level
            max_words = target_grade * 3 + 5  # Rough heuristic
            
            if len(words) > max_words:
                # Find good break points
                break_points = self._find_sentence_breaks(words, max_words)
                
                if break_points:
                    start = 0
                    for break_point in break_points:
                        part = ' '.join(words[start:break_point])
                        if len(part.strip()) > 10:  # Minimum length
                            simplified_sentences.append(part.strip() + '.')
                        start = break_point
                    
                    # Add remaining part
                    if start < len(words):
                        remaining = ' '.join(words[start:])
                        if len(remaining.strip()) > 10:
                            simplified_sentences.append(remaining.strip() + '.')
                else:
                    simplified_sentences.append(sentence)
            else:
                simplified_sentences.append(sentence)
        
        return ' '.join(simplified_sentences)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _find_sentence_breaks(self, words: List[str], max_words: int) -> List[int]:
        """Find good points to break a long sentence"""
        
        break_points = []
        current_length = 0
        
        for i, word in enumerate(words):
            current_length += 1
            
            # Look for good break points
            if (current_length >= max_words * 0.8 and  # Near target length
                word in ['and', 'or', 'but', 'which', 'that', 'who'] and
                i + 1 < len(words)):
                
                break_points.append(i + 1)
                current_length = 0
            
            # Force break if too long
            elif current_length >= max_words:
                break_points.append(i)
                current_length = 0
        
        return break_points
    
    async def _remove_redundancies(self, text: str) -> str:
        """Remove redundant words and phrases"""
        
        redundancies = [
            (r'\b(in order) to\b', 'to'),
            (r'\bdue to the fact that\b', 'because'),
            (r'\bat this point in time\b', 'now'),
            (r'\bin the event that\b', 'if'),
            (r'\bfor the purpose of\b', 'to'),
            (r'\bin spite of the fact that\b', 'although'),
            (r'\bwith regard to\b', 'about'),
            (r'\bpertaining to\b', 'about'),
            (r'\bas to whether\b', 'whether'),
            (r'\bthe question as to whether\b', 'whether')
        ]
        
        for pattern, replacement in redundancies:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    async def _add_explanations(self, text: str, language: str) -> str:
        """Add simple explanations for technical terms"""
        
        # Define terms that need explanation
        technical_terms = {
            'en': {
                'deductible': ' (the amount you pay first)',
                'premium': ' (the money you pay)',
                'coverage': ' (what the insurance pays for)',
                'exclusions': ' (what the insurance does not pay for)',
                'waiting period': ' (time you must wait before benefits start)',
                'sum assured': ' (the amount of money promised)',
                'nominee': ' (person you choose to receive money)',
                'policy term': ' (how long the insurance lasts)',
                'renewal': ' (continuing the insurance for more time)',
                'claim': ' (asking the insurance company to pay)'
            },
            'hi': {
                'कटौती योग्य': ' (वह रकम जो आप पहले देते हैं)',
                'प्रीमियम': ' (वह पैसा जो आप देते हैं)',
                'कवरेज': ' (वह जो बीमा भुगतान करता है)',
                'अपवाद': ' (वह जो बीमा भुगतान नहीं करता)',
                'प्रतीक्षा अवधि': ' (वह समय जिसे आपको लाभ शुरू होने से पहले इंतजार करना होता है)',
                'बीमाकृत राशि': ' (वादा की गई रकम)',
                'नामांकित व्यक्ति': ' (वह व्यक्ति जिसे आप पैसे देना चुनते हैं)',
                'पॉलिसी अवधि': ' (बीमा कितने समय तक चलता है)',
                'नवीकरण': ' (बीमा को और समय के लिए जारी रखना)',
                'दावा': ' (बीमा कंपनी से भुगतान करने के लिए कहना)'
            },
            'mr': {
                'वजवटण्याजोगी रक्कम': ' (तुम्ही आधी द्यायची रक्कम)',
                'प्रीमियम': ' (तुम्ही द्यायचे पैसे)',
                'कव्हरेज': ' (विमा काय देतो)',
                'अपवाद': ' (विमा काय देत नाही)',
                'प्रतीक्षा कालावधी': ' (तुम्ही लाभ सुरू होण्यापूर्वी प्रतीक्षा करणारा कालावधी)',
                'बीमाकृत रक्कम': ' (वचनबद्ध केलेली रक्कम)',
                'नामनिर्देशित व्यक्ती': ' (तुम्ही निवडलेली व्यक्ती जिला पैसे मिळतात)',
                'पॉलिसी कालावधी': ' (विमा किती काळासाठी असतो)',
                'नूतनीकरण': ' (विमा अधिक काळासाठी सुरू ठेवणे)',
                'दावा': ' (विमा कंपनीकडे पैसे मागणे)'
            }
        }
        
        # Add explanations for technical terms
        terms = technical_terms.get(language, technical_terms['en'])
        
        for term, explanation in terms.items():
            # Only add explanation if term appears in text
            if re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE):
                # Add explanation after the first occurrence
                pattern = r'(' + re.escape(term) + r')(?![^(]*\\))'
                text = re.sub(pattern, r'\1' + explanation, text, count=1, flags=re.IGNORECASE)
        
        return text
    
    async def _format_for_readability(self, text: str) -> str:
        """Format text for better readability"""
        
        # Add proper spacing after punctuation
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
        
        # Ensure proper capitalization at sentence start
        sentences = self._split_into_sentences(text)
        formatted_sentences = []
        
        for sentence in sentences:
            if sentence:
                # Capitalize first letter
                sentence = sentence[0].upper() + sentence[1:].lower()
                formatted_sentences.append(sentence)
        
        return ' '.join(formatted_sentences)
    
    async def calculate_improvement(self, original: str, simplified: str) -> Dict:
        """Calculate readability improvement metrics"""
        
        original_words = original.split()
        simplified_words = simplified.split()
        
        original_sentences = self._split_into_sentences(original)
        simplified_sentences = self._split_into_sentences(simplified)
        
        return {
            'original_word_count': len(original_words),
            'simplified_word_count': len(simplified_words),
            'word_reduction': len(original_words) - len(simplified_words),
            'original_sentence_count': len(original_sentences),
            'simplified_sentence_count': len(simplified_sentences),
            'avg_words_per_sentence_original': len(original_words) / max(len(original_sentences), 1),
            'avg_words_per_sentence_simplified': len(simplified_words) / max(len(simplified_sentences), 1)
        }
    
    def get_readability_grade(self, text: str) -> int:
        """Estimate the reading grade level of text"""
        
        words = text.split()
        sentences = self._split_into_sentences(text)
        
        if not words or not sentences:
            return 1
        
        # Simple heuristic based on average sentence length and word complexity
        avg_sentence_length = len(words) / len(sentences)
        
        # Count complex words (longer than 6 characters)
        complex_words = sum(1 for word in words if len(word) > 6)
        complex_word_ratio = complex_words / len(words)
        
        # Simple grade estimation
        grade = int(avg_sentence_length * 0.5 + complex_word_ratio * 10)
        
        return max(1, min(12, grade))  # Clamp between 1-12