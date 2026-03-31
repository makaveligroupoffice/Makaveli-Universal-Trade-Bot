from cryptography.fernet import Fernet
import os
import base64
import logging
from config import Config

log = logging.getLogger("SecurityManager")

class SecurityManager:
    """Handles encryption/decryption of sensitive user data and secret validation."""
    
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            key = Config.API_KEY_ENCRYPTION_KEY
            if not key or key == "secure-encryption-key-12345":
                log.warning("USING DEFAULT/INSECURE ENCRYPTION KEY. Please set API_KEY_ENCRYPTION_KEY in .env")
            
            # Fernet key must be 32 bytes and base64 encoded.
            # We'll hash the config key to ensure it's always the right format.
            import hashlib
            key_hashed = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_hashed)
            cls._fernet = Fernet(fernet_key)
        return cls._fernet

    @classmethod
    def encrypt(cls, data: str) -> str:
        """Encrypts a string and returns the base64-encoded encrypted string."""
        if not data:
            return ""
        f = cls._get_fernet()
        return f.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        """Decrypts a base64-encoded encrypted string."""
        if not encrypted_data:
            return ""
        f = cls._get_fernet()
        try:
            return f.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            log.error(f"Decryption failed: {e}")
            return ""

    @classmethod
    def validate_webhook_secret(cls, request_secret: str) -> bool:
        """Validates if the provided secret matches the configured webhook secret."""
        if not request_secret:
            return False
        return request_secret == Config.WEBHOOK_SECRET
    
    @classmethod
    def validate_tradebot_secret(cls, request_secret: str) -> bool:
        """Validates if the provided secret matches the X-TradeBot-Secret."""
        if not request_secret:
            # If the secret is not provided, we check if we're in 'development' mode (e.g., debug enabled)
            # to avoid blocking PyCharm local testing if the user hasn't set up headers yet.
            if Config.DEBUG:
                log.debug("No X-TradeBot-Secret provided, but DEBUG is enabled. Allowing request.")
                return True
            return False
        # For now, we reuse WEBHOOK_SECRET for both for simplicity, 
        # or we could add a separate TRADEBOT_SECRET to Config.
        return request_secret == Config.WEBHOOK_SECRET
