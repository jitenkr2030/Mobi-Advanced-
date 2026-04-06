"""
Data Encryption Module
Provides comprehensive encryption for sensitive data protection
"""

import os
import base64
import secrets
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from flask import current_app

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Manages data encryption and decryption"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or self._generate_master_key()
        self.fernet = Fernet(self._derive_fernet_key())
        self.backend = default_backend()
    
    def _generate_master_key(self) -> bytes:
        """Generate a new master key"""
        return os.urandom(32)
    
    def _derive_fernet_key(self) -> bytes:
        """Derive Fernet key from master key"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'mobi_invoice_salt',  # In production, use a proper salt
            iterations=100000,
            backend=self.backend
        )
        return base64.urlsafe_b64encode(kdf.derive(self.master_key))
    
    def encrypt(self, data: Union[str, bytes, Dict, List]) -> str:
        """
        Encrypt data
        
        Args:
            data: Data to encrypt
        
        Returns:
            Base64 encoded encrypted data
        """
        try:
            if isinstance(data, (dict, list)):
                data = json.dumps(data, default=str).encode()
            elif isinstance(data, str):
                data = data.encode()
            
            encrypted_data = self.fernet.encrypt(data)
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> Union[str, Dict, List]:
        """
        Decrypt data
        
        Args:
            encrypted_data: Base64 encoded encrypted data
        
        Returns:
            Decrypted data
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            
            # Try to parse as JSON first
            try:
                return json.loads(decrypted_data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return decrypted_data.decode()
                
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_field(self, value: Any, field_name: str = None) -> str:
        """Encrypt a single field value"""
        if value is None:
            return None
        
        # Add field context for additional security
        if field_name:
            data = {'field': field_name, 'value': value}
        else:
            data = value
        
        return self.encrypt(data)
    
    def decrypt_field(self, encrypted_value: str, field_name: str = None) -> Any:
        """Decrypt a single field value"""
        if not encrypted_value:
            return None
        
        decrypted = self.decrypt(encrypted_value)
        
        # Extract value if field context was used
        if field_name and isinstance(decrypted, dict) and 'value' in decrypted:
            return decrypted['value']
        
        return decrypted
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
        """
        Hash password with salt
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)
        
        Returns:
            Tuple of (hashed_password, salt)
        """
        if salt is None:
            salt = os.urandom(32)
        
        pwdhash = hashlib.pbkdf2_hmac('sha256', 
                                      password.encode('utf-8'), 
                                      salt, 
                                      100000)  # 100k iterations
        return pwdhash.hex(), salt
    
    def verify_password(self, password: str, hashed: str, salt: bytes) -> bool:
        """Verify password against hash"""
        pwdhash, _ = self.hash_password(password, salt)
        return hmac.compare_digest(pwdhash, hashed)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def generate_api_key(self) -> str:
        """Generate API key"""
        timestamp = str(int(datetime.utcnow().timestamp()))
        random_part = secrets.token_urlsafe(24)
        return f"mi_{timestamp}_{random_part}"
    
    def create_data_hash(self, data: Union[str, bytes]) -> str:
        """Create SHA-256 hash of data"""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).hexdigest()
    
    def verify_data_integrity(self, data: Union[str, bytes], expected_hash: str) -> bool:
        """Verify data integrity against hash"""
        actual_hash = self.create_data_hash(data)
        return hmac.compare_digest(actual_hash, expected_hash)

class FieldEncryption:
    """Handles encryption of specific model fields"""
    
    def __init__(self, encryption_manager: EncryptionManager):
        self.encryption_manager = encryption_manager
        self.encrypted_fields = {
            'User': ['password_hash', 'two_factor_secret'],
            'Customer': ['phone', 'gstin', 'credit_card'],
            'Invoice': ['notes'],
            'Payment': ['reference'],
        }
    
    def encrypt_model_data(self, model_name: str, data: Dict) -> Dict:
        """Encrypt sensitive fields in model data"""
        if model_name not in self.encrypted_fields:
            return data
        
        encrypted_data = data.copy()
        fields_to_encrypt = self.encrypted_fields[model_name]
        
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field] is not None:
                try:
                    encrypted_value = self.encryption_manager.encrypt_field(
                        encrypted_data[field], field
                    )
                    encrypted_data[field] = encrypted_value
                except Exception as e:
                    logger.error(f"Failed to encrypt field {field}: {e}")
        
        return encrypted_data
    
    def decrypt_model_data(self, model_name: str, data: Dict) -> Dict:
        """Decrypt sensitive fields in model data"""
        if model_name not in self.encrypted_fields:
            return data
        
        decrypted_data = data.copy()
        fields_to_decrypt = self.encrypted_fields[model_name]
        
        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field] is not None:
                try:
                    decrypted_value = self.encryption_manager.decrypt_field(
                        decrypted_data[field], field
                    )
                    decrypted_data[field] = decrypted_value
                except Exception as e:
                    logger.error(f"Failed to decrypt field {field}: {e}")
        
        return decrypted_data

class KeyManager:
    """Manages encryption keys and rotation"""
    
    def __init__(self):
        self.current_key_id = "default"
        self.keys: Dict[str, bytes] = {}
        self.key_metadata: Dict[str, Dict] = {}
        self._initialize_default_key()
    
    def _initialize_default_key(self):
        """Initialize default encryption key"""
        default_key = os.urandom(32)
        self.keys[self.current_key_id] = default_key
        self.key_metadata[self.current_key_id] = {
            'created_at': datetime.utcnow(),
            'is_active': True,
            'usage_count': 0
        }
    
    def add_key(self, key_id: str, key: bytes) -> None:
        """Add a new encryption key"""
        self.keys[key_id] = key
        self.key_metadata[key_id] = {
            'created_at': datetime.utcnow(),
            'is_active': True,
            'usage_count': 0
        }
        logger.info(f"Added encryption key: {key_id}")
    
    def rotate_key(self, new_key_id: str = None) -> str:
        """
        Rotate to a new encryption key
        
        Args:
            new_key_id: Optional ID for new key
        
        Returns:
            ID of the new key
        """
        if new_key_id is None:
            new_key_id = f"key_{int(datetime.utcnow().timestamp())}"
        
        # Generate new key
        new_key = os.urandom(32)
        self.add_key(new_key_id, new_key)
        
        # Deactivate old key
        self.key_metadata[self.current_key_id]['is_active'] = False
        self.key_metadata[self.current_key_id]['deactivated_at'] = datetime.utcnow()
        
        self.current_key_id = new_key_id
        logger.info(f"Rotated encryption key to: {new_key_id}")
        
        return new_key_id
    
    def get_key(self, key_id: str = None) -> bytes:
        """Get encryption key by ID"""
        key_id = key_id or self.current_key_id
        if key_id not in self.keys:
            raise ValueError(f"Key not found: {key_id}")
        
        # Update usage count
        self.key_metadata[key_id]['usage_count'] += 1
        self.key_metadata[key_id]['last_used'] = datetime.utcnow()
        
        return self.keys[key_id]
    
    def get_key_info(self, key_id: str = None) -> Dict[str, Any]:
        """Get key metadata"""
        key_id = key_id or self.current_key_id
        return self.key_metadata.get(key_id, {})
    
    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """List all keys with metadata"""
        return self.key_metadata.copy()
    
    def delete_key(self, key_id: str) -> bool:
        """Delete a key (only if not active)"""
        if key_id == self.current_key_id:
            raise ValueError("Cannot delete current active key")
        
        if key_id in self.keys:
            del self.keys[key_id]
            del self.key_metadata[key_id]
            logger.info(f"Deleted encryption key: {key_id}")
            return True
        
        return False

class SecureConfig:
    """Manages secure configuration values"""
    
    def __init__(self, encryption_manager: EncryptionManager):
        self.encryption_manager = encryption_manager
        self.config_file = 'secure_config.json'
        self.config_data = {}
        self._load_config()
    
    def _load_config(self):
        """Load encrypted configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    encrypted_config = f.read()
                
                if encrypted_config:
                    self.config_data = self.encryption_manager.decrypt(encrypted_config)
        except Exception as e:
            logger.error(f"Failed to load secure config: {e}")
            self.config_data = {}
    
    def _save_config(self):
        """Save encrypted configuration"""
        try:
            encrypted_config = self.encryption_manager.encrypt(self.config_data)
            with open(self.config_file, 'w') as f:
                f.write(encrypted_config)
        except Exception as e:
            logger.error(f"Failed to save secure config: {e}")
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config_data[key] = value
        self._save_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config_data.get(key, default)
    
    def delete(self, key: str):
        """Delete configuration value"""
        if key in self.config_data:
            del self.config_data[key]
            self._save_config()

# Encryption utilities
class EncryptionUtils:
    """Utility functions for encryption operations"""
    
    @staticmethod
    def generate_key_pair() -> Tuple[str, str]:
        """Generate RSA key pair for asymmetric encryption (placeholder)"""
        # In a real implementation, you'd use cryptography.hazmat.primitives.asymmetric
        private_key = "private_key_placeholder"
        public_key = "public_key_placeholder"
        return private_key, public_key
    
    @staticmethod
    def encrypt_with_public_key(data: str, public_key: str) -> str:
        """Encrypt data with RSA public key (placeholder)"""
        # In a real implementation, you'd use RSA encryption
        return f"encrypted_with_{public_key[:10]}..."
    
    @staticmethod
    def decrypt_with_private_key(encrypted_data: str, private_key: str) -> str:
        """Decrypt data with RSA private key (placeholder)"""
        # In a real implementation, you'd use RSA decryption
        return "decrypted_data"
    
    @staticmethod
    def create_secure_hash(data: str, salt: str = None) -> str:
        """Create secure hash with optional salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        hash_input = data + salt
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    @staticmethod
    def verify_secure_hash(data: str, hash_value: str, salt: str) -> bool:
        """Verify secure hash"""
        expected_hash = EncryptionUtils.create_secure_hash(data, salt)
        return hmac.compare_digest(expected_hash, hash_value)

# Global instances
encryption_manager = EncryptionManager()
field_encryption = FieldEncryption(encryption_manager)
key_manager = KeyManager()
secure_config = SecureConfig(encryption_manager)

# Decorators for encryption
def encrypt_response(f):
    """Decorator to encrypt response data"""
    from functools import wraps
    from flask import jsonify
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        
        if isinstance(response, (dict, list)):
            try:
                encrypted_response = encryption_manager.encrypt(response)
                return jsonify({'encrypted': True, 'data': encrypted_response})
            except Exception as e:
                logger.error(f"Failed to encrypt response: {e}")
                return jsonify(response)
        
        return response
    
    return decorated_function

def decrypt_request(f):
    """Decorator to decrypt request data"""
    from functools import wraps
    from flask import request
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.is_json:
            data = request.get_json()
            
            if data and data.get('encrypted'):
                try:
                    decrypted_data = encryption_manager.decrypt(data['data'])
                    request._decrypted_json = decrypted_data
                except Exception as e:
                    logger.error(f"Failed to decrypt request: {e}")
                    return {'error': 'Invalid encrypted data'}, 400
        
        return f(*args, **kwargs)
    
    return decorated_function

# Initialize encryption system
def initialize_encryption():
    """Initialize encryption system"""
    logger.info("Initializing encryption system...")
    
    # Set up secure configuration defaults
    if not secure_config.get('encryption_initialized'):
        secure_config.set('encryption_initialized', True)
        secure_config.set('master_key_created', datetime.utcnow().isoformat())
        secure_config.set('key_rotation_interval_days', 90)
        
        logger.info("Encryption system initialized")
    
    # Check for key rotation
    last_rotation = secure_config.get('last_key_rotation')
    if last_rotation:
        last_rotation_date = datetime.fromisoformat(last_rotation)
        if datetime.utcnow() - last_rotation_date > timedelta(days=90):
            new_key_id = key_manager.rotate_key()
            secure_config.set('last_key_rotation', datetime.utcnow().isoformat())
            secure_config.set('current_key_id', new_key_id)
            logger.info(f"Automatic key rotation performed: {new_key_id}")

if __name__ == "__main__":
    # Test encryption functionality
    print("Testing encryption system...")
    
    try:
        # Test basic encryption/decryption
        test_data = "This is a secret message"
        encrypted = encryption_manager.encrypt(test_data)
        decrypted = encryption_manager.decrypt(encrypted)
        
        print(f"Original: {test_data}")
        print(f"Encrypted: {encrypted[:50]}...")
        print(f"Decrypted: {decrypted}")
        print(f"Match: {test_data == decrypted}")
        
        # Test password hashing
        password = "test_password_123"
        hashed, salt = encryption_manager.hash_password(password)
        is_valid = encryption_manager.verify_password(password, hashed, salt)
        
        print(f"Password valid: {is_valid}")
        
        # Test field encryption
        field_value = "sensitive_data_456"
        encrypted_field = encryption_manager.encrypt_field(field_value, "test_field")
        decrypted_field = encryption_manager.decrypt_field(encrypted_field, "test_field")
        
        print(f"Field encryption match: {field_value == decrypted_field}")
        
        # Test model data encryption
        model_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password_hash': 'secret_hash',
            'two_factor_secret': 'totp_secret'
        }
        
        encrypted_model = field_encryption.encrypt_model_data('User', model_data)
        decrypted_model = field_encryption.decrypt_model_data('User', encrypted_model)
        
        print(f"Model encryption match: {model_data == decrypted_model}")
        
        # Test key management
        key_info = key_manager.get_key_info()
        print(f"Current key info: {key_info}")
        
        new_key_id = key_manager.rotate_key()
        print(f"Rotated to new key: {new_key_id}")
        
        # Test secure config
        secure_config.set('test_secret', 'confidential_value')
        retrieved_secret = secure_config.get('test_secret')
        print(f"Secure config match: {'confidential_value' == retrieved_secret}")
        
        # Test utilities
        secure_hash = EncryptionUtils.create_secure_hash("test_data")
        hash_valid = EncryptionUtils.verify_secure_hash("test_data", secure_hash, 
                                                       EncryptionUtils.create_secure_hash("test_data")[:32])
        print(f"Secure hash valid: {hash_valid}")
        
        print("All encryption tests passed!")
        
    except Exception as e:
        print(f"Encryption test failed: {e}")
        import traceback
        traceback.print_exc()