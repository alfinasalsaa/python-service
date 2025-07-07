import qrcode
import json
import cv2
import numpy as np
import fitz  # PyMuPDF

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
        """Extract QR code data from PDF using OpenCV"""
        try:
            # Open PDF
            pdf_document = fitz.open(pdf_path)
            
            # Initialize OpenCV QR detector
            qr_detector = cv2.QRCodeDetector()
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Convert page to image with higher resolution
                mat = fitz.Matrix(3, 3)  # Increased zoom for better QR detection
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to OpenCV format
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Convert to grayscale for better QR detection
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Detect and decode QR code
                data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(gray)
                
                if data:
                    try:
                        qr_data = json.loads(data)
                        pdf_document.close()
                        return qr_data
                    except json.JSONDecodeError:
                        # If not JSON, return raw data
                        pdf_document.close()
                        return {"raw_data": data}
                
                # Try with original color image if grayscale fails
                data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(img)
                
                if data:
                    try:
                        qr_data = json.loads(data)
                        pdf_document.close()
                        return qr_data
                    except json.JSONDecodeError:
                        pdf_document.close()
                        return {"raw_data": data}
            
            pdf_document.close()
            return None
            
        except Exception as e:
            print(f"Error extracting QR code: {str(e)}")
            return None
    
    def extract_qr_from_image(self, image_path):
        """Extract QR code data from image file"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                print(f"Could not read image: {image_path}")
                return None
            
            # Initialize OpenCV QR detector
            qr_detector = cv2.QRCodeDetector()
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect and decode QR code
            data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(gray)
            
            if data:
                try:
                    qr_data = json.loads(data)
                    return qr_data
                except json.JSONDecodeError:
                    return {"raw_data": data}
            
            # Try with original color image if grayscale fails
            data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(img)
            
            if data:
                try:
                    qr_data = json.loads(data)
                    return qr_data
                except json.JSONDecodeError:
                    return {"raw_data": data}
            
            return None
            
        except Exception as e:
            print(f"Error extracting QR code from image: {str(e)}")
            return None