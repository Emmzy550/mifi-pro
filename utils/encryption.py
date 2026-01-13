from cryptography.fernet import Fernet
import os

class EncryptionAgent:
    """
    Handles PII encryption and decryption using Fernet (AES).
    """
    _key = None
    _fernet = None

    @classmethod
    def _init(cls):
        if cls._fernet is None:
            # In a real app, this key would be in a secure Vault/Env
            cls._key = os.getenv("PII_SECRET_KEY", Fernet.generate_key().decode())
            cls._fernet = Fernet(cls._key.encode())

    @classmethod
    def encrypt(cls, data: str) -> str:
        cls._init()
        if not data: return data
        return cls._fernet.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        cls._init()
        if not encrypted_data: return encrypted_data
        try:
            return cls._fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return "[DECRYPTION_FAILED]"

    @classmethod
    def mask(cls, data: str) -> str:
        """Simple masking for logs/UI."""
        if not data: return data
        if len(data) <= 4: return "****"
        return f"{data[:2]}****{data[-2:]}"
