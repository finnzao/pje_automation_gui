import streamlit as st
from abc import ABC, abstractmethod
from typing import Optional, Any

from ..state.session_state import SessionStateManager
from ..services.navigation import NavigationService
from ..services.session_service import PJESessionService
from ..services.download_manager import DownloadManagerService


class BasePage(ABC):
    """
    Classe base abstrata para todas as páginas.
    
    Define a interface comum e fornece acesso aos
    serviços necessários.
    """
    
    PAGE_TITLE: str = "Página"
    
    REQUIRES_AUTH: bool = True
    
    REQUIRES_PROFILE: bool = False
    
    def __init__(
        self,
        state_manager: SessionStateManager,
        navigation: NavigationService,
    ):
        """
        Inicializa a página.
        
        Args:
            state_manager: Gerenciador de estado
            navigation: Serviço de navegação
        """
        self._state = state_manager
        self._navigation = navigation
        self._session_service: Optional[PJESessionService] = None
        self._download_manager: Optional[DownloadManagerService] = None
    
    @property
    def state(self) -> SessionStateManager:
        """Retorna o gerenciador de estado."""
        return self._state
    
    @property
    def navigation(self) -> NavigationService:
        """Retorna o serviço de navegação."""
        return self._navigation
    
    @property
    def session_service(self) -> PJESessionService:
        """Retorna o serviço de sessão PJE (lazy initialization)."""
        if self._session_service is None:
            self._session_service = PJESessionService(self._state)
        return self._session_service
    
    @property
    def download_manager(self) -> DownloadManagerService:
        """Retorna o gerenciador de downloads (lazy initialization)."""
        if self._download_manager is None:
            self._download_manager = DownloadManagerService(
                self._state,
                self.session_service
            )
        return self._download_manager
    
    def _check_auth(self) -> bool:
        """
        Verifica se o usuário está autenticado.
        
        Returns:
            True se autenticado ou não requer autenticação
        """
        if not self.REQUIRES_AUTH:
            return True
        
        if not self.session_service.validate_session():
            st.error("Sessão expirada. Redirecionando para login...")
            import time
            time.sleep(1)
            self.session_service.clear_session_complete()
            self._navigation.go_to_login()
            return False
        
        return True
    
    def _check_profile(self) -> bool:
        """
        Verifica se há perfil selecionado.
        
        Returns:
            True se há perfil ou não requer perfil
        """
        if not self.REQUIRES_PROFILE:
            return True
        
        if not self._state.selected_profile:
            st.warning("Nenhum perfil selecionado")
            self._navigation.go_to_select_profile()
            return False
        
        return True
    
    def _render_header(self) -> None:
        """Renderiza o cabeçalho da página."""
        st.title(self.PAGE_TITLE)
        
        # Informações do usuário/perfil se autenticado
        if self.REQUIRES_AUTH and self._state.user_name:
            caption_parts = [f"Usuário: {self._state.user_name}"]
            
            if self._state.selected_profile:
                caption_parts.append(
                    f"Perfil: {self._state.selected_profile.nome}"
                )
            
            st.caption(" | ".join(caption_parts))
        
        st.markdown("---")
    
    def _render_sidebar(self) -> None:
        """
        Renderiza a sidebar.
        Pode ser sobrescrito pelas subclasses.
        """
        pass
    
    @abstractmethod
    def _render_content(self) -> None:
        """
        Renderiza o conteúdo principal da página.
        Deve ser implementado pelas subclasses.
        """
        pass
    
    def render(self) -> None:
        """
        Renderiza a página completa.
        
        Executa verificações de autenticação/perfil,
        renderiza header, sidebar e conteúdo.
        """
        # Verificações
        if not self._check_auth():
            return
        
        if not self._check_profile():
            return
        
        # Renderizar página
        self._render_sidebar()
        self._render_header()
        self._render_content()


class ProcessingPageBase(BasePage):
    """
    Classe base para páginas de processamento.
    
    Fornece infraestrutura comum para páginas que
    executam processamentos longos.
    """
    
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def __init__(
        self,
        state_manager: SessionStateManager,
        navigation: NavigationService,
    ):
        super().__init__(state_manager, navigation)
        self._start_time: Optional[float] = None
    
    def _get_processing_params(self) -> dict:
        """
        Obtém parâmetros do processamento.
        Deve ser sobrescrito pelas subclasses.
        
        Returns:
            Dict com parâmetros
        """
        return {}
    
    def _validate_params(self) -> bool:
        """
        Valida parâmetros antes de processar.
        Deve ser sobrescrito pelas subclasses.
        
        Returns:
            True se válido
        """
        return True
    
    def _get_back_page(self) -> str:
        """
        Retorna página para voltar.
        Deve ser sobrescrito pelas subclasses.
        
        Returns:
            Nome da página
        """
        from ..config import PAGE_CONFIG
        return PAGE_CONFIG.MAIN_MENU
    
    @abstractmethod
    def _get_generator(self):
        """
        Retorna o generator de processamento.
        Deve ser implementado pelas subclasses.
        """
        pass
    
    def _handle_cancel_request(self) -> None:
        """Trata solicitação de cancelamento."""
        self._state.set("show_cancel_confirm", True)
        st.rerun()
    
    def _handle_cancel_confirm(self) -> None:
        """Confirma cancelamento."""
        self._state.is_cancellation_requested = True
        self._state.set("show_cancel_confirm", False)
        self.download_manager.cancel_processing()
        st.rerun()
    
    def _handle_cancel_deny(self) -> None:
        """Nega cancelamento."""
        self._state.set("show_cancel_confirm", False)
        st.rerun()