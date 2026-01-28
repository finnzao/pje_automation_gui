import streamlit as st
from typing import Any, Optional, Dict, List, TypeVar, Generic
from dataclasses import dataclass, field

from ..config import APP_CONFIG, PAGE_CONFIG


T = TypeVar('T')


@dataclass
class SessionStateDefaults:
    """Valores padrão para o estado da sessão."""
    
    # Navegação
    page: str = PAGE_CONFIG.LOGIN
    
    # Autenticação
    logged_in: bool = False
    user_name: Optional[str] = None
    
    # Perfil
    perfil_selecionado: Any = None
    perfis: List = field(default_factory=list)
    
    # Tarefas
    tarefas: List = field(default_factory=list)
    tarefas_favoritas: List = field(default_factory=list)
    tarefas_para_analise: List = field(default_factory=list)
    
    # Assuntos
    tarefas_ignoradas: List = field(default_factory=list)
    assuntos_analisados: List = field(default_factory=list)
    subject_step: int = 1
    
    # Cliente PJE
    pje_client: Any = None
    
    # Resultado
    relatorio: Optional[Dict] = None
    
    # Configurações
    download_dir: str = APP_CONFIG.DOWNLOAD_DIR
    
    # Controle de processamento
    cancelamento_solicitado: bool = False
    show_cancel_confirm: bool = False
    perfil_sendo_selecionado: bool = False
    processing_iteration: int = 0
    
    # Download por tarefa
    selected_task: Any = None
    task_limit: Optional[int] = None
    task_usar_favoritas: bool = False
    task_tamanho_lote: int = APP_CONFIG.DEFAULT_BATCH_SIZE
    
    # Download por etiqueta
    selected_tag: Any = None
    tag_limit: Optional[int] = None
    tag_tamanho_lote: int = APP_CONFIG.DEFAULT_BATCH_SIZE
    
    # Download por número
    processos_para_baixar: List[str] = field(default_factory=list)
    tipo_documento_numero: str = "Selecione"
    
    # Download por assunto
    selected_subject: Any = None
    subject_limit: Optional[int] = None
    subject_tamanho_lote: int = APP_CONFIG.DEFAULT_BATCH_SIZE
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "page": self.page,
            "logged_in": self.logged_in,
            "user_name": self.user_name,
            "perfil_selecionado": self.perfil_selecionado,
            "perfis": self.perfis,
            "tarefas": self.tarefas,
            "tarefas_favoritas": self.tarefas_favoritas,
            "tarefas_para_analise": self.tarefas_para_analise,
            "tarefas_ignoradas": self.tarefas_ignoradas,
            "assuntos_analisados": self.assuntos_analisados,
            "subject_step": self.subject_step,
            "pje_client": self.pje_client,
            "relatorio": self.relatorio,
            "download_dir": self.download_dir,
            "cancelamento_solicitado": self.cancelamento_solicitado,
            "show_cancel_confirm": self.show_cancel_confirm,
            "perfil_sendo_selecionado": self.perfil_sendo_selecionado,
            "processing_iteration": self.processing_iteration,
            "selected_task": self.selected_task,
            "task_limit": self.task_limit,
            "task_usar_favoritas": self.task_usar_favoritas,
            "task_tamanho_lote": self.task_tamanho_lote,
            "selected_tag": self.selected_tag,
            "tag_limit": self.tag_limit,
            "tag_tamanho_lote": self.tag_tamanho_lote,
            "processos_para_baixar": self.processos_para_baixar,
            "tipo_documento_numero": self.tipo_documento_numero,
            "selected_subject": self.selected_subject,
            "subject_limit": self.subject_limit,
            "subject_tamanho_lote": self.subject_tamanho_lote,
        }


class SessionStateManager:
    """
    Gerenciador centralizado do estado da sessão.
    """
    
    def __init__(self):
        """Inicializa o gerenciador."""
        self._defaults = SessionStateDefaults()
        self._initialized = False
    
    def initialize(self) -> None:
        """Inicializa o estado da sessão com valores padrão."""
        if self._initialized:
            return
        
        defaults_dict = self._defaults.to_dict()
        
        for key, value in defaults_dict.items():
            if key not in st.session_state:
                st.session_state[key] = value
        
        self._initialized = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor do estado."""
        return st.session_state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Define valor no estado."""
        st.session_state[key] = value
    
    def update(self, **kwargs) -> None:
        """Atualiza múltiplos valores no estado."""
        for key, value in kwargs.items():
            st.session_state[key] = value
    
    def delete(self, key: str) -> None:
        """Remove valor do estado."""
        if key in st.session_state:
            del st.session_state[key]
    
    def has(self, key: str) -> bool:
        """Verifica se chave existe no estado."""
        return key in st.session_state
    
    def clear(self) -> None:
        """Limpa todo o estado da sessão."""
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        self._initialized = False
    
    def reset_to_defaults(self) -> None:
        """Reseta estado para valores padrão."""
        self.clear()
        self.initialize()
    
    # Propriedades de conveniência
    
    @property
    def current_page(self) -> str:
        """Página atual."""
        return self.get("page", PAGE_CONFIG.LOGIN)
    
    @current_page.setter
    def current_page(self, value: str) -> None:
        self.set("page", value)
    
    @property
    def is_logged_in(self) -> bool:
        """Verifica se está logado."""
        return self.get("logged_in", False)
    
    @is_logged_in.setter
    def is_logged_in(self, value: bool) -> None:
        self.set("logged_in", value)
    
    @property
    def user_name(self) -> Optional[str]:
        """Nome do usuário."""
        return self.get("user_name")
    
    @user_name.setter
    def user_name(self, value: Optional[str]) -> None:
        self.set("user_name", value)
    
    @property
    def pje_client(self) -> Any:
        """Cliente PJE."""
        return self.get("pje_client")
    
    @pje_client.setter
    def pje_client(self, value: Any) -> None:
        self.set("pje_client", value)
    
    @property
    def selected_profile(self) -> Any:
        """Perfil selecionado."""
        return self.get("perfil_selecionado")
    
    @selected_profile.setter
    def selected_profile(self, value: Any) -> None:
        self.set("perfil_selecionado", value)
    
    @property
    def is_cancellation_requested(self) -> bool:
        """Verifica se cancelamento foi solicitado."""
        return self.get("cancelamento_solicitado", False)
    
    @is_cancellation_requested.setter
    def is_cancellation_requested(self, value: bool) -> None:
        self.set("cancelamento_solicitado", value)
    
    @property
    def report(self) -> Optional[Dict]:
        """Relatório atual."""
        return self.get("relatorio")
    
    @report.setter
    def report(self, value: Optional[Dict]) -> None:
        self.set("relatorio", value)
    
    def increment_processing_iteration(self) -> int:
        """Incrementa e retorna iteração de processamento."""
        current = self.get("processing_iteration", 0)
        new_value = current + 1
        self.set("processing_iteration", new_value)
        return new_value
    
    def reset_processing_state(self) -> None:
        """Reseta estado de processamento."""
        self.update(
            cancelamento_solicitado=False,
            show_cancel_confirm=False,
            processing_iteration=0,
        )
    
    def reset_subject_state(self) -> None:
        """Reseta estado do fluxo de assuntos."""
        self.update(
            subject_step=1,
            tarefas_ignoradas=[],
            assuntos_analisados=[],
            tarefas_para_analise=[],
            selected_subject=None,
        )