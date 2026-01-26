import streamlit as st
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass

from .base import BaseComponent, ComponentConfig


@dataclass
class MetricConfig(ComponentConfig):
    """Configuração para métricas."""
    
    label: str = ""
    value: Any = 0
    delta: Optional[Union[int, float, str]] = None
    delta_color: str = "normal"  # normal, inverse, off


class MetricCard(BaseComponent):
    """
    Card de métrica individual.
    """
    
    def __init__(
        self,
        label: str,
        value: Any,
        delta: Optional[Union[int, float, str]] = None,
        delta_color: str = "normal",
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o card de métrica.
        
        Args:
            label: Label da métrica
            value: Valor a exibir
            delta: Variação (opcional)
            delta_color: Cor do delta (normal/inverse/off)
            help_text: Texto de ajuda
        """
        config = MetricConfig(
            label=label,
            value=value,
            delta=delta,
            delta_color=delta_color,
        )
        super().__init__(config)
        self._help_text = help_text
    
    def render(self) -> None:
        """Renderiza o card de métrica."""
        st.metric(
            label=self._config.label,
            value=self._config.value,
            delta=self._config.delta,
            delta_color=self._config.delta_color,
            help=self._help_text,
        )


class MetricsRow(BaseComponent):
    """
    Linha de métricas em colunas.
    """
    
    def __init__(
        self,
        metrics: List[Dict[str, Any]],
        columns: Optional[int] = None,
    ):
        """
        Inicializa a linha de métricas.
        
        Args:
            metrics: Lista de dicts com {label, value, delta?, delta_color?}
            columns: Número de colunas (None = automático)
        """
        super().__init__()
        self._metrics = metrics
        self._columns = columns or len(metrics)
    
    def render(self) -> None:
        """Renderiza a linha de métricas."""
        cols = st.columns(self._columns)
        
        for i, metric_data in enumerate(self._metrics):
            col_index = i % self._columns
            with cols[col_index]:
                metric = MetricCard(
                    label=metric_data.get("label", ""),
                    value=metric_data.get("value", 0),
                    delta=metric_data.get("delta"),
                    delta_color=metric_data.get("delta_color", "normal"),
                    help_text=metric_data.get("help_text"),
                )
                metric.render()


class ProgressMetrics(BaseComponent):
    """
    Métricas de progresso de processamento.
    """
    
    def __init__(
        self,
        total: int = 0,
        progress: int = 0,
        success: int = 0,
        files: int = 0,
        elapsed_time: Optional[str] = None,
        estimated_time: Optional[str] = None,
        success_rate: Optional[float] = None,
    ):
        """
        Inicializa as métricas de progresso.
        
        Args:
            total: Total de processos
            progress: Progresso atual
            success: Quantidade de sucesso
            files: Quantidade de arquivos
            elapsed_time: Tempo decorrido formatado
            estimated_time: Tempo estimado formatado
            success_rate: Taxa de sucesso (0-100)
        """
        super().__init__()
        self._total = total
        self._progress = progress
        self._success = success
        self._files = files
        self._elapsed_time = elapsed_time
        self._estimated_time = estimated_time
        self._success_rate = success_rate
    
    def render(self) -> None:
        """Renderiza as métricas de progresso."""
        # Primeira linha: métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", self._total)
        
        with col2:
            st.metric("Progresso", f"{self._progress}/{self._total}")
        
        with col3:
            st.metric("Sucesso", self._success)
        
        with col4:
            st.metric("Arquivos", self._files)
        
        # Segunda linha: métricas de tempo (se disponíveis)
        if any([self._elapsed_time, self._estimated_time, self._success_rate is not None]):
            cols = st.columns(3)
            
            with cols[0]:
                if self._elapsed_time:
                    st.metric("Tempo decorrido", self._elapsed_time)
            
            with cols[1]:
                if self._estimated_time:
                    st.metric("Tempo estimado", self._estimated_time)
            
            with cols[2]:
                if self._success_rate is not None:
                    st.metric("Taxa de sucesso", f"{self._success_rate:.1f}%")


class StatsSummary(BaseComponent):
    """
    Resumo estatístico de um processamento.
    """
    
    def __init__(
        self,
        report: Dict[str, Any],
    ):
        """
        Inicializa o resumo.
        
        Args:
            report: Relatório do processamento
        """
        super().__init__()
        self._report = report
    
    def render(self) -> None:
        """Renderiza o resumo estatístico."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total de processos",
                self._report.get("processos", 0)
            )
        
        with col2:
            st.metric(
                "Bem-sucedidos",
                self._report.get("sucesso", 0)
            )
        
        with col3:
            st.metric(
                "Falhas",
                self._report.get("falha", 0)
            )
        
        with col4:
            st.metric(
                "Arquivos baixados",
                len(self._report.get("arquivos", []))
            )