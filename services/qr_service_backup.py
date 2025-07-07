# services/qr_service_alternative.py - QR Service tanpa pyzbar

import qrcode
import json
import cv2
import numpy as np
import fitz  # PyMuPDF
import logging
from PIL import Image
import base64
import io

logger = logging.getLogger(__name__)

class QRService:
    def generate_qr_code(self, data, filename_prefix):
        """Generate QR code with verification data"""
        # Convert data to JSON string
        qr_data = json.dumps(data)
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_filename = f"{filename_prefix}_qr.png"
        qr_image.save(qr_filename)
        
        return qr_filename
    
    def extract_qr_from_pdf(self, pdf_path):
        """Extract QR code data from PDF - Alternative method tanpa pyzbar"""
        try:
            logger.info(f"Starting QR extraction from: {pdf_path}")
            
            # Method 1: Try dengan OpenCV QR detector
            result = self._extract_with_opencv(pdf_path)
            if result:
                return result
            
            # Method 2: Try manual pattern detection
            result = self._extract_with_pattern_detection(pdf_path)
            if result:
                return result
            
            # Method 3: Extract semua teks dan cari JSON pattern
            result = self._extract_text_based_qr(pdf_path)
            if result:
                return result
            
            logger.error("No QR code found with any method")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting QR code: {str(e)}")
            return None
    
    def _extract_with_opencv(self, pdf_path):
        """Method 1: OpenCV QRCodeDetector"""
        try:
            # Open PDF dan convert ke image
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Convert to high resolution image
                mat = fitz.Matrix(3, 3)  # 3x zoom
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to OpenCV format
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Use OpenCV QR Code detector
                detector = cv2.QRCodeDetector()
                
                # Detect and decode
                data, vertices_array, binary_qrcode = detector.detectAndDecode(img)
                
                if data:
                    logger.info(f"QR Code detected with OpenCV: {data[:100]}...")
                    
                    try:
                        qr_data = json.loads(data)
                        logger.info("Successfully parsed QR data as JSON")
                        pdf_document.close()
                        return qr_data
                    except json.JSONDecodeError:
                        logger.warning("QR data is not valid JSON")
                        continue
            
            pdf_document.close()
            return None
            
        except Exception as e:
            logger.error(f"OpenCV method failed: {str(e)}")
            return None
    
    def _extract_with_pattern_detection(self, pdf_path):
        """Method 2: Manual QR pattern detection"""
        try:
            # This is a simplified version - detect QR-like patterns
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Get page images
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    # Extract image
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        # Convert to PNG bytes
                        img_data = pix.tobytes("png")
                        
                        # Check if this might be a QR code (square-ish, right size)
                        if self._looks_like_qr_code(pix):
                            # Try to decode with OpenCV
                            nparr = np.frombuffer(img_data, np.uint8)
                            img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            
                            detector = cv2.QRCodeDetector()
                            data, _, _ = detector.detectAndDecode(img_cv)
                            
                            if data:
                                try:
                                    qr_data = json.loads(data)
                                    pdf_document.close()
                                    return qr_data
                                except json.JSONDecodeError:
                                    continue
                    
                    pix = None
            
            pdf_document.close()
            return None
            
        except Exception as e:
            logger.error(f"Pattern detection method failed: {str(e)}")
            return None
    
    def _extract_text_based_qr(self, pdf_path):
        """Method 3: Extract text dan cari JSON pattern"""
        try:
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text = page.get_text()
                
                # Look for JSON-like patterns in text
                # Sometimes QR data might be embedded as text
                if '{' in text and '}' in text:
                    # Try to extract JSON-like strings
                    potential_jsons = self._extract_json_from_text(text)
                    
                    for json_str in potential_jsons:
                        try:
                            qr_data = json.loads(json_str)
                            
                            # Check if it has QR-like fields
                            if self._validate_qr_data(qr_data):
                                pdf_document.close()
                                return qr_data
                                
                        except json.JSONDecodeError:
                            continue
            
            pdf_document.close()
            return None
            
        except Exception as e:
            logger.error(f"Text-based method failed: {str(e)}")
            return None
    
    def _looks_like_qr_code(self, pix):
        """Check if image looks like a QR code"""
        # Simple heuristics
        width, height = pix.width, pix.height
        
        # QR codes are roughly square
        aspect_ratio = width / height if height > 0 else 0
        
        # Size should be reasonable (not too small, not too big)
        size_ok = 50 < width < 1000 and 50 < height < 1000
        
        # Aspect ratio should be close to 1:1
        square_ish = 0.8 < aspect_ratio < 1.2
        
        return size_ok and square_ish
    
    def _extract_json_from_text(self, text):
        """Extract potential JSON strings from text"""
        import re
        
        # Find all potential JSON objects
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text)
        
        return matches
    
    def _validate_qr_data(self, data):
        """Validate if data looks like our QR format"""
        if not isinstance(data, dict):
            return False
        
        required_fields = ['transaction_id', 'document_hash', 'signature']
        return all(field in data for field in required_fields)

# ===================================================================
# Fallback service jika semua method gagal

class QRServiceFallback:
    """Simplified QR service untuk testing tanpa QR reading"""
    
    def generate_qr_code(self, data, filename_prefix):
        """Generate QR code with verification data"""
        qr_data = json.dumps(data)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        qr_filename = f"{filename_prefix}_qr.png"
        qr_image.save(qr_filename)
        
        return qr_filename
    
    def extract_qr_from_pdf(self, pdf_path):
        """Mock QR extraction - returns sample data untuk testing"""
        logger.warning("Using fallback QR service - returning mock data")
        
        # Return mock data untuk testing
        mock_data = {
            'transaction_id': 'MOCK_TRX_001',
            'document_hash': 'mock_hash_123456789',
            'signature': 'mock_signature_abcdef',
            'timestamp': '2025-07-07 12:00:00',
            'verification_url': 'http://localhost:5000/verify'
        }
        
        return mock_data