"""
Serviço especializado para download de processos por número.

Este serviço orquestra a busca e download de processos
quando apenas o número CNJ é fornecido.
"""

import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Generator, Set
from dataclasses import dataclass, field

from ..config import BASE_URL
from ..core import PJEHttpClient
from ..utils import delay, save_json, timestamp_str, get_logger
from .process_search_service import ProcessSearchService, ResultadoBusca
from .download_service import DownloadService


@dataclass
class ProcessoParaDownload:
    """Representa um processo para download."""
    numero_processo: str
    id_processo: int = 0
    chave_acesso: str = ""
    status: str = "pendente"  # pendente, buscando, encontrado, nao_encontrado, baixando, concluido, falha
    arquivo_baixado: Optional[str] = None
    erro: Optional[str] = None
    tentativas: int = 0


@dataclass
class RelatorioDownloadNumero:
    """Relatório de download por número."""
    tipo: str = "download_por_numero"
    diretorio: str = ""
    data_inicio: str = ""
    data_fim: str = ""
    processos: int = 0
    sucesso: int = 0
    falha: int = 0
    arquivos: List[str] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)
    status: str = "iniciando"
    processo_atual: str = ""
    progresso: int = 0
    integridade: str = "pendente"
    retries: Dict[str, Any] = field(default_factory=lambda: {
        "tentativas": 0,
        "processos_reprocessados": [],
        "processos_falha_definitiva": []
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "tipo": self.tipo,
            "diretorio": self.diretorio,
            "data_inicio": self.data_inicio,
            "data_fim": self.data_fim,
            "processos": self.processos,
            "sucesso": self.sucesso,
            "falha": self.falha,
            "arquivos": self.arquivos,
            "erros": self.erros,
            "status": self.status,
            "processo_atual": self.processo_atual,
            "progresso": self.progresso,
            "integridade": self.integridade,
            "retries": self.retries
        }


class NumberDownloadService:
    """
    Serviço para download de processos por número.
    
    Combina o serviço de busca com o serviço de download
    para fornecer uma interface simplificada.
    """
    
    def __init__(
        self,
        http_client: PJEHttpClient,
        download_service: DownloadService,
        download_dir: Path
    ):
        self.client = http_client
        self.download_service = download_service
        self.download_dir = download_dir
        self.logger = get_logger()
        
        self.search_service = ProcessSearchService(http_client)
        
        # Configurações
        self.max_retries = 2
        self.retry_delay = 5
        self.tempo_espera_download = 60
        
        # Controle de cancelamento
        self._cancelar = False
    
    def cancelar(self):
        """Solicita cancelamento do processamento."""
        self._cancelar = True
        self.logger.info("Cancelamento solicitado")
    
    def _check_cancelado(self) -> bool:
        """Verifica se foi solicitado cancelamento."""
        return self._cancelar
    
    def _reset_cancelamento(self):
        """Reseta flag de cancelamento."""
        self._cancelar = False
    
    def processar_generator(
        self,
        numeros: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa lista de números de processos com generator.
        
        Yields:
            Dict com estado atual do processamento
        
        Returns:
            Relatório final
        """
        self._reset_cancelamento()
        self.search_service.limpar_cache()
        self.download_service.limpar_diagnosticos()
        
        # Criar diretório
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        diretorio = self.download_dir / f"processos_{timestamp}"
        diretorio.mkdir(parents=True, exist_ok=True)
        
        # Inicializar relatório
        relatorio = RelatorioDownloadNumero(
            diretorio=str(diretorio),
            data_inicio=datetime.now().isoformat(),
            processos=len(numeros)
        )
        
        yield relatorio.to_dict()
        
        self.logger.section(f"PROCESSANDO {len(numeros)} PROCESSOS POR NÚMERO")
        
        if not numeros:
            relatorio.status = "concluido"
            relatorio.erros.append("Nenhum processo informado")
            yield relatorio.to_dict()
            return relatorio.to_dict()
        
        # Estrutura para controle
        processos_controle: Dict[str, ProcessoParaDownload] = {}
        for numero in numeros:
            numero_norm = self._normalizar_numero(numero)
            if numero_norm:
                processos_controle[numero_norm] = ProcessoParaDownload(
                    numero_processo=numero_norm
                )
            else:
                relatorio.erros.append(f"Número inválido: {numero}")
                relatorio.falha += 1
        
        processos_pendentes: List[str] = []
        total = len(processos_controle)
        
        relatorio.status = "processando"
        
        # Fase 1: Buscar e solicitar downloads
        for i, (numero, proc_ctrl) in enumerate(processos_controle.items(), 1):
            if self._check_cancelado():
                relatorio.status = "cancelado"
                relatorio.erros.append("Processamento cancelado pelo usuário")
                yield relatorio.to_dict()
                return relatorio.to_dict()
            
            relatorio.processo_atual = numero
            relatorio.progresso = i
            proc_ctrl.status = "buscando"
            
            self.logger.info(f"[{i}/{total}] Processando {numero}")
            yield relatorio.to_dict()
            
            # Buscar processo
            relatorio.status = "buscando_processo"
            yield relatorio.to_dict()
            
            resultado_busca = self.search_service.buscar_processo(numero)
            
            if self._check_cancelado():
                relatorio.status = "cancelado"
                yield relatorio.to_dict()
                return relatorio.to_dict()
            
            if not resultado_busca.encontrado:
                proc_ctrl.status = "nao_encontrado"
                proc_ctrl.erro = "Processo não encontrado"
                relatorio.falha += 1
                relatorio.erros.append(f"Processo não encontrado: {numero}")
                relatorio.status = "processando"
                yield relatorio.to_dict()
                continue
            
            proc_ctrl.id_processo = resultado_busca.id_processo
            proc_ctrl.chave_acesso = resultado_busca.chave_acesso
            proc_ctrl.status = "encontrado"
            
            relatorio.status = "processando"
            yield relatorio.to_dict()
            
            # Solicitar download
            proc_ctrl.status = "baixando"
            sucesso, detalhes = self.download_service.solicitar_download(
                resultado_busca.id_processo,
                numero,
                tipo_documento,
                diretorio_download=diretorio
            )
            
            if sucesso:
                if detalhes.get("arquivo_baixado"):
                    arquivo = Path(detalhes["arquivo_baixado"])
                    if self._verificar_arquivo(arquivo):
                        proc_ctrl.status = "concluido"
                        proc_ctrl.arquivo_baixado = str(arquivo)
                        relatorio.arquivos.append(str(arquivo))
                        relatorio.sucesso += 1
                        self.logger.success(f"Download concluído: {numero}")
                    else:
                        processos_pendentes.append(numero)
                else:
                    processos_pendentes.append(numero)
            else:
                proc_ctrl.status = "falha"
                proc_ctrl.erro = "Falha ao solicitar download"
                relatorio.falha += 1
                relatorio.erros.append(f"Falha ao solicitar: {numero}")
            
            yield relatorio.to_dict()
            time.sleep(2)
        
        # Fase 2: Aguardar downloads pendentes
        if self._check_cancelado():
            relatorio.status = "cancelado"
            yield relatorio.to_dict()
            return relatorio.to_dict()
        
        if aguardar_download and processos_pendentes:
            relatorio.status = "aguardando_downloads"
            relatorio.processo_atual = f"Aguardando {len(processos_pendentes)} downloads"
            yield relatorio.to_dict()
            
            arquivos = self._aguardar_e_baixar(
                processos_pendentes, 
                diretorio, 
                tempo_espera
            )
            
            for arq in arquivos:
                if arq not in relatorio.arquivos:
                    relatorio.arquivos.append(arq)
                    relatorio.sucesso += 1
                    
                    # Atualizar controle
                    num_proc = self._extrair_numero_do_arquivo(arq)
                    if num_proc and num_proc in processos_controle:
                        processos_controle[num_proc].status = "concluido"
                        processos_controle[num_proc].arquivo_baixado = arq
        
        # Fase 3: Verificar integridade
        if self._check_cancelado():
            relatorio.status = "cancelado"
            yield relatorio.to_dict()
            return relatorio.to_dict()
        
        relatorio.status = "verificando_integridade"
        relatorio.processo_atual = "Verificando arquivos"
        yield relatorio.to_dict()
        
        processos_esperados = list(processos_controle.keys())
        integridade = self._verificar_integridade(processos_esperados, diretorio)
        relatorio.integridade = integridade["integridade"]
        processos_faltantes = integridade["processos_faltantes"]
        
        # Fase 4: Retries
        tentativa = 0
        while (
            processos_faltantes 
            and tentativa < self.max_retries 
            and not self._check_cancelado()
        ):
            tentativa += 1
            relatorio.retries["tentativas"] = tentativa
            relatorio.status = f"retry_{tentativa}"
            relatorio.processo_atual = (
                f"Retry {tentativa}/{self.max_retries} - "
                f"{len(processos_faltantes)} processos"
            )
            
            self.logger.info(f"Retry {tentativa}: {len(processos_faltantes)} faltantes")
            yield relatorio.to_dict()
            
            time.sleep(self.retry_delay)
            
            for num_proc in processos_faltantes[:]:
                if self._check_cancelado():
                    break
                
                proc_ctrl = processos_controle.get(num_proc)
                if not proc_ctrl or proc_ctrl.id_processo <= 0:
                    continue
                
                relatorio.processo_atual = f"Retry: {num_proc}"
                proc_ctrl.tentativas += 1
                yield relatorio.to_dict()
                
                sucesso, _ = self.download_service.solicitar_download(
                    proc_ctrl.id_processo,
                    num_proc,
                    tipo_documento,
                    diretorio_download=diretorio
                )
                
                if sucesso:
                    relatorio.retries["processos_reprocessados"].append(num_proc)
                
                time.sleep(3)
            
            if self._check_cancelado():
                break
            
            time.sleep(15)
            arquivos_retry = self._aguardar_e_baixar(
                processos_faltantes, 
                diretorio, 
                tempo_espera=60
            )
            
            for arq in arquivos_retry:
                if arq not in relatorio.arquivos:
                    relatorio.arquivos.append(arq)
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            processos_faltantes = integridade["processos_faltantes"]
            relatorio.integridade = integridade["integridade"]
        
        if processos_faltantes:
            relatorio.retries["processos_falha_definitiva"] = processos_faltantes
        
        # Finalização
        arquivos_validos = [
            a for a in relatorio.arquivos 
            if self._verificar_arquivo(Path(a))
        ]
        relatorio.arquivos = arquivos_validos
        relatorio.sucesso = len(arquivos_validos)
        relatorio.falha = relatorio.processos - relatorio.sucesso
        relatorio.data_fim = datetime.now().isoformat()
        
        if self._check_cancelado():
            relatorio.status = "cancelado"
        elif relatorio.integridade == "ok":
            relatorio.status = "concluido"
        elif processos_faltantes:
            relatorio.status = "concluido_com_falhas"
        else:
            relatorio.status = "concluido"
        
        relatorio.processo_atual = ""
        
        # Salvar relatório
        save_json(
            relatorio.to_dict(), 
            diretorio / f"relatorio_{timestamp_str()}.json"
        )
        
        self._log_resumo(relatorio)
        
        yield relatorio.to_dict()
        return relatorio.to_dict()
    
    def processar(
        self,
        numeros: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """
        Processa lista de números (versão síncrona).
        
        Returns:
            Relatório final
        """
        relatorio = None
        for estado in self.processar_generator(
            numeros, tipo_documento, aguardar_download, tempo_espera
        ):
            relatorio = estado
        return relatorio
    
    def _normalizar_numero(self, numero: str) -> Optional[str]:
        """Normaliza número do processo."""
        return self.search_service._normalizar_numero(numero)
    
    def _verificar_arquivo(self, filepath: Path) -> bool:
        """Verifica se arquivo é válido."""
        try:
            if not filepath.exists():
                return False
            if filepath.stat().st_size == 0:
                return False
            with open(filepath, 'rb') as f:
                f.read(1)
            return True
        except Exception:
            return False
    
    def _extrair_numero_do_arquivo(self, nome_arquivo: str) -> Optional[str]:
        """Extrai número do processo do nome do arquivo."""
        import re
        match = re.match(
            r'^(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', 
            Path(nome_arquivo).name
        )
        return match.group(1) if match else None
    
    def _listar_arquivos(self, diretorio: Path) -> Set[str]:
        """Lista arquivos válidos no diretório."""
        arquivos = set()
        if not diretorio.exists():
            return arquivos
        
        for arquivo in diretorio.iterdir():
            if arquivo.is_file() and arquivo.suffix.lower() in ['.pdf', '.zip']:
                if self._verificar_arquivo(arquivo):
                    arquivos.add(arquivo.name)
        
        return arquivos
    
    def _verificar_integridade(
        self, 
        processos_esperados: List[str], 
        diretorio: Path
    ) -> Dict[str, Any]:
        """Verifica integridade dos downloads."""
        arquivos = self._listar_arquivos(diretorio)
        
        processos_baixados = set()
        for arquivo in arquivos:
            num = self._extrair_numero_do_arquivo(arquivo)
            if num:
                processos_baixados.add(num)
        
        processos_faltantes = set(processos_esperados) - processos_baixados
        
        return {
            "total_esperado": len(processos_esperados),
            "total_arquivos": len(arquivos),
            "processos_confirmados": len(processos_baixados),
            "processos_faltantes": list(processos_faltantes),
            "integridade": "ok" if not processos_faltantes else "inconsistente"
        }
    
    def _aguardar_e_baixar(
        self, 
        processos: List[str], 
        diretorio: Path,
        tempo_espera: int
    ) -> List[str]:
        """Aguarda e baixa downloads pendentes."""
        if not processos:
            return []
        
        arquivos_baixados = []
        self.logger.info(f"Verificando {len(processos)} downloads pendentes")
        
        time.sleep(5)
        
        inicio = time.time()
        processos_restantes = set(processos)
        
        while processos_restantes and (time.time() - inicio) < tempo_espera:
            if self._check_cancelado():
                break
            
            downloads = self.download_service.listar_downloads_disponiveis()
            
            for download in downloads:
                if self._check_cancelado():
                    break
                
                for num in download.get_numeros_processos():
                    if num in processos_restantes:
                        arquivo = self.download_service.baixar_arquivo(
                            download, diretorio
                        )
                        if arquivo and self._verificar_arquivo(arquivo):
                            arquivos_baixados.append(str(arquivo))
                            processos_restantes.discard(num)
            
            if processos_restantes and not self._check_cancelado():
                self.logger.info(f"Restantes: {len(processos_restantes)}")
                time.sleep(10)
        
        return arquivos_baixados
    
    def _log_resumo(self, relatorio: RelatorioDownloadNumero):
        """Exibe resumo no log."""
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio.processos}")
        self.logger.info(f"Sucesso: {relatorio.sucesso}")
        self.logger.info(f"Arquivos: {len(relatorio.arquivos)}")
        self.logger.info(f"Integridade: {relatorio.integridade}")
