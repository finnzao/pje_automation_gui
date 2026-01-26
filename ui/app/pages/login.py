import streamlit as st
import time
from typing import Optional, Tuple

from .base import BasePage
from ..components.forms import LoginForm
from ..components.buttons import ActionButton, NavigationButton
from ui.credential_manager import CredentialManager


class LoginPage(BasePage):
    """
    Página de autenticação do usuário.
    """
    
    PAGE_TITLE = "PJE Download Manager"
    REQUIRES_AUTH = False
    REQUIRES_PROFILE = False
    
    def __init__(self, state_manager, navigation):
        super().__init__(state_manager, navigation)
        self._credential_manager = CredentialManager()
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho customizado."""
        st.title(self.PAGE_TITLE)
        st.caption("Sistema de download automatizado de processos judiciais")
        st.markdown("---")
    
    def _get_saved_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Obtém credenciais salvas."""
        return self._credential_manager.load_credentials()
    
    def _has_saved_credentials(self) -> bool:
        """Verifica se há credenciais salvas."""
        user, pwd = self._get_saved_credentials()
        return user is not None and pwd is not None
    
    def _do_login(self, username: str, password: str) -> None:
        """
        Executa o login.
        
        Args:
            username: CPF do usuário
            password: Senha
        """
        with st.spinner("Autenticando..."):
            try:
                if self.session_service.login(username, password):
                    st.success("Login realizado com sucesso!")
                    time.sleep(0.5)
                    self._navigation.go_to_select_profile()
                else:
                    st.error(
                        "Falha na autenticação. "
                        "Verifique suas credenciais e tente novamente."
                    )
            except Exception as e:
                st.error(f"Erro ao conectar: {str(e)}")
    
    def _render_saved_credentials_section(self) -> bool:
        """
        Renderiza seção de credenciais salvas.
        
        Returns:
            True se login foi iniciado com credenciais salvas
        """
        saved_user, saved_pass = self._get_saved_credentials()
        
        st.info(f"Credenciais salvas para: {saved_user}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "Entrar com credenciais salvas",
                use_container_width=True,
                type="primary",
                key="btn_login_saved"
            ):
                self._do_login(saved_user, saved_pass)
                return True
        
        with col2:
            if st.button(
                "Limpar credenciais",
                use_container_width=True,
                key="btn_clear_cred"
            ):
                self._credential_manager.clear_credentials()
                st.rerun()
        
        st.markdown("---")
        return False
    
    def _render_login_form(self, saved_user: str = "") -> None:
        """
        Renderiza formulário de login.
        
        Args:
            saved_user: Username salvo para preencher
        """
        has_saved = self._has_saved_credentials()
        
        with st.form("login_form", clear_on_submit=False):
            st.subheader("Login")
            
            username = st.text_input(
                "CPF",
                value=saved_user,
                placeholder="Digite seu CPF",
                key="input_username"
            )
            
            password = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
                key="input_password"
            )
            
            save_cred = st.checkbox(
                "Salvar credenciais neste computador",
                value=has_saved,
                key="chk_save_cred"
            )
            
            submitted = st.form_submit_button(
                "Entrar",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                if not username or not password:
                    st.error("Por favor, preencha CPF e senha")
                else:
                    if save_cred:
                        self._credential_manager.save_credentials(username, password)
                    self._do_login(username, password)
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página de login."""
        # Layout centralizado
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # Seção de credenciais salvas
            if self._has_saved_credentials():
                if self._render_saved_credentials_section():
                    return
            
            # Formulário de login
            saved_user, _ = self._get_saved_credentials()
            self._render_login_form(saved_user or "")