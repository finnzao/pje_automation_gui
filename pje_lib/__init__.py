"""
PJE Lib - Biblioteca compartilhada para automacao do PJE.
"""

from pathlib import Path
from dotenv import load_dotenv

env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from .client import PJEClient
from .config import (
    BASE_URL, SSO_URL, API_BASE,
    TIPO_DOCUMENTO_VALUES,
)
from .models import (
    Usuario, Perfil, Tarefa, ProcessoTarefa,
    Etiqueta, Processo, DownloadDisponivel,
    DiagnosticoDownload, AssuntoPrincipal,
)

__version__ = "1.0.0"
__all__ = [
    "PJEClient",
    "BASE_URL", "SSO_URL", "API_BASE", "TIPO_DOCUMENTO_VALUES",
    "Usuario", "Perfil", "Tarefa", "ProcessoTarefa",
    "Etiqueta", "Processo", "DownloadDisponivel", "DiagnosticoDownload",
    "AssuntoPrincipal",
]