import streamlit as st
import time
from typing import Dict, Any, Generator, Optional
from abc import abstractmethod

from .base import BasePage, ProcessingPageBase
from ..config import PAGE_CONFIG, STATUS_CONFIG
from ..components.progress import (
    ProgressBar,
    ProcessingStatus,
    TimeEstimate,
    ProcessingContainer,
)
from ..components.buttons import CancelButton, ConfirmationDialog
from ..components.metrics import MetricsRow


class BaseProcessingPage(ProcessingPageBase):
    """
    Classe base para todas as páginas de processamento.
    
    Implementa a lógica comum de:
    - Exibição de progresso
    - Métricas em tempo real
    - Controle de cancelamento
    - Transição para resultado
    """
    
    def _render_sidebar(self) -> None:
        """Sem sidebar nas páginas de processamento."""
        pass
    
    def _render_cancel_controls(self, key_prefix: str, iteration: int) -> None:
        """
        Renderiza controles de cancelamento.
        
        Args:
            key_prefix: Prefixo para chaves únicas
            iteration: Iteração atual (para chaves únicas)
        """
        if self._state.is_cancellation_requested:
            st.error("Cancelamento solicitado. Aguarde a interrupção...")
        
        elif self._state.get("show_cancel_confirm", False):
            st.warning("Confirmar cancelamento?")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(
                    "Sim, cancelar",
                    type="primary",
                    use_container_width=True,
                    key=f"{key_prefix}_confirm_cancel_{iteration}"
                ):
                    self._handle_cancel_confirm()
            
            with col2:
                if st.button(
                    "Não, continuar",
                    use_container_width=True,
                    key=f"{key_prefix}_deny_cancel_{iteration}"
                ):
                    self._handle_cancel_deny()
        
        else:
            if st.button(
                "Cancelar processamento",
                use_container_width=True,
                key=f"{key_prefix}_request_cancel_{iteration}"
            ):
                self._handle_cancel_request()
    
    def _render_processing_ui(
        self,
        state: Dict[str, Any],
        start_time: float,
        key_prefix: str,
        iteration: int
    ) -> None:
        """
        Renderiza a interface de processamento.
        
        Args:
            state: Estado atual do processamento
            start_time: Timestamp de início
            key_prefix: Prefixo para chaves
            iteration: Iteração atual
        """
        status = state.get("status", "")
        progress = state.get("progresso", 0)
        total = state.get("processos", 0)
        current_process = state.get("processo_atual", "")
        success = state.get("sucesso", 0)
        files_count = len(state.get("arquivos", []))
        
        # Status
        status_component = ProcessingStatus(status, current_process)
        status_component.render()
        
        # Barra de progresso
        progress_value = progress / total if total > 0 else 0
        st.progress(progress_value)
        
        # Processo atual
        if current_process:
            st.caption(f"Processando: {current_process}")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("Progresso", f"{progress}/{total}")
        with col3:
            st.metric("Sucesso", success)
        with col4:
            st.metric("Arquivos", files_count)
        
        st.markdown("---")
        
        # Métricas de tempo
        elapsed_seconds = int(time.time() - start_time)
        mins, secs = divmod(elapsed_seconds, 60)
        
        cols = st.columns(3)
        
        with cols[0]:
            st.metric("Tempo decorrido", f"{mins}m {secs}s")
        
        with cols[1]:
            if progress > 0 and total > 0:
                time_per_process = elapsed_seconds / progress
                remaining = int((total - progress) * time_per_process)
                mins_rest, secs_rest = divmod(remaining, 60)
                st.metric("Tempo estimado", f"{mins_rest}m {secs_rest}s")
            else:
                st.metric("Tempo estimado", "-")
        
        with cols[2]:
            success_rate = (success / progress * 100) if progress > 0 else 0
            st.metric("Taxa de sucesso", f"{success_rate:.1f}%")
        
        st.markdown("---")
        
        # Controles de cancelamento
        self._render_cancel_controls(key_prefix, iteration)
    
    def _run_processing_loop(
        self,
        generator: Generator[Dict[str, Any], None, Dict[str, Any]],
        key_prefix: str
    ) -> None:
        """
        Executa o loop de processamento.
        
        Args:
            generator: Generator que produz estados
            key_prefix: Prefixo para chaves únicas
        """
        start_time = time.time()
        iteration = 0
        
        # Containers para atualização
        status_container = st.empty()
        
        try:
            for state in generator:
                iteration += 1
                status = state.get("status", "")
                
                # Renderizar UI
                with status_container.container():
                    self._render_processing_ui(
                        state,
                        start_time,
                        key_prefix,
                        iteration
                    )
                
                # Verificar se terminou
                if STATUS_CONFIG.is_final_status(status):
                    self._state.report = state
                    self._state.reset_processing_state()
                    time.sleep(0.5)
                    self._navigation.go_to_result(state)
                    break
                
                # Pequeno delay para atualização da UI
                time.sleep(0.05)
        
        except InterruptedError:
            st.error("Processamento cancelado")
            time.sleep(1)
            self._state.reset_processing_state()
            self._navigation.navigate_to(self._get_back_page())
        
        except Exception as e:
            st.error(f"Erro durante processamento: {str(e)}")
            
            if st.button("Voltar", key=f"{key_prefix}_back_error"):
                self._navigation.navigate_to(self._get_back_page())


class ProcessingTaskPage(BaseProcessingPage):
    """
    Página de processamento de download por tarefa.
    """
    
    PAGE_TITLE = "Processando Tarefa"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_TASK
    
    def _validate_params(self) -> bool:
        """Valida se há tarefa selecionada."""
        task = self._state.get("selected_task")
        return task is not None
    
    def _get_generator(self):
        """Retorna generator de processamento de tarefa."""
        task = self._state.get("selected_task")
        limit = self._state.get("task_limit")
        use_favorites = self._state.get("task_usar_favoritas", False)
        batch_size = self._state.get("task_tamanho_lote", 10)
        
        return self.download_manager.process_task_generator(
            task_name=task.nome,
            use_favorites=use_favorites,
            limit=limit,
            batch_size=batch_size,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com nome da tarefa."""
        task = self._state.get("selected_task")
        task_name = task.nome if task else "Desconhecida"
        
        st.title(f"Processando: {task_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        if not self._validate_params():
            st.error("Nenhuma tarefa selecionada")
            self._navigation.go_to_download_by_task()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "task")


class ProcessingTagPage(BaseProcessingPage):
    """
    Página de processamento de download por etiqueta.
    """
    
    PAGE_TITLE = "Processando Etiqueta"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_TAG
    
    def _validate_params(self) -> bool:
        """Valida se há etiqueta selecionada."""
        tag = self._state.get("selected_tag")
        return tag is not None
    
    def _get_generator(self):
        """Retorna generator de processamento de etiqueta."""
        tag = self._state.get("selected_tag")
        limit = self._state.get("tag_limit")
        batch_size = self._state.get("tag_tamanho_lote", 10)
        
        return self.download_manager.process_tag_generator(
            tag_name=tag.nome,
            limit=limit,
            batch_size=batch_size,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com nome da etiqueta."""
        tag = self._state.get("selected_tag")
        tag_name = tag.nome if tag else "Desconhecida"
        
        st.title(f"Processando: {tag_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        if not self._validate_params():
            st.error("Nenhuma etiqueta selecionada")
            self._navigation.go_to_download_by_tag()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "tag")


class ProcessingNumberPage(BaseProcessingPage):
    """
    Página de processamento de download por número.
    """
    
    PAGE_TITLE = "Processando Processos"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_NUMBER
    
    def _validate_params(self) -> bool:
        """Valida se há processos para baixar."""
        processes = self._state.get("processos_para_baixar", [])
        return len(processes) > 0
    
    def _get_generator(self):
        """Retorna generator de processamento por número."""
        processes = self._state.get("processos_para_baixar", [])
        document_type = self._state.get("tipo_documento_numero", "Selecione")
        
        return self.download_manager.process_numbers_generator(
            process_numbers=processes,
            document_type=document_type,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com quantidade de processos."""
        processes = self._state.get("processos_para_baixar", [])
        count = len(processes)
        
        st.title(f"Processando {count} processo(s)")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        if not self._validate_params():
            st.error("Nenhum processo para baixar")
            self._navigation.go_to_download_by_number()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "number")