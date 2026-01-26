from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass(frozen=True)
class AppConfig:
    """Configurações gerais da aplicação."""
    
    # Informações da aplicação
    APP_TITLE: str = "PJE Download Manager"
    APP_ICON: str = "⚖️"
    APP_VERSION: str = "2.1.0"
    
    # Layout
    LAYOUT: str = "wide"
    INITIAL_SIDEBAR_STATE: str = "collapsed"
    
    # Diretórios
    DOWNLOAD_DIR: str = "./downloads"
    LOG_DIR: str = "./.logs"
    SESSION_DIR: str = "./.session"
    CONFIG_DIR: str = "./.config"
    
    # Timeouts e delays
    DEFAULT_TIMEOUT: int = 300
    SESSION_CHECK_INTERVAL: int = 300  # 5 minutos
    
    # Limites
    MAX_PROCESSES_LIMIT: int = 500
    DEFAULT_BATCH_SIZE: int = 10
    MIN_BATCH_SIZE: int = 5
    MAX_BATCH_SIZE: int = 30


@dataclass(frozen=True)
class PageConfig:
    """Configuração de páginas disponíveis."""
    
    LOGIN: str = "login"
    SELECT_PROFILE: str = "select_profile"
    MAIN_MENU: str = "main_menu"
    DOWNLOAD_BY_TASK: str = "download_by_task"
    DOWNLOAD_BY_TAG: str = "download_by_tag"
    DOWNLOAD_BY_NUMBER: str = "download_by_number"
    PROCESSING_TASK: str = "processing_task"
    PROCESSING_TAG: str = "processing_tag"
    PROCESSING_NUMBER: str = "processing_number"
    RESULT: str = "result"
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Retorna todas as páginas disponíveis."""
        return [
            cls.LOGIN,
            cls.SELECT_PROFILE,
            cls.MAIN_MENU,
            cls.DOWNLOAD_BY_TASK,
            cls.DOWNLOAD_BY_TAG,
            cls.DOWNLOAD_BY_NUMBER,
            cls.PROCESSING_TASK,
            cls.PROCESSING_TAG,
            cls.PROCESSING_NUMBER,
            cls.RESULT,
        ]


@dataclass(frozen=True)
class StatusConfig:
    """Configuração de status de processamento."""
    
    # Status disponíveis
    INICIANDO: str = "iniciando"
    BUSCANDO_TAREFA: str = "buscando_tarefa"
    BUSCANDO_ETIQUETA: str = "buscando_etiqueta"
    BUSCANDO_PROCESSO: str = "buscando_processo"
    LISTANDO_PROCESSOS: str = "listando_processos"
    PROCESSANDO: str = "processando"
    BAIXANDO_LOTE: str = "baixando_lote"
    AGUARDANDO_DOWNLOADS: str = "aguardando_downloads"
    VERIFICANDO_INTEGRIDADE: str = "verificando_integridade"
    RETRY_1: str = "retry_1"
    RETRY_2: str = "retry_2"
    CONCLUIDO: str = "concluido"
    CONCLUIDO_COM_FALHAS: str = "concluido_com_falhas"
    CANCELADO: str = "cancelado"
    ERRO: str = "erro"
    
    @classmethod
    def get_display_text(cls, status: str) -> str:
        """Retorna texto de exibição para o status."""
        texts = {
            cls.INICIANDO: "Iniciando",
            cls.BUSCANDO_TAREFA: "Buscando tarefa",
            cls.BUSCANDO_ETIQUETA: "Buscando etiqueta",
            cls.BUSCANDO_PROCESSO: "Buscando processo",
            cls.LISTANDO_PROCESSOS: "Listando processos",
            cls.PROCESSANDO: "Processando",
            cls.BAIXANDO_LOTE: "Baixando arquivos",
            cls.AGUARDANDO_DOWNLOADS: "Aguardando downloads",
            cls.VERIFICANDO_INTEGRIDADE: "Verificando integridade",
            cls.RETRY_1: "Tentativa 1/2",
            cls.RETRY_2: "Tentativa 2/2",
            cls.CONCLUIDO: "Concluído",
            cls.CONCLUIDO_COM_FALHAS: "Concluído com falhas",
            cls.CANCELADO: "Cancelado",
            cls.ERRO: "Erro",
        }
        return texts.get(status, status)
    
    @classmethod
    def is_final_status(cls, status: str) -> bool:
        """Verifica se é um status final."""
        return status in [
            cls.CONCLUIDO,
            cls.CONCLUIDO_COM_FALHAS,
            cls.CANCELADO,
            cls.ERRO,
        ]


@dataclass(frozen=True)
class DocumentTypeConfig:
    """Configuração de tipos de documento."""
    
    OPTIONS: tuple = (
        "Selecione",
        "Petição Inicial",
        "Petição",
        "Sentença",
        "Decisão",
        "Despacho",
        "Acórdão",
        "Outros documentos",
    )
    
    DEFAULT: str = "Selecione"


APP_CONFIG = AppConfig()
PAGE_CONFIG = PageConfig()
STATUS_CONFIG = StatusConfig()
DOCUMENT_TYPE_CONFIG = DocumentTypeConfig()