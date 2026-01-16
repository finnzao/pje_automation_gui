"""
Gerenciador de credenciais para armazenamento seguro local.
Versão simplificada que funciona sem dependências externas de criptografia.
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple


class SimpleEncryption:
    """
    Criptografia simples usando XOR com chave derivada.
    Não é tão segura quanto Fernet, mas funciona sem dependências extras.
    """
    
    def __init__(self, key: bytes):
        self.key = key
    
    def encrypt(self, data: bytes) -> bytes:
        """Criptografa dados usando XOR."""
        key_extended = (self.key * (len(data) // len(self.key) + 1))[:len(data)]
        encrypted = bytes(a ^ b for a, b in zip(data, key_extended))
        return base64.b64encode(encrypted)
    
    def decrypt(self, data: bytes) -> bytes:
        """Descriptografa dados usando XOR."""
        decoded = base64.b64decode(data)
        key_extended = (self.key * (len(decoded) // len(self.key) + 1))[:len(decoded)]
        decrypted = bytes(a ^ b for a, b in zip(decoded, key_extended))
        return decrypted


class CredentialManager:
    """
    Gerencia credenciais de forma segura.
    As credenciais são salvas localmente de forma ofuscada.
    """
    
    def __init__(self, config_dir: str = ".config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_file = self.config_dir / "credentials.dat"
        self.key_file = self.config_dir / "key.bin"
        self._cipher = None
    
    def _get_machine_id(self) -> bytes:
        """Obtém um ID único da máquina para derivação de chave."""
        machine_info = f"{os.name}-pje-automation-v2"
        return machine_info.encode()
    
    def _get_or_create_key(self) -> bytes:
        """Obtém ou cria chave de criptografia."""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                salt = f.read()
        else:
            salt = os.urandom(32)
            with open(self.key_file, 'wb') as f:
                f.write(salt)
        
        # Deriva chave usando SHA256
        key_material = self._get_machine_id() + salt
        key = hashlib.sha256(key_material).digest()
        return key
    
    def _get_cipher(self) -> SimpleEncryption:
        """Obtém instância do cipher para criptografia."""
        if self._cipher is None:
            key = self._get_or_create_key()
            self._cipher = SimpleEncryption(key)
        return self._cipher
    
    def save_credentials(self, username: str, password: str) -> bool:
        """Salva credenciais de forma criptografada."""
        try:
            cipher = self._get_cipher()
            data = json.dumps({
                "username": username,
                "password": password
            }).encode('utf-8')
            encrypted = cipher.encrypt(data)
            
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted)
            
            return True
        except Exception as e:
            print(f"Erro ao salvar credenciais: {e}")
            return False
    
    def load_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Carrega credenciais salvas."""
        if not self.credentials_file.exists():
            return None, None
        
        try:
            cipher = self._get_cipher()
            
            with open(self.credentials_file, 'rb') as f:
                encrypted = f.read()
            
            decrypted = cipher.decrypt(encrypted)
            data = json.loads(decrypted.decode('utf-8'))
            
            return data.get("username"), data.get("password")
        except Exception as e:
            print(f"Erro ao carregar credenciais: {e}")
            return None, None
    
    def has_saved_credentials(self) -> bool:
        """Verifica se existem credenciais salvas."""
        return self.credentials_file.exists()
    
    def clear_credentials(self) -> bool:
        """Remove credenciais salvas."""
        try:
            if self.credentials_file.exists():
                self.credentials_file.unlink()
            return True
        except Exception as e:
            print(f"Erro ao limpar credenciais: {e}")
            return False


class PreferencesManager:
    """Gerencia preferências do usuário."""
    
    def __init__(self, config_dir: str = ".config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.preferences_file = self.config_dir / "preferences.json"
    
    def save_preferences(self, preferences: dict) -> bool:
        """Salva preferências."""
        try:
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(preferences, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def load_preferences(self) -> dict:
        """Carrega preferências."""
        if not self.preferences_file.exists():
            return {}
        try:
            with open(self.preferences_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def get(self, key: str, default=None):
        """Obtém uma preferência específica."""
        prefs = self.load_preferences()
        return prefs.get(key, default)
    
    def set(self, key: str, value) -> bool:
        """Define uma preferência específica."""
        prefs = self.load_preferences()
        prefs[key] = value
        return self.save_preferences(prefs)
