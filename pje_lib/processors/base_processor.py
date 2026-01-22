"""
Classe base para processadores de download.
"""

import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set, Optional, Generator
from abc import ABC, abstractmethod

from ..utils import get_logger, save_json, timestamp_str


class BaseProcessor(ABC):
    """
    Classe base para todos os processadores de download.
    
    Fornece infraestrutura comum:
    - Controle de cancelamento thread-safe
    - Verificação de integridade
    - Gestão de relatórios
    - Retry automático
    """
    
    def __init__(
        self,
        download_service,
        download_dir: Path,
        max_retries: int = 2,
        retry_delay: int = 5
    ):
        self.download_service = download_service
        self.download_dir = download_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.logger = get_logger()
        
        # Controle de cancelamento thread-safe
        self._cancelamento_lock = threading.Lock()
        self._cancelar = False
        self._operacao_atual: Optional[str] = None
    
    # ==================== CANCELAMENTO ====================
    
    def cancelar(self):
        """Solicita cancelamento thread-safe."""
        with self._cancelamento_lock:
            self._cancelar = True
            self._operacao_atual = "cancelada"
            self.logger.warning("🛑 CANCELAMENTO SOLICITADO")
    
    def _reset_cancelamento(self):
        """Reseta flag de cancelamento."""
        with self._cancelamento_lock:
            self._cancelar = False
            self._operacao_atual = None
    
    def _check_cancelado(self) -> bool:
        """Verifica se foi cancelado (thread-safe)."""
        with self._cancelamento_lock:
            return self._cancelar
    
    def _check_cancelado_raise(self, operacao: str = ""):
        """
        Verifica cancelamento e lança exceção se cancelado.
        Útil para interromper loops profundos.
        """
        if self._check_cancelado():
            msg = f"Operação cancelada: {operacao}" if operacao else "Operação cancelada"
            raise InterruptedError(msg)
    
    # ==================== VERIFICAÇÃO DE ARQUIVOS ====================
    
    def _verificar_arquivo_valido(self, filepath: Path) -> bool:
        """Verifica se arquivo existe e é válido."""
        try:
            if not filepath.exists():
                return False
            if filepath.stat().st_size == 0:
                return False
            # Tentar ler primeiro byte
            with open(filepath, 'rb') as f:
                f.read(1)
            return True
        except Exception:
            return False
    
    def _listar_arquivos_diretorio(self, diretorio: Path) -> Set[str]:
        """Lista arquivos válidos no diretório."""
        arquivos = set()
        if not diretorio.exists():
            return arquivos
        
        for arquivo in diretorio.iterdir():
            if arquivo.is_file() and arquivo.suffix.lower() in ['.pdf', '.zip']:
                if self._verificar_arquivo_valido(arquivo):
                    arquivos.add(arquivo.name)
        
        return arquivos
    
    def _extrair_numero_processo_arquivo(self, nome_arquivo: str) -> Optional[str]:
        """Extrai número do processo do nome do arquivo."""
        import re
        match = re.match(r'^(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', nome_arquivo)
        if match:
            return match.group(1)
        return None
    
    def _verificar_integridade(
        self,
        processos_esperados: List[str],
        diretorio: Path
    ) -> Dict[str, Any]:
        """
        Verifica integridade dos downloads.
        
        Returns:
            Dict com informações de integridade
        """
        arquivos_disco = self._listar_arquivos_diretorio(diretorio)
        
        processos_baixados = set()
        for arquivo in arquivos_disco:
            num_proc = self._extrair_numero_processo_arquivo(arquivo)
            if num_proc:
                processos_baixados.add(num_proc)
        
        processos_esperados_set = set(processos_esperados)
        processos_faltantes = processos_esperados_set - processos_baixados
        
        return {
            "total_esperado": len(processos_esperados),
            "total_arquivos": len(arquivos_disco),
            "processos_confirmados": len(processos_baixados),
            "processos_faltantes": list(processos_faltantes),
            "integridade": "ok" if not processos_faltantes else "inconsistente"
        }
    
    # ==================== DOWNLOAD PENDENTES ====================
    
    def _baixar_pendentes_verificado(
        self,
        processos: List[str],
        diretorio: Path,
        tempo_espera: int = 60
    ) -> List[str]:
        """
        Aguarda e baixa processos pendentes.
        
        Args:
            processos: Lista de números de processos
            diretorio: Diretório de destino
            tempo_espera: Tempo máximo de espera em segundos
        
        Returns:
            Lista de caminhos de arquivos baixados
        """
        if not processos:
            return []
        
        arquivos_baixados = []
        self.logger.info(f"Verificando {len(processos)} downloads pendentes")
        
        time.sleep(5)
        
        inicio = time.time()
        processos_restantes = set(processos)
        
        while processos_restantes and (time.time() - inicio) < tempo_espera:
            # Verificar cancelamento
            if self._check_cancelado():
                self.logger.info("Download pendente cancelado")
                break
            
            downloads = self.download_service.listar_downloads_disponiveis()
            
            for download in downloads:
                if self._check_cancelado():
                    break
                
                numeros = download.get_numeros_processos()
                for num in numeros:
                    if num in processos_restantes:
                        arquivo = self.download_service.baixar_arquivo(download, diretorio)
                        if arquivo and self._verificar_arquivo_valido(arquivo):
                            arquivos_baixados.append(str(arquivo))
                            processos_restantes.discard(num)
            
            if processos_restantes and not self._check_cancelado():
                self.logger.info(f"Restantes: {len(processos_restantes)}")
                time.sleep(10)
        
        return arquivos_baixados
    
    # ==================== RETRY ====================
    
    def _executar_retries(
        self,
        processos_faltantes: List[str],
        mapa_processos: Dict[str, Any],
        diretorio: Path,
        tipo_documento: str,
        relatorio: Dict[str, Any]
    ) -> List[str]:
        """
        Executa tentativas de retry para processos faltantes.
        
        Args:
            processos_faltantes: Lista de processos que falharam
            mapa_processos: Mapeamento número -> dados do processo
            diretorio: Diretório de downloads
            tipo_documento: Tipo de documento
            relatorio: Relatório para atualizar
        
        Returns:
            Lista de processos que ainda falharam após retries
        """
        tentativa = 0
        
        while processos_faltantes and tentativa < self.max_retries:
            # Verificar cancelamento
            if self._check_cancelado():
                break
            
            tentativa += 1
            relatorio["retries"]["tentativas"] = tentativa
            
            self.logger.info(
                f"Retry {tentativa}/{self.max_retries}: "
                f"{len(processos_faltantes)} processos faltantes"
            )
            
            time.sleep(self.retry_delay)
            
            # Reprocessar cada processo faltante
            for num_proc in processos_faltantes[:]:
                if self._check_cancelado():
                    break
                
                if num_proc not in mapa_processos:
                    continue
                
                proc = mapa_processos[num_proc]
                id_processo = proc.get("id_processo", 0)
                
                if id_processo <= 0:
                    continue
                
                self.logger.debug(f"Retry: {num_proc}")
                
                sucesso, _ = self.download_service.solicitar_download(
                    id_processo,
                    num_proc,
                    tipo_documento,
                    diretorio_download=diretorio
                )
                
                if sucesso:
                    relatorio["retries"]["processos_reprocessados"].append(num_proc)
                
                time.sleep(3)
            
            if self._check_cancelado():
                break
            
            # Aguardar downloads dos retries
            time.sleep(15)
            arquivos_retry = self._baixar_pendentes_verificado(
                processos_faltantes,
                diretorio,
                tempo_espera=60
            )
            
            # Atualizar arquivos no relatório
            for arq in arquivos_retry:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
            
            # Verificar integridade novamente
            processos_esperados = list(mapa_processos.keys())
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            processos_faltantes = integridade["processos_faltantes"]
            relatorio["integridade"] = integridade["integridade"]
        
        return processos_faltantes
    
    # ==================== RELATÓRIO ====================
    
    def _criar_relatorio_base(
        self,
        tipo: str,
        diretorio: Path,
        total_processos: int
    ) -> Dict[str, Any]:
        """Cria estrutura base de relatório."""
        return {
            "tipo": tipo,
            "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": total_processos,
            "sucesso": 0,
            "falha": 0,
            "arquivos": [],
            "erros": [],
            "status": "iniciando",
            "processo_atual": "",
            "progresso": 0,
            "integridade": "pendente",
            "retries": {
                "tentativas": 0,
                "processos_reprocessados": [],
                "processos_falha_definitiva": []
            }
        }
    
    def _finalizar_relatorio(
        self,
        relatorio: Dict[str, Any],
        diretorio: Path,
        processos_esperados: List[str],
        cancelado: bool = False
    ) -> Dict[str, Any]:
        """Finaliza relatório com informações finais."""
        # Validar arquivos
        arquivos_validos = [
            a for a in relatorio["arquivos"]
            if self._verificar_arquivo_valido(Path(a))
        ]
        
        relatorio["arquivos"] = arquivos_validos
        relatorio["sucesso"] = len(arquivos_validos)
        relatorio["falha"] = relatorio["processos"] - relatorio["sucesso"]
        relatorio["data_fim"] = datetime.now().isoformat()
        relatorio["processo_atual"] = ""
        
        # Determinar status final
        if cancelado:
            relatorio["status"] = "cancelado"
        elif relatorio["integridade"] == "ok":
            relatorio["status"] = "concluido"
        elif relatorio["retries"]["processos_falha_definitiva"]:
            relatorio["status"] = "concluido_com_falhas"
        else:
            relatorio["status"] = "concluido"
        
        # Salvar relatório
        sufixo = "cancelado" if cancelado else timestamp_str()
        save_json(relatorio, diretorio / f"relatorio_{sufixo}.json")
        
        # Log resumo
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        self.logger.info(f"Integridade: {relatorio['integridade']}")
        
        return relatorio
    
    # ==================== MÉTODO ABSTRATO ====================
    
    @abstractmethod
    def processar_generator(self, **kwargs) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Método abstrato para processamento.
        Deve ser implementado pelas subclasses.
        """
        pass
    
    def processar(self, **kwargs) -> Dict[str, Any]:
        """
        Versão síncrona do processamento.
        Executa o generator até o final.
        """
        relatorio = None
        for estado in self.processar_generator(**kwargs):
            relatorio = estado
        return relatorio
