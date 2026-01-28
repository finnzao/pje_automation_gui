import streamlit as st
from typing import Dict, Callable, Optional

from .config import APP_CONFIG, PAGE_CONFIG
from .state.session_state import SessionStateManager
from .styles.css import StyleManager
from .services.navigation import NavigationService
from .pages import (
    LoginPage,
    SelectProfilePage,
    MainMenuPage,
    DownloadByTaskPage,
    DownloadByTagPage,
    DownloadByNumberPage,
    DownloadBySubjectPage,
    ProcessingTaskPage,
    ProcessingTagPage,
    ProcessingNumberPage,
    ProcessingSubjectPage,
    ResultPage,
)


class Application:
    """
    Classe principal da aplicação.
    Responsável por configurar e executar o app Streamlit.
    """
    
    def __init__(self):
        """Inicializa a aplicação."""
        self._pages: Dict[str, Callable] = {}
        self._state_manager: Optional[SessionStateManager] = None
        self._navigation: Optional[NavigationService] = None
        self._setup_complete = False
    
    def _configure_page(self) -> None:
        """Configura a página Streamlit."""
        st.set_page_config(
            page_title=APP_CONFIG.APP_TITLE,
            page_icon=APP_CONFIG.APP_ICON,
            layout=APP_CONFIG.LAYOUT,
            initial_sidebar_state=APP_CONFIG.INITIAL_SIDEBAR_STATE,
        )
    
    def _apply_styles(self) -> None:
        """Aplica estilos CSS customizados."""
        StyleManager.apply_global_styles()
    
    def _init_state(self) -> None:
        """Inicializa o gerenciador de estado."""
        self._state_manager = SessionStateManager()
        self._state_manager.initialize()
    
    def _init_navigation(self) -> None:
        """Inicializa o serviço de navegação."""
        self._navigation = NavigationService(self._state_manager)
    
    def _register_pages(self) -> None:
        """Registra todas as páginas disponíveis."""
        self._pages = {
            PAGE_CONFIG.LOGIN: LoginPage,
            PAGE_CONFIG.SELECT_PROFILE: SelectProfilePage,
            PAGE_CONFIG.MAIN_MENU: MainMenuPage,
            PAGE_CONFIG.DOWNLOAD_BY_TASK: DownloadByTaskPage,
            PAGE_CONFIG.DOWNLOAD_BY_TAG: DownloadByTagPage,
            PAGE_CONFIG.DOWNLOAD_BY_NUMBER: DownloadByNumberPage,
            PAGE_CONFIG.DOWNLOAD_BY_SUBJECT: DownloadBySubjectPage,
            PAGE_CONFIG.PROCESSING_TASK: ProcessingTaskPage,
            PAGE_CONFIG.PROCESSING_TAG: ProcessingTagPage,
            PAGE_CONFIG.PROCESSING_NUMBER: ProcessingNumberPage,
            PAGE_CONFIG.PROCESSING_SUBJECT: ProcessingSubjectPage,
            PAGE_CONFIG.RESULT: ResultPage,
        }
    
    def _setup(self) -> None:
        """Executa setup inicial da aplicação."""
        if self._setup_complete:
            return
        
        self._configure_page()
        self._apply_styles()
        self._init_state()
        self._init_navigation()
        self._register_pages()
        self._setup_complete = True
    
    def _get_current_page(self) -> Callable:
        """Obtém a página atual baseada no estado."""
        current_page_name = self._state_manager.get("page", PAGE_CONFIG.LOGIN)
        page_class = self._pages.get(current_page_name)
        
        if page_class is None:
            page_class = self._pages[PAGE_CONFIG.LOGIN]
        
        return page_class
    
    def _render_current_page(self) -> None:
        """Renderiza a página atual."""
        page_class = self._get_current_page()
        page_instance = page_class(
            state_manager=self._state_manager,
            navigation=self._navigation,
        )
        page_instance.render()
    
    def run(self) -> None:
        """Executa a aplicação."""
        self._setup()
        self._render_current_page()


def create_app() -> Application:
    """Factory function para criar a aplicação."""
    return Application()


def main() -> None:
    """Função principal de entrada."""
    app = create_app()
    app.run()