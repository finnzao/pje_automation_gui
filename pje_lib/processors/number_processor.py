"""
Processador para download de processos por número.

Atualizado para usar o método de busca direta que acessa
diretamente o endpoint de consulta pública para obter
idProcesso e chave de acesso (ca).
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
    - Busca de processos por número usando múltiplas estratégias
    - Busca direta (mais eficiente para processos fora do painel)
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
        timeout: int = None,
        metodos: List[str] = None
    ) -> Optional[Dict]:
        """
        Busca processo com timeout e verificação de cancelamento.
        
        Args:
            numero: Número do processo
            timeout: Timeout em segundos (usa self.search_timeout se None)
            metodos: Lista de métodos de busca a usar
                    Default: ['busca_direta', 'consulta_publica', 'painel_tarefas', 'etiquetas']
        
        Returns:
            Dict com informações do processo ou None
        
        Raises:
            InterruptedError: Se cancelado
            TimeoutError: Se exceder timeout
        """
        if timeout is None:
            timeout = self.search_timeout
        
        # Métodos padrão - api_processo primeiro por ser mais confiável
        # NOTA: etiquetas removido por ser muito lento
        if metodos is None:
            metodos = ['api_processo', 'painel_tarefas', 'busca_direta']
        
        self.logger.debug(f"[BUSCA_TIMEOUT] Iniciando busca para: {numero}")
        self.logger.debug(f"[BUSCA_TIMEOUT] Timeout: {timeout}s, Métodos: {metodos}")
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Passar os métodos de busca para o serviço
            future = executor.submit(
                self.search_service.buscar_processo, 
                numero,
                True,  # usar_cache
                metodos
            )
            
            elapsed = 0
            check_interval = 0.5
            
            while elapsed < timeout:
                # Verificar cancelamento
                if self._check_cancelado():
                    self.logger.warning(f"[BUSCA_TIMEOUT] ⚠️ Busca CANCELADA pelo usuário")
                    future.cancel()
                    raise InterruptedError(f"Busca cancelada: {numero}")
                
                try:
                    resultado = future.result(timeout=check_interval)
                    
                    # Converter ResultadoBusca para dict
                    if resultado and resultado.encontrado:
                        self.logger.info(f"[BUSCA_TIMEOUT] ✅ Processo encontrado!")
                        self.logger.debug(f"[BUSCA_TIMEOUT]   ID: {resultado.id_processo}")
                        self.logger.debug(f"[BUSCA_TIMEOUT]   Método: {resultado.metodo_busca}")
                        self.logger.debug(f"[BUSCA_TIMEOUT]   CA: {resultado.chave_acesso[:30] + '...' if resultado.chave_acesso else 'N/A'}")
                        return {
                            "id_processo": resultado.id_processo,
                            "numero_processo": resultado.numero_processo,
                            "chave_acesso": resultado.chave_acesso,
                            "metodo": resultado.metodo_busca,
                            "url_autos": resultado.url_autos
                        }
                    
                    self.logger.info(f"[BUSCA_TIMEOUT] ❌ Processo NÃO encontrado")
                    return None
                    
                except FutureTimeoutError:
                    elapsed += check_interval
                    if elapsed % 10 == 0:  # Log a cada 10 segundos
                        self.logger.debug(f"[BUSCA_TIMEOUT] Aguardando... ({elapsed:.0f}s / {timeout}s)")
                    continue
            
            # Timeout atingido
            self.logger.error(f"[BUSCA_TIMEOUT] ❌ TIMEOUT após {timeout}s")
            future.cancel()
            raise TimeoutError(f"Timeout ao buscar {numero}")
    
    def processar_generator(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300,
        metodos_busca: List[str] = None
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa lista de números de processos.
        
        Args:
            numeros_processos: Lista de números CNJ
            tipo_documento: Tipo de documento para download
            aguardar_download: Se deve aguardar downloads pendentes
            tempo_espera: Tempo máximo de espera em segundos
            metodos_busca: Lista de métodos de busca a usar
                          Default: ['busca_direta', 'consulta_publica', 'painel_tarefas', 'etiquetas']
        
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
            self.logger.info("=" * 60)
            self.logger.info("FASE 1: BUSCAR PROCESSOS E SOLICITAR DOWNLOADS")
            self.logger.info("=" * 60)
            
            for i, numero in enumerate(numeros_processos, 1):
                # Verificar cancelamento
                self._check_cancelado_raise(f"processamento de {numero}")
                
                relatorio["processo_atual"] = numero
                relatorio["progresso"] = i
                
                self.logger.info("=" * 60)
                self.logger.info(f"[{i}/{total}] Processando: {numero}")
                self.logger.info("=" * 60)
                
                yield relatorio
                
                # Normalizar número
                numero_norm = self._normalizar_numero(numero)
                if not numero_norm:
                    self.logger.error(f"[{i}/{total}] ❌ Número INVÁLIDO: {numero}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Número inválido: {numero}")
                    continue
                
                self.logger.debug(f"[{i}/{total}] Número normalizado: {numero_norm}")
                
                # Buscar processo
                relatorio["status"] = "buscando_processo"
                self.logger.info(f"[{i}/{total}] Buscando processo...")
                yield relatorio
                
                try:
                    proc_info = self._buscar_processo_com_timeout(
                        numero_norm,
                        metodos=metodos_busca
                    )
                    
                    if not proc_info or not proc_info.get("id_processo"):
                        self.logger.error(f"[{i}/{total}] ❌ Processo NÃO ENCONTRADO: {numero_norm}")
                        relatorio["falha"] += 1
                        relatorio["erros"].append(f"Processo não encontrado: {numero_norm}")
                        relatorio["status"] = "processando"
                        yield relatorio
                        continue
                    
                    processos_info[numero_norm] = proc_info
                    
                    # Log do método de busca utilizado
                    metodo = proc_info.get("metodo", "desconhecido")
                    self.logger.info(f"[{i}/{total}] ✅ Processo ENCONTRADO!")
                    self.logger.info(f"[{i}/{total}]   Método: {metodo}")
                    self.logger.info(f"[{i}/{total}]   ID: {proc_info['id_processo']}")
                    self.logger.info(f"[{i}/{total}]   CA: {proc_info.get('chave_acesso', 'N/A')[:30]}...")
                    
                    # Verificar cancelamento antes de solicitar
                    self._check_cancelado_raise(f"download de {numero_norm}")
                    
                    relatorio["status"] = "processando"
                    yield relatorio
                    
                    # Solicitar download
                    self.logger.info(f"[{i}/{total}] Solicitando download...")
                    sucesso, detalhes = self.download_service.solicitar_download(
                        proc_info["id_processo"],
                        numero_norm,
                        tipo_documento,
                        diretorio_download=diretorio
                    )
                    
                    if sucesso:
                        self.logger.debug(f"[{i}/{total}] Solicitação OK. Detalhes: {detalhes}")
                        if detalhes.get("arquivo_baixado"):
                            arquivo_path = Path(detalhes["arquivo_baixado"])
                            if self._verificar_arquivo_valido(arquivo_path):
                                relatorio["arquivos"].append(str(arquivo_path))
                                relatorio["sucesso"] += 1
                                self.logger.success(f"[{i}/{total}] ✅ Download CONCLUÍDO: {arquivo_path.name}")
                            else:
                                self.logger.warning(f"[{i}/{total}] ⚠️ Arquivo inválido/corrompido")
                                processos_pendentes.append(numero_norm)
                        else:
                            self.logger.info(f"[{i}/{total}] Download pendente (será aguardado)")
                            processos_pendentes.append(numero_norm)
                    else:
                        self.logger.error(f"[{i}/{total}] ❌ Falha ao solicitar download")
                        self.logger.error(f"[{i}/{total}]   Detalhes: {detalhes}")
                        relatorio["falha"] += 1
                        relatorio["erros"].append(f"Falha ao solicitar: {numero_norm}")
                    
                    yield relatorio
                    time.sleep(2)
                    
                except InterruptedError:
                    # Cancelamento - propagar
                    raise
                
                except TimeoutError as e:
                    self.logger.error(f"[{i}/{total}] ❌ TIMEOUT: {e}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Timeout: {numero_norm}")
                
                except Exception as e:
                    self.logger.error(f"[{i}/{total}] ❌ ERRO: {type(e).__name__}: {str(e)}")
                    import traceback
                    self.logger.debug(f"[{i}/{total}] Traceback:\n{traceback.format_exc()}")
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Erro em {numero_norm}: {str(e)}")
            
            # ============ FASE 2: AGUARDAR DOWNLOADS ============
            self.logger.info("=" * 60)
            self.logger.info("FASE 2: AGUARDAR DOWNLOADS PENDENTES")
            self.logger.info("=" * 60)
            
            if aguardar_download and processos_pendentes:
                self._check_cancelado_raise("aguardar downloads")
                
                self.logger.info(f"Processos pendentes: {len(processos_pendentes)}")
                for p in processos_pendentes:
                    self.logger.debug(f"  - {p}")
                
                relatorio["status"] = "aguardando_downloads"
                relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
                yield relatorio
                
                arquivos = self._baixar_pendentes_verificado(
                    processos_pendentes,
                    diretorio,
                    tempo_espera=tempo_espera
                )
                
                self.logger.info(f"Arquivos baixados na fase 2: {len(arquivos)}")
                
                for arq in arquivos:
                    if arq not in relatorio["arquivos"]:
                        relatorio["arquivos"].append(arq)
                        relatorio["sucesso"] += 1
                        self.logger.success(f"✅ Download concluído (pendente): {arq}")
            else:
                if not processos_pendentes:
                    self.logger.info("Nenhum download pendente")
            
            # ============ FASE 3: VERIFICAR INTEGRIDADE ============
            self.logger.info("=" * 60)
            self.logger.info("FASE 3: VERIFICAR INTEGRIDADE")
            self.logger.info("=" * 60)
            
            self._check_cancelado_raise("verificação de integridade")
            
            relatorio["status"] = "verificando_integridade"
            relatorio["processo_atual"] = "Verificando arquivos"
            yield relatorio
            
            processos_esperados = list(processos_info.keys())
            self.logger.info(f"Processos esperados: {len(processos_esperados)}")
            self.logger.info(f"Arquivos baixados: {len(relatorio['arquivos'])}")
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            relatorio["integridade"] = integridade["integridade"]
            processos_faltantes = integridade["processos_faltantes"]
            
            self.logger.info(f"Integridade: {integridade['integridade']}")
            if processos_faltantes:
                self.logger.warning(f"Processos faltantes: {len(processos_faltantes)}")
                for p in processos_faltantes:
                    self.logger.warning(f"  - {p}")
            
            # ============ FASE 4: RETRIES ============
            self.logger.info("=" * 60)
            self.logger.info("FASE 4: RETRIES (se necessário)")
            self.logger.info("=" * 60)
            
            if processos_faltantes:
                self.logger.info(f"Tentando retry para {len(processos_faltantes)} processos faltantes")
                processos_faltantes = self._executar_retries(
                    processos_faltantes,
                    processos_info,
                    diretorio,
                    tipo_documento,
                    relatorio
                )
                
                if processos_faltantes:
                    self.logger.error(f"❌ {len(processos_faltantes)} processos falharam após retries:")
                    for p in processos_faltantes:
                        self.logger.error(f"  - {p}")
                    relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
                else:
                    self.logger.success("✅ Todos os retries concluídos com sucesso!")
            else:
                self.logger.info("Nenhum retry necessário")
            
            # ============ FINALIZAÇÃO ============
            self.logger.info("=" * 60)
            self.logger.info("FINALIZAÇÃO")
            self.logger.info("=" * 60)
            
            relatorio = self._finalizar_relatorio(
                relatorio,
                diretorio,
                processos_esperados,
                cancelado=False
            )
            
            self.logger.info(f"Status final: {relatorio['status']}")
            self.logger.info(f"Sucesso: {relatorio['sucesso']}")
            self.logger.info(f"Falha: {relatorio['falha']}")
            self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
            self.logger.info(f"Integridade: {relatorio['integridade']}")
            
            if relatorio['erros']:
                self.logger.warning(f"Erros encontrados: {len(relatorio['erros'])}")
                for erro in relatorio['erros'][:10]:  # Mostrar até 10 erros
                    self.logger.warning(f"  - {erro}")
            
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