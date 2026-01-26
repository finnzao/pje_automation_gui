import streamlit as st
from typing import List, Any, Optional

from .base import BasePage
from ..config import APP_CONFIG
from ..components.forms import SearchInput, NumberInput, Slider, Checkbox
from ..components.buttons import NavigationButton
from ..components.lists import TaskList


class DownloadByTaskPage(BasePage):
    """
    Página para download de processos por tarefa.
    """
    
    PAGE_TITLE = "Download por Tarefa"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _render_sidebar(self) -> None:
        """Renderiza sidebar com configurações."""
        with st.sidebar:
            st.header("Configurações")
            
            # Checkbox para favoritas
            self._use_favorites = st.checkbox(
                "Apenas tarefas favoritas",
                key="chk_favoritas"
            )
            
            # Limite de processos
            self._limit = st.number_input(
                "Limite de processos (0 = todos)",
                min_value=0,
                max_value=APP_CONFIG.MAX_PROCESSES_LIMIT,
                value=0,
                key="input_limite_task"
            )
            
            # Tamanho do lote
            self._batch_size = st.slider(
                "Tamanho do lote de download",
                min_value=APP_CONFIG.MIN_BATCH_SIZE,
                max_value=APP_CONFIG.MAX_BATCH_SIZE,
                value=APP_CONFIG.DEFAULT_BATCH_SIZE,
                key="slider_lote_task"
            )
            
            st.markdown("---")
            
            # Botão atualizar
            if st.button(
                "Atualizar lista de tarefas",
                use_container_width=True,
                key="btn_refresh_tasks"
            ):
                self._state.set("tarefas", [])
                self._state.set("tarefas_favoritas", [])
                st.rerun()
            
            st.markdown("---")
            
            # Botão voltar
            if st.button(
                "Voltar ao menu",
                use_container_width=True,
                key="btn_back_task"
            ):
                self._navigation.go_to_main_menu()
    
    def _load_tasks(self) -> List[Any]:
        """
        Carrega lista de tarefas.
        
        Returns:
            Lista de tarefas
        """
        if self._use_favorites:
            tasks = self._state.get("tarefas_favoritas", [])
            if not tasks:
                with st.spinner("Carregando tarefas favoritas..."):
                    tasks = self.session_service.list_favorite_tasks(force_refresh=True)
                    self._state.set("tarefas_favoritas", tasks)
        else:
            tasks = self._state.get("tarefas", [])
            if not tasks:
                with st.spinner("Carregando tarefas..."):
                    tasks = self.session_service.list_tasks(force_refresh=True)
                    self._state.set("tarefas", tasks)
        
        return tasks
    
    def _handle_task_selection(self, task: Any) -> None:
        """
        Trata seleção de tarefa para download.
        
        Args:
            task: Tarefa selecionada
        """
        limit = self._limit if self._limit > 0 else None
        
        self._navigation.go_to_processing_task(
            task=task,
            limit=limit,
            use_favorites=self._use_favorites,
            batch_size=self._batch_size
        )
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        # Inicializar variáveis da sidebar
        self._use_favorites = self._state.get("chk_favoritas", False)
        self._limit = 0
        self._batch_size = APP_CONFIG.DEFAULT_BATCH_SIZE
        
        # Carregar tarefas
        tasks = self._load_tasks()
        
        if not tasks:
            st.warning("Nenhuma tarefa encontrada para este perfil")
            return
        
        st.info(f"Total: {len(tasks)} tarefa(s)")
        
        # Campo de busca
        search_text = st.text_input(
            "Filtrar tarefas",
            placeholder="Digite para buscar...",
            key="input_filter_tasks"
        )
        
        st.markdown("---")
        
        # Lista de tarefas
        task_list = TaskList(
            tasks=tasks,
            on_select=self._handle_task_selection,
            key_prefix="tarefa",
            filter_text=search_text,
            action_label="Baixar"
        )
        task_list.render()