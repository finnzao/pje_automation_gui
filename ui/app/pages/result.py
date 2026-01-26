import streamlit as st
import json
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from .base import BasePage
from ..config import STATUS_CONFIG
from ..components.metrics import StatsSummary
from ..components.progress import IntegrityStatus
from ..components.lists import FileList, ErrorList
from ..components.buttons import ActionButton, NavigationButton
from ..services.download_manager import DownloadManagerService


class ResultPage(BasePage):
    """
    Página de exibição dos resultados do processamento.
    """
    
    PAGE_TITLE = "Resultado do Processamento"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _get_report(self) -> Dict[str, Any]:
        """Obtém relatório do estado."""
        return self._state.report or {}
    
    def _get_page_title(self) -> str:
        """Retorna título baseado no status."""
        report = self._get_report()
        status = report.get("status", "concluido")
        
        titles = {
            STATUS_CONFIG.CONCLUIDO: " Processamento Concluído",
            STATUS_CONFIG.CONCLUIDO_COM_FALHAS: "⚠️ Concluído com Falhas",
            STATUS_CONFIG.CANCELADO: "🛑 Processamento Cancelado",
            STATUS_CONFIG.ERRO: "❌ Erro no Processamento",
        }
        
        return titles.get(status, "Resultado do Processamento")
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho customizado."""
        st.title(self._get_page_title())
        st.markdown("---")
    
    def _render_main_metrics(self, report: Dict[str, Any]) -> None:
        """
        Renderiza métricas principais.
        
        Args:
            report: Relatório do processamento
        """
        stats = StatsSummary(report)
        stats.render()
    
    def _render_integrity_status(self, report: Dict[str, Any]) -> None:
        """
        Renderiza status de integridade.
        
        Args:
            report: Relatório do processamento
        """
        integrity = report.get("integridade", "pendente")
        retries = report.get("retries", {})
        
        integrity_component = IntegrityStatus(integrity, retries)
        integrity_component.render()
    
    def _render_errors(self, report: Dict[str, Any]) -> None:
        """
        Renderiza lista de erros.
        
        Args:
            report: Relatório do processamento
        """
        errors = report.get("erros", [])
        
        if errors:
            error_list = ErrorList(errors)
            error_list.render()
    
    def _render_failed_processes(self, report: Dict[str, Any]) -> None:
        """
        Renderiza lista de processos com falha definitiva.
        
        Args:
            report: Relatório do processamento
        """
        retries = report.get("retries", {})
        failed = retries.get("processos_falha_definitiva", [])
        
        if failed:
            with st.expander(f"Processos com falha definitiva ({len(failed)})"):
                for proc in failed:
                    st.code(proc)
    
    def _render_downloaded_files(self, report: Dict[str, Any]) -> None:
        """
        Renderiza lista de arquivos baixados.
        
        Args:
            report: Relatório do processamento
        """
        files = report.get("arquivos", [])
        
        if files:
            file_list = FileList(files)
            file_list.render()
    
    def _render_directory_info(self, report: Dict[str, Any]) -> None:
        """
        Renderiza informações do diretório.
        
        Args:
            report: Relatório do processamento
        """
        directory = report.get(
            "diretorio",
            self._state.get("download_dir", "./downloads")
        )
        
        st.text(f"📁 Diretório de download: {directory}")
    
    def _render_action_buttons(self, report: Dict[str, Any]) -> None:
        """
        Renderiza botões de ação.
        
        Args:
            report: Relatório do processamento
        """
        directory = report.get(
            "diretorio",
            self._state.get("download_dir", "./downloads")
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "📂 Abrir pasta de downloads",
                use_container_width=True,
                type="primary",
                key="btn_open_result"
            ):
                DownloadManagerService.open_folder(directory)
        
        with col2:
            # Preparar dados do relatório para download
            report_json = json.dumps(report, ensure_ascii=False, indent=2)
            filename = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            st.download_button(
                "📥 Baixar relatório (JSON)",
                data=report_json,
                file_name=filename,
                mime="application/json",
                use_container_width=True,
                key="btn_download_report"
            )
    
    def _render_navigation_buttons(self) -> None:
        """Renderiza botões de navegação."""
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "🔄 Novo download",
                use_container_width=True,
                type="primary",
                key="btn_new_download"
            ):
                self._state.report = None
                self._navigation.go_to_main_menu()
        
        with col2:
            if st.button(
                "🚪 Sair do sistema",
                use_container_width=True,
                key="btn_logout_result"
            ):
                self.session_service.clear_session_complete()
                self._navigation.go_to_login()
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página de resultado."""
        report = self._get_report()
        
        if not report:
            st.warning("Nenhum relatório disponível")
            self._navigation.go_to_main_menu()
            return
        
        # Métricas principais
        self._render_main_metrics(report)
        
        # Status de integridade
        self._render_integrity_status(report)
        
        # Erros (se houver)
        self._render_errors(report)
        
        st.markdown("---")
        
        # Informações do diretório
        self._render_directory_info(report)
        
        # Botões de ação
        self._render_action_buttons(report)
        
        # Detalhes adicionais
        st.markdown("---")
        
        # Processos com falha
        self._render_failed_processes(report)
        
        # Arquivos baixados
        self._render_downloaded_files(report)
        
        st.markdown("---")
        
        # Navegação
        self._render_navigation_buttons()