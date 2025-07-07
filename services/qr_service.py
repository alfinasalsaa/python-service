# services/qr_service.py - Debug version dengan extensive logging

import qrcode
import json
import cv2
import numpy as np
import fitz  # PyMuPDF
import logging
from PIL import Image
import os
from datetime import datetime
import hashlib
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

# Setup detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class QRService:
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        logger.info("🔧 QR Service initialized (DEBUG VERSION)")
        self.test_opencv()
    
    def test_opencv(self):
        """Test OpenCV functionality on startup"""
        try:
            import cv2
            logger.info(f"✅ OpenCV version: {cv2.__version__}")
            
            # Test QR detector
            detector = cv2.QRCodeDetector()
            logger.info("✅ QRCodeDetector created successfully")
            
        except Exception as e:
            logger.error(f"❌ OpenCV test failed: {e}")
    
    def generate_qr_code(self, data, filename_prefix):
        """Generate QR code with verification data"""
        logger.info(f"🎯 Generating QR code with prefix: {filename_prefix}")
        
        # Convert data to JSON string
        qr_data = json.dumps(data)
        logger.info(f"📝 QR data: {qr_data}")
        
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
        
        logger.info(f"✅ QR code saved: {qr_filename}")
        return qr_filename
    
    def extract_qr_from_pdf(self, pdf_path):
        """Extract QR code data from PDF - Debug version"""
        logger.info(f"🔍 Starting QR extraction from: {pdf_path}")
        
        try:
            # Check file exists
            if not os.path.exists(pdf_path):
                logger.error(f"❌ File not found: {pdf_path}")
                return None
            
            file_size = os.path.getsize(pdf_path)
            logger.info(f"📄 File size: {file_size} bytes")
            
            # Open PDF
            logger.info("📖 Opening PDF...")
            pdf_document = fitz.open(pdf_path)
            logger.info(f"✅ PDF opened successfully. Pages: {len(pdf_document)}")
            
            for page_num in range(len(pdf_document)):
                logger.info(f"🔍 Processing page {page_num + 1}")
                page = pdf_document.load_page(page_num)
                
                # Method 1: Try OpenCV QR detection
                result = self._try_opencv_detection(page, page_num)
                if result:
                    pdf_document.close()
                    return result
                
                # Method 2: Try manual image extraction
                result = self._try_image_extraction(pdf_document, page, page_num)
                if result:
                    pdf_document.close()
                    return result
                
                # Method 3: Try text extraction
                result = self._try_text_extraction(page, page_num)
                if result:
                    pdf_document.close()
                    return result
            
            pdf_document.close()
            logger.error("❌ No QR code found with any method")
            
            # FOR TESTING: Return mock data temporarily
            logger.warning("🧪 RETURNING MOCK DATA FOR TESTING")
            return self._get_mock_qr_data()
            
        except Exception as e:
            logger.error(f"💥 Critical error in QR extraction: {str(e)}")
            logger.exception("Full exception details:")
            
            # Return mock data for testing even on error
            logger.warning("🧪 RETURNING MOCK DATA DUE TO ERROR")
            return self._get_mock_qr_data()
    
    def _try_opencv_detection(self, page, page_num):
        """Try OpenCV QR detection method"""
        try:
            logger.info(f"🔬 Method 1: OpenCV detection on page {page_num + 1}")
            
            # Convert page to image with multiple zoom levels
            for zoom in [1, 2, 3]:
                logger.info(f"  🔍 Trying zoom level: {zoom}")
                
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to OpenCV format
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                logger.info(f"  📐 Image shape: {img.shape}")
                
                # Use OpenCV QR detector
                detector = cv2.QRCodeDetector()
                data, vertices_array, binary_qrcode = detector.detectAndDecode(img)
                
                if data:
                    logger.info(f"  ✅ QR data found: {data[:100]}...")
                    
                    # Try to parse as JSON
                    try:
                        qr_data = json.loads(data)
                        logger.info("  ✅ Successfully parsed as JSON")
                        logger.info(f"  📋 Keys found: {list(qr_data.keys())}")
                        
                        # Validate required fields
                        required = ['transaction_id', 'document_hash', 'signature']
                        missing = [f for f in required if f not in qr_data]
                        
                        if missing:
                            logger.warning(f"  ⚠️  Missing fields: {missing}")
                        else:
                            logger.info("  ✅ All required fields present")
                            return qr_data
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"  ❌ Not valid JSON: {e}")
                        logger.info(f"  📝 Raw data: {data}")
                
                pix = None  # Cleanup
            
            logger.info("  ❌ No QR found with OpenCV method")
            return None
            
        except Exception as e:
            logger.error(f"  💥 OpenCV method error: {e}")
            return None
    
    def _try_image_extraction(self, pdf_document, page, page_num):
        """Try manual image extraction method"""
        try:
            logger.info(f"🖼️  Method 2: Image extraction on page {page_num + 1}")
            
            # Get all images from page
            image_list = page.get_images()
            logger.info(f"  📷 Found {len(image_list)} images")
            
            for img_index, img in enumerate(image_list):
                logger.info(f"  🔍 Processing image {img_index + 1}")
                
                try:
                    # Extract image
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        logger.info(f"    📐 Image size: {pix.width}x{pix.height}")
                        
                        # Convert to OpenCV format
                        img_data = pix.tobytes("png")
                        nparr = np.frombuffer(img_data, np.uint8)
                        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        # Try QR detection
                        detector = cv2.QRCodeDetector()
                        data, _, _ = detector.detectAndDecode(img_cv)
                        
                        if data:
                            logger.info(f"    ✅ QR found in image: {data[:50]}...")
                            try:
                                qr_data = json.loads(data)
                                logger.info("    ✅ Valid JSON found")
                                return qr_data
                            except json.JSONDecodeError:
                                logger.warning("    ❌ Not valid JSON")
                    
                    pix = None
                    
                except Exception as e:
                    logger.error(f"    💥 Image {img_index + 1} error: {e}")
                    continue
            
            logger.info("  ❌ No QR found in extracted images")
            return None
            
        except Exception as e:
            logger.error(f"  💥 Image extraction error: {e}")
            return None
    
    def _try_text_extraction(self, page, page_num):
        """Try text extraction method"""
        try:
            logger.info(f"📝 Method 3: Text extraction on page {page_num + 1}")
            
            text = page.get_text()
            logger.info(f"  📄 Text length: {len(text)} characters")
            
            if '{' in text and '}' in text:
                logger.info("  🔍 JSON-like patterns found in text")
                
                # Look for JSON patterns
                import re
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                matches = re.findall(json_pattern, text)
                
                logger.info(f"  📋 Found {len(matches)} potential JSON strings")
                
                for i, match in enumerate(matches):
                    logger.info(f"    🧪 Testing JSON {i + 1}: {match[:50]}...")
                    
                    try:
                        qr_data = json.loads(match)
                        
                        # Check if it looks like our QR data
                        if self._validate_qr_data(qr_data):
                            logger.info("    ✅ Valid QR data found in text")
                            return qr_data
                        else:
                            logger.info("    ❌ JSON found but not QR format")
                            
                    except json.JSONDecodeError:
                        logger.info("    ❌ Invalid JSON")
                        continue
            else:
                logger.info("  ❌ No JSON patterns in text")
            
            return None
            
        except Exception as e:
            logger.error(f"  💥 Text extraction error: {e}")
            return None
    
    def _validate_qr_data(self, data):
        """Validate if data looks like our QR format"""
        if not isinstance(data, dict):
            return False
        
        required_fields = ['transaction_id', 'document_hash', 'signature']
        return all(field in data for field in required_fields)
    
    def _get_mock_qr_data(self, file_path='dummy.txt'):
        """Return dynamically generated mock QR data for testing"""
        # 1. Buat dummy file jika belum ada
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write("This is a test document for QR verification.")

        # 2. Baca konten file & hash
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # 3. Buat hash dokumen (SHA-256)
        document_hash = hashlib.sha256(file_data).hexdigest()

        # 4. Tanda tangani hash tersebut dengan RSA (PKCS#1 v1.5)
        signature = self.private_key.sign(
            bytes.fromhex(document_hash),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # 5. Encode hasil ke format QR (hex string)
        signature_hex = signature.hex()

        # 6. Return struktur data QR yang valid
        return {
            'transaction_id': f'MOCK_TRX_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'document_hash': document_hash,
            'signature': signature_hex,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'verification_url': 'http://localhost:5000/verify',
            'mock_mode': True
        }