import streamlit as st
from typing import Optional, Dict, Any

from ..config import PAGE_CONFIG
from ..state.session_state import SessionStateManager


class NavigationService:
    """
    Serviço responsável pela navegação entre páginas.
    """
    
    def __init__(self, state_manager: SessionStateManager):
        self._state = state_manager
    
    def navigate_to(self, page: str, **kwargs) -> None:
        """Navega para uma página específica."""
        if page not in PAGE_CONFIG.get_all():
            raise ValueError(f"Página inválida: {page}")
        
        if kwargs:
            self._state.update(**kwargs)
        
        self._state.current_page = page
        st.rerun()
    
    def go_to_login(self) -> None:
        """Navega para página de login."""
        self.navigate_to(PAGE_CONFIG.LOGIN)
    
    def go_to_select_profile(self) -> None:
        """Navega para seleção de perfil."""
        self.navigate_to(PAGE_CONFIG.SELECT_PROFILE)
    
    def go_to_main_menu(self) -> None:
        """Navega para menu principal."""
        self.navigate_to(PAGE_CONFIG.MAIN_MENU)
    
    def go_to_download_by_task(self) -> None:
        """Navega para download por tarefa."""
        self.navigate_to(PAGE_CONFIG.DOWNLOAD_BY_TASK)
    
    def go_to_download_by_tag(self) -> None:
        """Navega para download por etiqueta."""
        self.navigate_to(PAGE_CONFIG.DOWNLOAD_BY_TAG)
    
    def go_to_download_by_number(self) -> None:
        """Navega para download por número."""
        self.navigate_to(PAGE_CONFIG.DOWNLOAD_BY_NUMBER)
    
    def go_to_download_by_subject(self) -> None:
        """Navega para download por assunto."""
        # Resetar estado do fluxo de assuntos
        self._state.set("subject_step", 1)
        self._state.set("tarefas_ignoradas", [])
        self._state.set("assuntos_analisados", [])
        self.navigate_to(PAGE_CONFIG.DOWNLOAD_BY_SUBJECT)
    
    def go_to_processing_task(
        self,
        task: Any,
        limit: Optional[int] = None,
        use_favorites: bool = False,
        batch_size: int = 10
    ) -> None:
        """Navega para processamento de tarefa."""
        self._state.reset_processing_state()
        self.navigate_to(
            PAGE_CONFIG.PROCESSING_TASK,
            selected_task=task,
            task_limit=limit,
            task_usar_favoritas=use_favorites,
            task_tamanho_lote=batch_size,
        )
    
    def go_to_processing_tag(
        self,
        tag: Any,
        limit: Optional[int] = None,
        batch_size: int = 10
    ) -> None:
        """Navega para processamento de etiqueta."""
        self._state.reset_processing_state()
        self.navigate_to(
            PAGE_CONFIG.PROCESSING_TAG,
            selected_tag=tag,
            tag_limit=limit,
            tag_tamanho_lote=batch_size,
        )
    
    def go_to_processing_number(
        self,
        processes: list,
        document_type: str = "Selecione"
    ) -> None:
        """Navega para processamento por número."""
        self._state.reset_processing_state()
        self.navigate_to(
            PAGE_CONFIG.PROCESSING_NUMBER,
            processos_para_baixar=processes,
            tipo_documento_numero=document_type,
        )
    
    def go_to_processing_subject(
        self,
        assunto: Any,
        limit: Optional[int] = None,
        batch_size: int = 10
    ) -> None:
        """Navega para processamento por assunto."""
        self._state.reset_processing_state()
        self.navigate_to(
            PAGE_CONFIG.PROCESSING_SUBJECT,
            selected_subject=assunto,
            subject_limit=limit,
            subject_tamanho_lote=batch_size,
        )
    
    def go_to_result(self, report: Dict[str, Any]) -> None:
        """Navega para página de resultado."""
        self._state.reset_processing_state()
        self.navigate_to(
            PAGE_CONFIG.RESULT,
            relatorio=report,
        )
    
    def go_back(self) -> None:
        """Navega para página anterior baseado no contexto."""
        current = self._state.current_page
        
        back_mapping = {
            PAGE_CONFIG.SELECT_PROFILE: PAGE_CONFIG.LOGIN,
            PAGE_CONFIG.MAIN_MENU: PAGE_CONFIG.SELECT_PROFILE,
            PAGE_CONFIG.DOWNLOAD_BY_TASK: PAGE_CONFIG.MAIN_MENU,
            PAGE_CONFIG.DOWNLOAD_BY_TAG: PAGE_CONFIG.MAIN_MENU,
            PAGE_CONFIG.DOWNLOAD_BY_NUMBER: PAGE_CONFIG.MAIN_MENU,
            PAGE_CONFIG.DOWNLOAD_BY_SUBJECT: PAGE_CONFIG.MAIN_MENU,
            PAGE_CONFIG.PROCESSING_TASK: PAGE_CONFIG.DOWNLOAD_BY_TASK,
            PAGE_CONFIG.PROCESSING_TAG: PAGE_CONFIG.DOWNLOAD_BY_TAG,
            PAGE_CONFIG.PROCESSING_NUMBER: PAGE_CONFIG.DOWNLOAD_BY_NUMBER,
            PAGE_CONFIG.PROCESSING_SUBJECT: PAGE_CONFIG.DOWNLOAD_BY_SUBJECT,
            PAGE_CONFIG.RESULT: PAGE_CONFIG.MAIN_MENU,
        }
        
        target = back_mapping.get(current, PAGE_CONFIG.MAIN_MENU)
        self.navigate_to(target)
    
    @property
    def current_page(self) -> str:
        """Retorna página atual."""
        return self._state.current_page
    
    def is_on_page(self, page: str) -> bool:
        """Verifica se está em uma página específica."""
        return self._state.current_page == page
    
    def is_on_processing_page(self) -> bool:
        """Verifica se está em uma página de processamento."""
        return self._state.current_page in [
            PAGE_CONFIG.PROCESSING_TASK,
            PAGE_CONFIG.PROCESSING_TAG,
            PAGE_CONFIG.PROCESSING_NUMBER,
            PAGE_CONFIG.PROCESSING_SUBJECT,
        ]