import os
import hashlib
import fitz  # PyMuPDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

class SignatureService:
    def __init__(self):
        self.private_key_path = 'keys/private_key.pem'
        self.public_key_path = 'keys/public_key.pem'
        
    def generate_keys(self):
        """Generate RSA key pair"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Save keys to files
        with open(self.private_key_path, 'wb') as f:
            f.write(private_pem)
            
        with open(self.public_key_path, 'wb') as f:
            f.write(public_pem)
            
        return self.private_key_path, self.public_key_path
    
    def load_private_key(self):
        """Load private key from file"""
        with open(self.private_key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        return private_key
    
    def _extract_document_content(self, file_path):
        """
        🔧 CORE FIX: Extract consistent document content for hashing
        This method ensures the same content is used for both signing and verification
        """
        try:
            doc = fitz.open(file_path)
            document_content = {
                'text_content': '',
                'metadata': {},
                'page_count': len(doc)
            }
            
            # Extract metadata
            document_content['metadata'] = doc.metadata
            
            # Extract text content from all pages
            all_text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                all_text += f"PAGE_{page_num}:{page_text}"
            
            document_content['text_content'] = all_text
            doc.close()
            
            # Create a deterministic string representation
            content_string = f"PAGES:{document_content['page_count']}"
            content_string += f"TITLE:{document_content['metadata'].get('title', '')}"
            content_string += f"AUTHOR:{document_content['metadata'].get('author', '')}"
            content_string += f"CONTENT:{document_content['text_content']}"
            
            # Normalize whitespace and encoding
            normalized_content = ' '.join(content_string.split())
            
            return normalized_content
            
        except Exception as e:
            print(f"❌ Error extracting document content: {str(e)}")
            # Fallback to simple text extraction
            return self._simple_text_extraction(file_path)
    
    def _simple_text_extraction(self, file_path):
        """Simple fallback text extraction"""
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return ' '.join(text.split())
        except:
            return f"FALLBACK_HASH_{os.path.basename(file_path)}"
    
    def generate_document_hash(self, file_path):
        """
        🔧 UPDATED: Generate hash from document content (for signing)
        Now uses content-based hashing instead of binary file hashing
        """
        try:
            # Extract document content consistently
            content = self._extract_document_content(file_path)
            
            # Generate hash from content
            sha256_hash = hashlib.sha256()
            sha256_hash.update(content.encode('utf-8'))
            
            hash_result = sha256_hash.hexdigest()
            print(f"📝 Document hash (signing): {hash_result[:16]}...")
            print(f"📄 Content preview: {content[:100]}...")
            
            return hash_result
            
        except Exception as e:
            print(f"❌ Error generating document hash: {str(e)}")
            # Fallback to binary hash (old method)
            return self._binary_file_hash(file_path)
    
    def generate_document_hash_for_verification(self, file_path):
        """
        🔧 FIXED: Generate hash for verification using the SAME method as signing
        This ensures consistency between signing and verification
        """
        try:
            # Use the exact same method as signing
            content = self._extract_document_content(file_path)
            
            # Generate hash from content
            sha256_hash = hashlib.sha256()
            sha256_hash.update(content.encode('utf-8'))
            
            hash_result = sha256_hash.hexdigest()
            print(f"🔍 Verification hash: {hash_result[:16]}...")
            print(f"📄 Content preview: {content[:100]}...")
            
            return hash_result
            
        except Exception as e:
            print(f"❌ Error generating verification hash: {str(e)}")
            # Use same fallback as signing method
            return self._binary_file_hash(file_path)
    
    def _binary_file_hash(self, file_path):
        """Original binary file hashing method (fallback)"""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def sign_document(self, document_hash):
        """Create digital signature for document hash"""
        private_key = self.load_private_key()
        
        # Convert hash to bytes
        hash_bytes = document_hash.encode('utf-8')
        
        # Create signature
        signature = private_key.sign(
            hash_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature