import streamlit as st
import time
from typing import List, Any

from .base import BasePage
from ..components.forms import SearchInput
from ..components.buttons import NavigationButton, ActionButton
from ..components.lists import ProfileList


class SelectProfilePage(BasePage):
    """
    Página para seleção de perfil de acesso.
    """
    
    PAGE_TITLE = "Selecionar Perfil"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = False
    
    def _render_sidebar(self) -> None:
        """Renderiza sidebar com ações."""
        pass  # Sem sidebar nesta página
    
    def _render_action_bar(self) -> None:
        """Renderiza barra de ações."""
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            if st.button(
                "Atualizar lista",
                use_container_width=True,
                key="btn_refresh_profiles"
            ):
                self._state.set("perfis", [])
                st.rerun()
        
        with col2:
            if st.button(
                "Verificar sessão",
                use_container_width=True,
                key="btn_check_session"
            ):
                self._verify_session()
    
    def _verify_session(self) -> None:
        """Verifica e exibe status da sessão."""
        with st.spinner("Verificando..."):
            if self.session_service.validate_session_full():
                st.success("Sessão válida")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Sessão inválida")
                time.sleep(1)
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
    
    def _load_profiles(self) -> List[Any]:
        """Carrega lista de perfis."""
        profiles = self._state.get("perfis", [])
        
        if not profiles:
            with st.spinner("Carregando perfis..."):
                profiles = self.session_service.list_profiles()
                self._state.set("perfis", profiles)
        
        return profiles
    
    def _handle_profile_selection(self, profile: Any) -> None:
        """
        Trata seleção de perfil.
        
        Args:
            profile: Perfil selecionado
        """
        # Evitar múltiplas seleções
        if self._state.get("perfil_sendo_selecionado", False):
            return
        
        self._state.set("perfil_sendo_selecionado", True)
        
        with st.spinner(f"Selecionando {profile.nome}..."):
            if self.session_service.select_profile_by_index(profile.index):
                self._state.selected_profile = profile
                self._state.set("tarefas", [])
                self._state.set("tarefas_favoritas", [])
                self._state.set("perfil_sendo_selecionado", False)
                
                st.success(f"Perfil selecionado: {profile.nome}")
                time.sleep(0.5)
                self._navigation.go_to_main_menu()
            else:
                self._state.set("perfil_sendo_selecionado", False)
                st.error("Erro ao selecionar perfil")
    
    def _render_no_profiles_found(self) -> None:
        """Renderiza mensagem quando não há perfis."""
        st.error("Nenhum perfil encontrado")
        st.warning("Isso pode indicar que sua sessão está corrompida.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "Tentar novamente",
                type="primary",
                use_container_width=True,
                key="btn_retry_profiles"
            ):
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
        
        with col2:
            if st.button(
                "Sair",
                use_container_width=True,
                key="btn_exit_profiles"
            ):
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        # Barra de ações
        self._render_action_bar()
        
        # Carregar perfis
        profiles = self._load_profiles()
        
        if not profiles:
            self._render_no_profiles_found()
            return
        
        st.info(f"Encontrados {len(profiles)} perfil(is) disponível(is)")
        
        # Campo de busca
        search_text = st.text_input(
            "Filtrar perfis",
            placeholder="Digite para buscar...",
            key="input_filter_profiles"
        )
        
        st.markdown("---")
        
        # Verificar se está selecionando
        if self._state.get("perfil_sendo_selecionado", False):
            st.info("Selecionando perfil, aguarde...")
            return
        
        # Lista de perfis
        profile_list = ProfileList(
            profiles=profiles,
            on_select=self._handle_profile_selection,
            key_prefix="perfil",
            filter_text=search_text
        )
        profile_list.render()
        
        # Botão de sair
        st.markdown("---")
        if st.button(
            "Sair do sistema",
            use_container_width=True,
            key="btn_logout_profile"
        ):
            self.session_service.clear_session_complete()
            self._navigation.go_to_login()