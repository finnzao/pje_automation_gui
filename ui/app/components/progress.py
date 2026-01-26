import streamlit as st
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .base import BaseComponent
from ..styles.css import StyleManager


class ProgressBar(BaseComponent):
    """
    Barra de progresso.
    """
    
    def __init__(
        self,
        progress: float = 0.0,
        text: Optional[str] = None,
    ):
        """
        Inicializa a barra de progresso.
        
        Args:
            progress: Progresso (0.0 a 1.0)
            text: Texto opcional
        """
        super().__init__()
        self._progress = min(max(progress, 0.0), 1.0)
        self._text = text
    
    def render(self) -> None:
        """Renderiza a barra de progresso."""
        if self._text:
            st.caption(self._text)
        st.progress(self._progress)
    
    def update(self, progress: float, text: Optional[str] = None) -> None:
        """
        Atualiza o progresso.
        
        Args:
            progress: Novo progresso
            text: Novo texto
        """
        self._progress = min(max(progress, 0.0), 1.0)
        if text is not None:
            self._text = text


class ProcessingStatus(BaseComponent):
    """
    Componente de status de processamento.
    Exibe badge de status e processo atual.
    """
    
    def __init__(
        self,
        status: str = "",
        current_process: str = "",
    ):
        """
        Inicializa o status.
        
        Args:
            status: Status atual
            current_process: Processo atual sendo processado
        """
        super().__init__()
        self._status = status
        self._current_process = current_process
    
    def render(self) -> None:
        """Renderiza o status."""
        # Badge de status
        badge_html = StyleManager.get_status_badge_for_processing(self._status)
        st.markdown(badge_html, unsafe_allow_html=True)
        
        # Processo atual
        if self._current_process:
            st.caption(f"Processando: {self._current_process}")
    
    def update(self, status: str, current_process: str = "") -> None:
        """
        Atualiza o status.
        
        Args:
            status: Novo status
            current_process: Novo processo atual
        """
        self._status = status
        self._current_process = current_process


class TimeEstimate(BaseComponent):
    """
    Componente de estimativa de tempo.
    """
    
    def __init__(
        self,
        start_time: float,
        progress: int,
        total: int,
    ):
        """
        Inicializa o estimador de tempo.
        
        Args:
            start_time: Timestamp de início
            progress: Progresso atual
            total: Total de itens
        """
        super().__init__()
        self._start_time = start_time
        self._progress = progress
        self._total = total
    
    @staticmethod
    def format_time(seconds: int) -> str:
        """
        Formata segundos em string legível.
        
        Args:
            seconds: Segundos
        
        Returns:
            String formatada (ex: "5m 30s")
        """
        mins, secs = divmod(seconds, 60)
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"
    
    def get_elapsed_time(self) -> int:
        """Retorna tempo decorrido em segundos."""
        return int(time.time() - self._start_time)
    
    def get_estimated_remaining(self) -> Optional[int]:
        """Retorna tempo restante estimado em segundos."""
        if self._progress <= 0 or self._total <= 0:
            return None
        
        elapsed = self.get_elapsed_time()
        time_per_item = elapsed / self._progress
        remaining_items = self._total - self._progress
        
        return int(remaining_items * time_per_item)
    
    def get_success_rate(self, success_count: int) -> float:
        """
        Calcula taxa de sucesso.
        
        Args:
            success_count: Quantidade de sucesso
        
        Returns:
            Taxa de sucesso (0-100)
        """
        if self._progress <= 0:
            return 0.0
        return (success_count / self._progress) * 100
    
    def render(self) -> None:
        """Renderiza as estimativas de tempo."""
        cols = st.columns(3)
        
        elapsed = self.get_elapsed_time()
        remaining = self.get_estimated_remaining()
        
        with cols[0]:
            st.metric("Tempo decorrido", self.format_time(elapsed))
        
        with cols[1]:
            if remaining is not None:
                st.metric("Tempo estimado", self.format_time(remaining))
            else:
                st.metric("Tempo estimado", "-")
        
        with cols[2]:
            if self._progress > 0:
                rate = (self._progress / self._total) * 100 if self._total > 0 else 0
                st.metric("Conclusão", f"{rate:.1f}%")


class ProcessingContainer(BaseComponent):
    """
    Container completo de processamento.
    Agrupa status, progresso, métricas e controles.
    """
    
    def __init__(
        self,
        state: Dict[str, Any],
        start_time: float,
        on_cancel: Optional[callable] = None,
        key_prefix: str = "processing",
    ):
        """
        Inicializa o container.
        
        Args:
            state: Estado atual do processamento
            start_time: Timestamp de início
            on_cancel: Callback de cancelamento
            key_prefix: Prefixo para chaves
        """
        super().__init__()
        self._state = state
        self._start_time = start_time
        self._on_cancel = on_cancel
        self._key_prefix = key_prefix
    
    def render(self) -> None:
        """Renderiza o container de processamento."""
        status = self._state.get("status", "")
        progress = self._state.get("progresso", 0)
        total = self._state.get("processos", 0)
        current = self._state.get("processo_atual", "")
        success = self._state.get("sucesso", 0)
        files = len(self._state.get("arquivos", []))
        
        # Status
        status_component = ProcessingStatus(status, current)
        status_component.render()
        
        # Barra de progresso
        progress_value = progress / total if total > 0 else 0
        progress_bar = ProgressBar(progress_value)
        progress_bar.render()
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("Progresso", f"{progress}/{total}")
        with col3:
            st.metric("Sucesso", success)
        with col4:
            st.metric("Arquivos", files)
        
        st.markdown("---")
        
        # Estimativas de tempo
        time_estimate = TimeEstimate(self._start_time, progress, total)
        time_estimate.render()


class IntegrityStatus(BaseComponent):
    """
    Componente de status de integridade.
    """
    
    def __init__(
        self,
        integrity: str,
        retries: Optional[Dict[str, Any]] = None,
    ):
        """
        Inicializa o status de integridade.
        
        Args:
            integrity: Status de integridade
            retries: Informações de retries
        """
        super().__init__()
        self._integrity = integrity
        self._retries = retries or {}
    
    def render(self) -> None:
        """Renderiza o status de integridade."""
        if self._integrity == "ok":
            st.success(
                "Integridade verificada: Todos os arquivos foram baixados corretamente"
            )
        elif self._integrity == "inconsistente":
            failures = self._retries.get("processos_falha_definitiva", [])
            st.warning(
                f"Integridade inconsistente: {len(failures)} arquivo(s) "
                "não puderam ser baixados"
            )
        else:
            st.info(f"Status de integridade: {self._integrity}")