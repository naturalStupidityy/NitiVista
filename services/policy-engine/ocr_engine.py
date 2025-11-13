import logging
from typing import Dict, List, Optional
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io
import os

logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        # Configure Tesseract
        self.tesseract_config = '--oem 1 --psm 6'
        self.supported_languages = ['eng', 'mar', 'hin']
        
    async def extract_text(self, file_path: str) -> Dict:
        """Extract text from PDF or image file using OCR"""
        
        try:
            if file_path.lower().endswith('.pdf'):
                return await self._extract_from_pdf(file_path)
            else:
                return await self._extract_from_image(file_path)
                
        except Exception as e:
            logger.error(f"OCR extraction failed for {file_path}: {str(e)}")
            raise
    
    async def _extract_from_pdf(self, pdf_path: str) -> Dict:
        """Extract text from PDF file"""
        
        doc = fitz.open(pdf_path)
        full_text = ""
        pages_data = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Try to extract text directly first
            text = page.get_text()
            
            # If direct text extraction fails or confidence is low, use OCR
            if not text or len(text.strip()) < 100:
                # Convert page to image and use OCR
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                
                # Perform OCR on the image
                ocr_result = await self._perform_ocr(img_data)
                text = ocr_result["text"]
                confidence = ocr_result["confidence"]
            else:
                confidence = 0.95  # High confidence for direct text
            
            page_data = {
                "page_number": page_num + 1,
                "text": text,
                "confidence": confidence,
                "word_count": len(text.split())
            }
            
            pages_data.append(page_data)
            full_text += text + "\n\n"
        
        doc.close()
        
        # Calculate overall confidence
        overall_confidence = sum(p["confidence"] for p in pages_data) / len(pages_data)
        
        return {
            "text": full_text.strip(),
            "pages": len(pages_data),
            "confidence": overall_confidence,
            "pages_data": pages_data,
            "word_count": len(full_text.split()),
            "file_type": "pdf"
        }
    
    async def _extract_from_image(self, image_path: str) -> Dict:
        """Extract text from image file"""
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        ocr_result = await self._perform_ocr(image_data)
        
        return {
            "text": ocr_result["text"],
            "pages": 1,
            "confidence": ocr_result["confidence"],
            "pages_data": [{
                "page_number": 1,
                "text": ocr_result["text"],
                "confidence": ocr_result["confidence"],
                "word_count": len(ocr_result["text"].split())
            }],
            "word_count": len(ocr_result["text"].split()),
            "file_type": "image"
        }
    
    async def _perform_ocr(self, image_data: bytes) -> Dict:
        """Perform OCR on image data"""
        
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))
            
            # Preprocess image for better OCR results
            processed_image = self._preprocess_image(image)
            
            # Detect language and perform OCR
            detected_language = self._detect_language(processed_image)
            
            # Perform OCR with appropriate language
            if detected_language in self.supported_languages:
                text = pytesseract.image_to_string(
                    processed_image, 
                    lang=detected_language,
                    config=self.tesseract_config
                )
            else:
                # Default to English
                text = pytesseract.image_to_string(
                    processed_image,
                    lang='eng',
                    config=self.tesseract_config
                )
            
            # Calculate confidence score
            confidence = self._calculate_confidence(text, processed_image)
            
            return {
                "text": text.strip(),
                "confidence": confidence,
                "language": detected_language,
                "method": "tesseract_ocr"
            }
            
        except Exception as e:
            logger.error(f"OCR failed: {str(e)}")
            return {
                "text": "",
                "confidence": 0.0,
                "language": "unknown",
                "error": str(e)
            }
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results"""
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if image is too small
        width, height = image.size
        if width < 1000 or height < 1000:
            new_width = max(width * 2, 1000)
            new_height = max(height * 2, 1000)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Enhance contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.2)
        
        # Enhance sharpness
        sharpness_enhancer = ImageEnhance.Sharpness(image)
        image = sharpness_enhancer.enhance(1.1)
        
        return image
    
    def _detect_language(self, image: Image.Image) -> str:
        """Detect language of the text in image"""
        
        try:
            # Try OCR with different languages and see which gives better results
            results = {}
            
            for lang in self.supported_languages:
                try:
                    text = pytesseract.image_to_string(image, lang=lang, config='--psm 6')
                    confidence = len(text.strip())  # Simple confidence based on text length
                    results[lang] = confidence
                except:
                    results[lang] = 0
            
            # Return language with highest confidence
            if results:
                return max(results, key=results.get)
            else:
                return 'eng'  # Default to English
                
        except Exception:
            return 'eng'  # Default to English on error
    
    def _calculate_confidence(self, text: str, image: Image.Image) -> float:
        """Calculate confidence score for OCR result"""
        
        if not text.strip():
            return 0.0
        
        # Factors affecting confidence
        text_length = len(text)
        word_count = len(text.split())
        
        # Check for common OCR errors
        error_indicators = [
            '�',  # Unicode replacement character
            '@@',  # Common OCR artifact
            '**',  # Common OCR artifact
        ]
        
        error_count = sum(text.count(indicator) for indicator in error_indicators)
        
        # Calculate base confidence
        base_confidence = min(0.95, (word_count / 100) * 0.8)
        
        # Reduce confidence based on errors
        error_penalty = (error_count / max(text_length, 1)) * 0.3
        
        confidence = max(0.1, base_confidence - error_penalty)
        
        return round(confidence, 2)
    
    async def batch_process(self, file_paths: List[str]) -> List[Dict]:
        """Process multiple files in batch"""
        
        results = []
        for file_path in file_paths:
            try:
                result = await self.extract_text(file_path)
                results.append(result)
            except Exception as e:
                results.append({
                    "file_path": file_path,
                    "error": str(e),
                    "confidence": 0.0
                })
        
        return results
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return self.supported_languages.copy()
    
    def get_tesseract_info(self) -> Dict:
        """Get Tesseract version and configuration info"""
        
        try:
            version = pytesseract.get_tesseract_version()
            return {
                "version": str(version),
                "supported_languages": self.supported_languages,
                "config": self.tesseract_config,
                "status": "operational"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }