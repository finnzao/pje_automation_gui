import streamlit as st
import time

from .base import BasePage
from ..components.buttons import ActionButton, NavigationButton
from ..services.download_manager import DownloadManagerService


class MainMenuPage(BasePage):
    """
    Menu principal com opções de download.
    """
    
    PAGE_TITLE = "Menu Principal"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _render_download_options(self) -> None:
        """Renderiza cards de opções de download."""
        # Primeira linha: 3 opções
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("📋 Download por Tarefa")
            st.markdown(
                "Baixar processos vinculados a uma tarefa específica do sistema"
            )
            if st.button(
                "Acessar",
                key="btn_task",
                use_container_width=True,
                type="primary"
            ):
                self._navigation.go_to_download_by_task()
        
        with col2:
            st.subheader("🏷️ Download por Etiqueta")
            st.markdown(
                "Baixar processos marcados com uma etiqueta específica"
            )
            if st.button(
                "Acessar",
                key="btn_tag",
                use_container_width=True,
                type="primary"
            ):
                self._navigation.go_to_download_by_tag()
        
        with col3:
            st.subheader("🔢 Download por Número")
            st.markdown(
                "Baixar processo(s) informando o número CNJ completo"
            )
            if st.button(
                "Acessar",
                key="btn_numero",
                use_container_width=True,
                type="primary"
            ):
                self._navigation.go_to_download_by_number()
        
        # Segunda linha: nova opção de assunto
        st.markdown("---")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.subheader("📚 Download por Assunto")
            st.markdown(
                "Baixar processos agrupados pelo assunto principal"
            )
            if st.button(
                "Acessar",
                key="btn_subject",
                use_container_width=True,
                type="primary"
            ):
                self._navigation.go_to_download_by_subject()
        
        with col_b:
            # Espaço reservado para futuras opções
            pass
        
        with col_c:
            # Espaço reservado para futuras opções
            pass
    
    def _render_actions(self) -> None:
        """Renderiza seção de ações."""
        st.subheader("Ações")
        
        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        
        with action_col1:
            if st.button(
                "🔄 Trocar perfil",
                use_container_width=True,
                key="btn_change_profile"
            ):
                self._state.set("tarefas", [])
                self._state.set("tarefas_favoritas", [])
                self._state.set("tarefas_para_analise", [])
                self._state.set("assuntos_analisados", [])
                self._navigation.go_to_select_profile()
        
        with action_col2:
            if st.button(
                "📂 Abrir pasta de downloads",
                use_container_width=True,
                key="btn_open_downloads"
            ):
                download_dir = self._state.get("download_dir", "./downloads")
                DownloadManagerService.open_folder(download_dir)
        
        with action_col3:
            if st.button(
                "🔍 Verificar sessão",
                use_container_width=True,
                key="btn_check_session_main"
            ):
                self._verify_session()
        
        with action_col4:
            if st.button(
                "🚪 Sair do sistema",
                use_container_width=True,
                key="btn_logout_main"
            ):
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
    
    def _verify_session(self) -> None:
        """Verifica sessão."""
        with st.spinner("Verificando..."):
            if self.session_service.validate_session_full():
                st.success("✓ Sessão válida")
            else:
                st.error("✗ Sessão corrompida. Fazendo logout...")
                time.sleep(1)
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
    
    def _render_content(self) -> None:
        """Renderiza conteúdo do menu principal."""
        # Opções de download
        self._render_download_options()
        
        st.markdown("---")
        
        # Ações
        self._render_actions()