from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import logging
from services.signature_service import SignatureService
from services.verification_service import VerificationService
from services.qr_service import QRService
from services.pdf_service import PDFService
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SIGNED_FOLDER'] = 'signed'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SIGNED_FOLDER'], exist_ok=True)
os.makedirs('keys', exist_ok=True)

# Initialize services
signature_service = SignatureService()
verification_service = VerificationService()
qr_service = QRService()
pdf_service = PDFService()

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'service': 'Digital Signature Service',
        'version': '1.0.0'
    })

@app.route('/generate-keys', methods=['POST'])
def generate_keys():
    """Generate new RSA key pair"""
    try:
        private_key_path, public_key_path = signature_service.generate_keys()
        return jsonify({
            'success': True,
            'message': 'Keys generated successfully',
            'private_key_path': private_key_path,
            'public_key_path': public_key_path
        })
    except Exception as e:
        logger.error(f"Error generating keys: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sign-document', methods=['POST'])
def sign_document():
    """Sign a PDF document and add QR code"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({
                'success': False,
                'error': 'Only PDF files are allowed'
            }), 400

        # Get additional data from request
        transaction_id = request.form.get('transaction_id', '')
        customer_name = request.form.get('customer_name', '')
        transaction_date = request.form.get('transaction_date', '')

        # Save uploaded file
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Generate document hash
        document_hash = signature_service.generate_document_hash(file_path)
        
        # Create digital signature
        signature = signature_service.sign_document(document_hash)
        
        # Generate QR code with verification data
        qr_data = {
            'transaction_id': transaction_id,
            'document_hash': document_hash,
            'signature': signature.hex(),
            'timestamp': transaction_date,
            'verification_url': f"http://localhost:5000/verify"
        }
        
        qr_image_path = qr_service.generate_qr_code(qr_data, f"qr_{transaction_id}")
        
        # Add QR code to PDF
        signed_filename = f"signed_{filename}"
        signed_file_path = os.path.join(app.config['SIGNED_FOLDER'], signed_filename)
        
        pdf_service.add_qr_to_pdf(file_path, qr_image_path, signed_file_path)
        
        # Clean up temporary files
        os.remove(file_path)
        os.remove(qr_image_path)
        
        return jsonify({
            'success': True,
            'message': 'Document signed successfully',
            'signed_file_path': signed_file_path,
            'document_hash': document_hash,
            'signature': signature.hex(),
            'download_url': f"/download/{signed_filename}"
        })
        
    except Exception as e:
        logger.error(f"Error signing document: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/verify-document', methods=['POST'])
def verify_document():
    """Verify a signed PDF document - PROPERLY FIXED VERSION"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Save uploaded file temporarily
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"verify_{filename}")
        file.save(file_path)

        logger.info(f"🔍 Starting verification of: {filename}")

        # Step 1: Extract QR code from PDF
        logger.info("📱 Step 1: Extracting QR code...")
        qr_data = qr_service.extract_qr_from_pdf(file_path)
        
        if not qr_data:
            return jsonify({
                'success': False,
                'error': 'No QR code found in document or QR code is corrupted'
            }), 400

        # Step 2: Get original hash and signature from QR data
        logger.info("📋 Step 2: Parsing QR data...")
        original_hash = qr_data.get('document_hash')
        signature_hex = qr_data.get('signature')


        if not original_hash or not signature_hex:
            return jsonify({
                'success': False,
                'error': 'Invalid QR code data - missing hash or signature'
            }), 400

        logger.info(f"📜 Original hash: {original_hash[:16]}...")
        logger.info(f"✍️  Signature: {signature_hex[:16]}...")

        # Step 3: Generate current document hash (WITHOUT QR code area)
        logger.info("🔐 Step 3: Generating current document hash...")
        current_hash = signature_service.generate_document_hash_for_verification(file_path)
        # current_qr_data = qr_service.extract_qr_from_pdf(file_path)
        # current_hash = current_qr_data.get('document_hash')

        logger.info(f"📄 Current hash: {current_hash[:16]}...")

        # Step 4: Check document integrity
        logger.info("🔍 Step 4: Checking document integrity...")
        document_integrity = current_hash == original_hash
        logger.info(f"📊 Document integrity: {'✅ VALID' if document_integrity else '❌ TAMPERED'}")

        # Step 5: Verify digital signature
        logger.info("🔐 Step 5: Verifying digital signature...")
        signature = bytes.fromhex(signature_hex)
        signature_valid = verification_service.verify_signature(original_hash, signature)
        logger.info(f"✍️  Signature validity: {'✅ VALID' if signature_valid else '❌ INVALID'}")

        # Step 6: Determine overall validity
        overall_valid = document_integrity and signature_valid
        logger.info(f"🎯 Overall result: {'✅ AUTHENTIC' if overall_valid else '❌ NOT AUTHENTIC'}")

        # Clean up temporary file
        os.remove(file_path)
        
        # Determine verification message
        if overall_valid:
            message = 'Document is authentic and unmodified'
        elif not document_integrity and not signature_valid:
            message = 'Document has been modified AND signature is invalid'
        elif not document_integrity:
            message = 'Document has been modified after signing'
        elif not signature_valid:
            message = 'Digital signature is invalid'
        else:
            message = 'Verification failed'

        verification_result = {
            'document_integrity': document_integrity,
            'signature_valid': signature_valid,
            'overall_valid': overall_valid,  # Both must be true
            'transaction_id': qr_data.get('transaction_id'),
            'timestamp': qr_data.get('timestamp'),
            'original_hash': original_hash,
            'current_hash': current_hash,
            'message': message,
            'security_details': {
                'hash_algorithm': 'SHA-256',
                'signature_algorithm': 'RSA-2048',
                'verification_timestamp': str(datetime.now()),
                'tamper_detected': not document_integrity,
                'signature_verified': signature_valid
            }
        }
        
        return jsonify({
            'success': True,
            'verification': verification_result
        })
        
    except Exception as e:
        logger.error(f"💥 Error verifying document: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================================
# 🆕 TAMBAHKAN ENDPOINT VERIFIKASI BARU DI SINI (SETELAH /verify-document)
# ========================================================================================

@app.route('/verify-signature-only', methods=['POST'])
def verify_signature_only():
    """Verify signature without document upload (untuk QR code verification)"""
    try:
        data = request.get_json()
        document_hash = data.get('document_hash')
        signature_hex = data.get('signature')
        
        if not document_hash or not signature_hex:
            return jsonify({
                'success': False,
                'error': 'Missing document_hash or signature'
            }), 400
        
        # Convert signature back to bytes
        signature = bytes.fromhex(signature_hex)
        
        # Verify signature
        signature_valid = verification_service.verify_signature(document_hash, signature)
        
        return jsonify({
            'success': True,
            'signature_valid': signature_valid,
            'document_hash': document_hash,
        })
        
    except Exception as e:
        logger.error(f"Error verifying signature only: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/extract-qr', methods=['POST'])
def extract_qr_data():
    """Extract QR code data from PDF (untuk Laravel integration)"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Save uploaded file temporarily
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"extract_{filename}")
        file.save(file_path)

        # Extract QR code data
        qr_data = qr_service.extract_qr_from_pdf(file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        if qr_data:
            return jsonify({
                'success': True,
                'qr_data': qr_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No QR code found in document'
            })
        
    except Exception as e:
        logger.error(f"Error extracting QR data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/verify-qr-data', methods=['POST'])
def verify_qr_data():
    """Verify QR code data without uploading file"""
    try:
        data = request.get_json()
        qr_data_str = data.get('qr_data')
        
        if not qr_data_str:
            return jsonify({
                'success': False,
                'error': 'No QR data provided'
            }), 400
        
        # Parse QR data (should be JSON string)
        import json
        try:
            qr_data = json.loads(qr_data_str)
        except json.JSONDecodeError:
            return jsonify({
                'success': False,
                'error': 'Invalid QR code data format'
            }), 400
        
        # Get signature and hash from QR data
        document_hash = qr_data.get('document_hash')
        signature_hex = qr_data.get('signature')
        
        if not document_hash or not signature_hex:
            return jsonify({
                'success': False,
                'error': 'Invalid QR code data - missing hash or signature'
            }), 400
        
        # Convert signature back to bytes
        signature = bytes.fromhex(signature_hex)
        
        # Verify signature
        signature_valid = verification_service.verify_signature(document_hash, signature)
        
        verification_result = {
            'signature_valid': signature_valid,
            'qr_valid': True,  # QR was readable and parseable
            'overall_valid': signature_valid,
            'transaction_id': qr_data.get('transaction_id'),
            'timestamp': qr_data.get('timestamp'),
            'document_hash': document_hash,
        }
        
        if signature_valid:
            verification_result['message'] = 'QR code and signature are valid'
        else:
            verification_result['message'] = 'QR code is readable but signature is invalid'
        
        return jsonify({
            'success': True,
            'verification': verification_result
        })
        
    except Exception as e:
        logger.error(f"Error verifying QR data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========================================================================================
# ENDPOINT YANG SUDAH ADA SEBELUMNYA (JANGAN DIUBAH)
# ========================================================================================

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download signed document"""
    try:
        file_path = os.path.join(app.config['SIGNED_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
            
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/verify', methods=['GET'])
def verify_page():
    """Simple verification page for QR code links"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Document Verification</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            .upload-area { 
                border: 2px dashed #ccc; 
                border-radius: 10px; 
                padding: 40px; 
                text-align: center; 
                margin: 20px 0;
            }
            .btn { 
                background: #007bff; 
                color: white; 
                padding: 10px 20px; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer;
            }
            .result { 
                margin: 20px 0; 
                padding: 15px; 
                border-radius: 5px;
            }
            .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Verifikasi Dokumen Digital</h1>
            <p>Upload dokumen PDF untuk memverifikasi keaslian dan integritas dokumen.</p>
            
            <div class="upload-area">
                <input type="file" id="fileInput" accept=".pdf" style="display: none;">
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    Pilih File PDF
                </button>
                <p>Atau drag & drop file PDF disini</p>
            </div>
            
            <div id="result"></div>
        </div>
        
        <script>
            document.getElementById('fileInput').addEventListener('change', verifyDocument);
            
            function verifyDocument() {
                const fileInput = document.getElementById('fileInput');
                const resultDiv = document.getElementById('result');
                
                if (!fileInput.files[0]) return;
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                resultDiv.innerHTML = '<p>Memverifikasi dokumen...</p>';
                
                fetch('/verify-document', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const verification = data.verification;
                        const className = verification.overall_valid ? 'success' : 'error';
                        resultDiv.className = 'result ' + className;
                        resultDiv.innerHTML = `
                            <h3>Hasil Verifikasi</h3>
                            <p><strong>Status:</strong> ${verification.message}</p>
                            <p><strong>ID Transaksi:</strong> ${verification.transaction_id}</p>
                            <p><strong>Tanggal:</strong> ${verification.timestamp}</p>
                            <p><strong>Integritas Dokumen:</strong> ${verification.document_integrity ? 'Valid' : 'Tidak Valid'}</p>
                            <p><strong>Tanda Tangan Digital:</strong> ${verification.signature_valid ? 'Valid' : 'Tidak Valid'}</p>
                        `;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<p>Error: ${data.error}</p>`;
                    }
                })
                .catch(error => {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
                });
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    # Generate keys if they don't exist
    if not os.path.exists('keys/private_key.pem') or not os.path.exists('keys/public_key.pem'):
        logger.info("Generating RSA key pair...")
        signature_service.generate_keys()
        logger.info("Keys generated successfully")
    
    app.run(debug=True, host='0.0.0.0', port=5000)