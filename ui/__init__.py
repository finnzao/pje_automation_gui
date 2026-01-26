"""
Módulo de interface gráfica do PJE Download Manager.

Este módulo contém:
- credential_manager: Gerenciamento de credenciais
- app: Aplicação Streamlit modular
"""

from .credential_manager import CredentialManager, PreferencesManager

# Importar Application do submódulo app
try:
    from .app import Application
except ImportError:
    # Fallback se o módulo app ainda não existir
    Application = None

__all__ = [
    "CredentialManager",
    "PreferencesManager",
    "Application",
]