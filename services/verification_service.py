from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

class VerificationService:
    def __init__(self):
        self.public_key_path = 'keys/public_key.pem'
    
    def load_public_key(self):
        """Load public key from file"""
        with open(self.public_key_path, 'rb') as f:
            public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        return public_key
    
    def verify_signature(self, document_hash, signature):
        """Verify digital signature"""
        try:
            public_key = self.load_public_key()
            
            # Convert hash to bytes
            hash_bytes = document_hash.encode('utf-8')
            
            # Verify signature
            public_key.verify(
                signature,
                hash_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False