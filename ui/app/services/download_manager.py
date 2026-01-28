import os
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Generator, Optional

from ..config import APP_CONFIG
from ..state.session_state import SessionStateManager
from .session_service import PJESessionService


class DownloadManagerService:
    """
    Serviço responsável pelo gerenciamento de downloads.
    """
    
    def __init__(
        self,
        state_manager: SessionStateManager,
        session_service: PJESessionService
    ):
        self._state = state_manager
        self._session = session_service
    
    @property
    def download_dir(self) -> str:
        """Retorna diretório de downloads."""
        return self._state.get("download_dir", APP_CONFIG.DOWNLOAD_DIR)
    
    def process_task_generator(
        self,
        task_name: str,
        use_favorites: bool = False,
        limit: Optional[int] = None,
        batch_size: int = 10,
        document_type: str = "Selecione",
        wait_download: bool = True,
        timeout: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """Processa downloads de uma tarefa."""
        client = self._session.client
        
        for state in client.processar_tarefa_generator(
            nome_tarefa=task_name,
            usar_favoritas=use_favorites,
            limite=limit,
            tipo_documento=document_type,
            aguardar_download=wait_download,
            tempo_espera=timeout,
            tamanho_lote=batch_size
        ):
            if self._state.is_cancellation_requested:
                client.cancelar_processamento()
            
            yield state
    
    def process_tag_generator(
        self,
        tag_name: str,
        limit: Optional[int] = None,
        batch_size: int = 10,
        document_type: str = "Selecione",
        wait_download: bool = True,
        timeout: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """Processa downloads de uma etiqueta."""
        client = self._session.client
        
        for state in client.processar_etiqueta_generator(
            nome_etiqueta=tag_name,
            limite=limit,
            tipo_documento=document_type,
            aguardar_download=wait_download,
            tempo_espera=timeout,
            tamanho_lote=batch_size
        ):
            if self._state.is_cancellation_requested:
                client.cancelar_processamento()
            
            yield state
    
    def process_numbers_generator(
        self,
        process_numbers: List[str],
        document_type: str = "Selecione",
        wait_download: bool = True,
        timeout: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """Processa downloads por números de processo."""
        client = self._session.client
        
        for state in client.processar_numeros_generator(
            numeros_processos=process_numbers,
            tipo_documento=document_type,
            aguardar_download=wait_download,
            tempo_espera=timeout
        ):
            if self._state.is_cancellation_requested:
                client.cancelar_processamento()
            
            yield state
    
    def process_subject_generator(
        self,
        subject_name: str,
        limit: Optional[int] = None,
        batch_size: int = 10,
        document_type: str = "Selecione",
        wait_download: bool = True,
        timeout: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa downloads de um assunto principal.
        
        Args:
            subject_name: Nome do assunto
            limit: Limite de processos
            batch_size: Tamanho do lote
            document_type: Tipo de documento
            wait_download: Se aguarda downloads
            timeout: Tempo máximo de espera
        
        Yields:
            Estado atual do processamento
        
        Returns:
            Relatório final
        """
        client = self._session.client
        
        for state in client.processar_assunto_generator(
            nome_assunto=subject_name,
            limite=limit,
            tipo_documento=document_type,
            aguardar_download=wait_download,
            tempo_espera=timeout,
            tamanho_lote=batch_size
        ):
            if self._state.is_cancellation_requested:
                client.cancelar_processamento()
            
            yield state
    
    def cancel_processing(self) -> None:
        """Cancela processamento atual."""
        self._state.is_cancellation_requested = True
        self._session.cancel_processing()
    
    @staticmethod
    def open_folder(path: str) -> bool:
        """Abre pasta no explorador de arquivos."""
        folder_path = Path(path)
        
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        
        try:
            system = platform.system()
            
            if system == "Windows":
                os.startfile(str(folder_path))
            elif system == "Darwin":
                subprocess.Popen(["open", str(folder_path)])
            else:
                subprocess.Popen(["xdg-open", str(folder_path)])
            
            return True
        
        except Exception:
            return False
    
    @staticmethod
    def get_report_filename() -> str:
        """Gera nome de arquivo para relatório."""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"relatorio_{timestamp}.json"