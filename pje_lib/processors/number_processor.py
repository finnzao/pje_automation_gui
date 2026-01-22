"""
Processador para download de processos por número.
"""

import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .base_processor import BaseProcessor
from ..utils import normalizar_nome_pasta


class NumberProcessor(BaseProcessor):
    """
    Processador especializado para downloads por número de processo.
    
    Implementa:
    - Busca de processos por número
    - Download com timeout
    - Validação de números CNJ
    """
    
    def __init__(
        self,
        download_service,
        search_service,
        download_dir: Path,
        max_retries: int = 2,
        retry_delay: int = 5,
        search_timeout: int = 30
    ):
        super().__init__(download_service, download_dir, max_retries, retry_delay)
        self.search_service = search_service
        self.search_timeout = search_timeout
    
    def _normalizar_numero(self, numero: str) -> Optional[str]:
        """
        Normaliza número do processo para formato CNJ.
        
        Aceita:
        - NNNNNNN-DD.AAAA.J.TR.OOOO (formatado)
        - NNNNNNNDDAAAAJTROOOO (apenas números)
        
        Retorna: NNNNNNN-DD.AAAA.J.TR.OOOO
        """
        numero = numero.strip()
        
        # Se já está formatado
        if re.match(r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$', numero):
            return numero
        
        # Extrair apenas números
        apenas_numeros = re.sub(r'[^\d]', '', numero)
        
        if len(apenas_numeros) != 20:
            return None
        
        # Formatar
        return (
            f"{apenas_numeros[:7]}-{apenas_numeros[7:9]}."
            f"{apenas_numeros[9:13]}.{apenas_numeros[13]}."
            f"{apenas_numeros[14:16]}.{apenas_numeros[16:20]}"
        )
    
    def _buscar_processo_com_timeout(
        self,
        numero: str,
        timeout: int = None
    ) -> Optional[Dict]:
        """
        Busca processo com timeout e verificação de cancelamento.
        
        Args:
            numero: Número do processo
            timeout: Timeout em segundos (usa self.search_timeout se None)
        
        Returns:
            Dict com informações do processo ou None
        
        Raises:
            InterruptedError: Se cancelado
            TimeoutError: Se exceder timeout
        """
        if timeout is None:
            timeout = self.search_timeout
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.search_service.buscar_processo, numero)
            
            elapsed = 0
            check_interval = 0.5
            
            while elapsed < timeout:
                # Verificar cancelamento
                if self._check_cancelado():
                    future.cancel()
                    raise InterruptedError(f"Busca cancelada: {numero}")
                
                try:
                    resultado = future.result(timeout=check_interval)
                    
                    # Converter ResultadoBusca para dict
                    if resultado and resultado.encontrado:
                        return {
                            "id_processo": resultado.id_processo,
                            "numero_processo": resultado.numero_processo,
                            "chave_acesso": resultado.chave_acesso,
                            "metodo": resultado.metodo_busca
                        }
                    return None
                    
                except FutureTimeoutError:
                    elapsed += check_interval
                    continue
            
            # Timeout atingido
            future.cancel()
            raise TimeoutError(f"Timeout ao buscar {numero}")
    
    def processar_generator(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa lista de números de processos.
        
        Args:
            numeros_processos: Lista de números CNJ
            tipo_documento: Tipo de documento para download
            aguardar_download: Se deve aguardar downloads pendentes
            tempo_espera: Tempo máximo de espera em segundos
        
        Yields:
            Dict com estado atual do processamento
        
        Returns:
            Relatório final
        """
        # Reset e preparação
        self._reset_cancelamento()
        self.download_service.limpar_diagnosticos()
        
        # Criar diretório
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        diretorio = self.download_dir / f"processos_{timestamp}"
        diretorio.mkdir(parents=True, exist_ok=True)
        
        # Inicializar relatório
        relatorio = self._criar_relatorio_base(
            "download_por_numero",
            diretorio,
            len(numeros_processos)
        )
        
        yield relatorio
        
        try:
            self.logger.section(f"PROCESSANDO {len(numeros_processos)} PROCESSOS POR NÚMERO")
            
            if not numeros_processos:
                relatorio["status"] = "concluido"
                relatorio["erros"].append("Nenhum processo informado")
                yield relatorio
                return relatorio
            
            # Estruturas de controle
            processos_info: Dict[str, Dict] = {}
            processos_pendentes: List[str] = []
            total = len(numeros_processos)
            
            relatorio["status"] = "processando"
            
            # ============ FASE 1: BUSCAR E SOLICITAR ============
            for i, numero in enumerate(numeros_processos, 1):
                # Verificar cancelamento
                self._check_cancelado_raise(f"processamento de {numero}")
                
                relatorio["processo_atual"] = numero
                relatorio["progresso"] = i
                self.logger.info(f"[{i}/{total}] Processando {numero}")
                yield relatorio
                
                # Normalizar número
                numero_norm = self._normalizar_numero(numero)
                if not numero_norm:
                    self.logger.error(f"Número inválido: {numero}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Número inválido: {numero}")
                    continue
                
                # Buscar processo
                relatorio["status"] = "buscando_processo"
                yield relatorio
                
                try:
                    proc_info = self._buscar_processo_com_timeout(numero_norm)
                    
                    if not proc_info or not proc_info.get("id_processo"):
                        self.logger.error(f"Processo não encontrado: {numero_norm}")
                        relatorio["falha"] += 1
                        relatorio["erros"].append(f"Processo não encontrado: {numero_norm}")
                        relatorio["status"] = "processando"
                        yield relatorio
                        continue
                    
                    processos_info[numero_norm] = proc_info
                    
                    # Verificar cancelamento antes de solicitar
                    self._check_cancelado_raise(f"download de {numero_norm}")
                    
                    relatorio["status"] = "processando"
                    yield relatorio
                    
                    # Solicitar download
                    sucesso, detalhes = self.download_service.solicitar_download(
                        proc_info["id_processo"],
                        numero_norm,
                        tipo_documento,
                        diretorio_download=diretorio
                    )
                    
                    if sucesso:
                        if detalhes.get("arquivo_baixado"):
                            arquivo_path = Path(detalhes["arquivo_baixado"])
                            if self._verificar_arquivo_valido(arquivo_path):
                                relatorio["arquivos"].append(str(arquivo_path))
                                relatorio["sucesso"] += 1
                                self.logger.success(f"Download concluído: {numero_norm}")
                            else:
                                processos_pendentes.append(numero_norm)
                        else:
                            processos_pendentes.append(numero_norm)
                    else:
                        relatorio["falha"] += 1
                        relatorio["erros"].append(f"Falha ao solicitar: {numero_norm}")
                    
                    yield relatorio
                    time.sleep(2)
                    
                except InterruptedError:
                    # Cancelamento - propagar
                    raise
                
                except TimeoutError as e:
                    self.logger.error(f"Timeout: {e}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Timeout: {numero_norm}")
                
                except Exception as e:
                    self.logger.error(f"Erro ao processar {numero_norm}: {e}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Erro em {numero_norm}: {str(e)}")
            
            # ============ FASE 2: AGUARDAR DOWNLOADS ============
            if aguardar_download and processos_pendentes:
                self._check_cancelado_raise("aguardar downloads")
                
                relatorio["status"] = "aguardando_downloads"
                relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
                yield relatorio
                
                arquivos = self._baixar_pendentes_verificado(
                    processos_pendentes,
                    diretorio,
                    tempo_espera=tempo_espera
                )
                
                for arq in arquivos:
                    if arq not in relatorio["arquivos"]:
                        relatorio["arquivos"].append(arq)
                        relatorio["sucesso"] += 1
            
            # ============ FASE 3: VERIFICAR INTEGRIDADE ============
            self._check_cancelado_raise("verificação de integridade")
            
            relatorio["status"] = "verificando_integridade"
            relatorio["processo_atual"] = "Verificando arquivos"
            yield relatorio
            
            processos_esperados = list(processos_info.keys())
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            relatorio["integridade"] = integridade["integridade"]
            processos_faltantes = integridade["processos_faltantes"]
            
            # ============ FASE 4: RETRIES ============
            if processos_faltantes:
                processos_faltantes = self._executar_retries(
                    processos_faltantes,
                    processos_info,
                    diretorio,
                    tipo_documento,
                    relatorio
                )
                
                if processos_faltantes:
                    relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
            
            # ============ FINALIZAÇÃO ============
            relatorio = self._finalizar_relatorio(
                relatorio,
                diretorio,
                processos_esperados,
                cancelado=False
            )
            
            yield relatorio
            return relatorio
        
        except InterruptedError as e:
            # Tratamento de cancelamento
            self.logger.warning(f"⚠️ Processamento CANCELADO: {e}")
            relatorio["status"] = "cancelado"
            relatorio["erros"].append(f"Cancelado: {str(e)}")
            
            relatorio = self._finalizar_relatorio(
                relatorio,
                diretorio,
                list(processos_info.keys()) if processos_info else [],
                cancelado=True
            )
            
            yield relatorio
            return relatorio
        
        except Exception as e:
            # Outros erros
            self.logger.error(f"Erro durante processamento: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            relatorio["status"] = "erro"
            relatorio["erros"].append(f"Erro: {str(e)}")
            relatorio["data_fim"] = datetime.now().isoformat()
            
            yield relatorio
            return relatorio
