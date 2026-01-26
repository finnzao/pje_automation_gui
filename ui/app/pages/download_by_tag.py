import streamlit as st
from typing import List, Any, Optional

from .base import BasePage
from ..config import APP_CONFIG
from ..components.forms import SearchInput, NumberInput, Slider
from ..components.buttons import NavigationButton
from ..components.lists import TagList


class DownloadByTagPage(BasePage):
    """
    Página para download de processos por etiqueta.
    """
    
    PAGE_TITLE = "Download por Etiqueta"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _render_sidebar(self) -> None:
        """Renderiza sidebar com configurações."""
        with st.sidebar:
            st.header("Configurações")
            
            # Limite de processos
            self._limit = st.number_input(
                "Limite de processos (0 = todos)",
                min_value=0,
                max_value=APP_CONFIG.MAX_PROCESSES_LIMIT,
                value=0,
                key="input_limite_tag"
            )
            
            # Tamanho do lote
            self._batch_size = st.slider(
                "Tamanho do lote de download",
                min_value=APP_CONFIG.MIN_BATCH_SIZE,
                max_value=APP_CONFIG.MAX_BATCH_SIZE,
                value=APP_CONFIG.DEFAULT_BATCH_SIZE,
                key="slider_lote_tag"
            )
            
            st.markdown("---")
            
            # Botão voltar
            if st.button(
                "Voltar ao menu",
                use_container_width=True,
                key="btn_back_tag"
            ):
                self._navigation.go_to_main_menu()
    
    def _search_tags(self, query: str) -> List[Any]:
        """
        Busca etiquetas.
        
        Args:
            query: Termo de busca
        
        Returns:
            Lista de etiquetas (sem duplicatas)
        """
        with st.spinner("Buscando etiquetas..."):
            tags = self.session_service.search_tags(query)
        
        # Remover duplicadas
        unique_tags = []
        seen_ids = set()
        
        for tag in tags:
            if tag.id not in seen_ids:
                unique_tags.append(tag)
                seen_ids.add(tag.id)
        
        return unique_tags
    
    def _handle_tag_selection(self, tag: Any) -> None:
        """
        Trata seleção de etiqueta para download.
        
        Args:
            tag: Etiqueta selecionada
        """
        limit = self._limit if self._limit > 0 else None
        
        self._navigation.go_to_processing_tag(
            tag=tag,
            limit=limit,
            batch_size=self._batch_size
        )
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        # Inicializar variáveis da sidebar
        self._limit = 0
        self._batch_size = APP_CONFIG.DEFAULT_BATCH_SIZE
        
        # Campo de busca
        search_query = st.text_input(
            "Nome da etiqueta",
            placeholder="Digite o nome da etiqueta...",
            key="input_search_tag"
        )
        
        if search_query:
            # Buscar etiquetas
            tags = self._search_tags(search_query)
            
            if tags:
                st.info(f"Encontradas {len(tags)} etiqueta(s)")
                st.markdown("---")
                
                # Lista de etiquetas
                tag_list = TagList(
                    tags=tags,
                    on_select=self._handle_tag_selection,
                    key_prefix="etiqueta",
                    action_label="Baixar"
                )
                tag_list.render()
            else:
                st.warning(f"Nenhuma etiqueta encontrada para: '{search_query}'")
        else:
            st.info("Digite o nome de uma etiqueta para buscar")