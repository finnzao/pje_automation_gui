import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Generator

from .base_processor import BaseProcessor
from ..models import ProcessoTarefa, AssuntoPrincipal
from ..utils import normalizar_nome_pasta


class SubjectProcessor(BaseProcessor):
    """
    Processador especializado para downloads por assunto principal.
    
    Implementa:
    - Download de todos os processos de um assunto
    - Download em lotes
    - Verificação de integridade
    """
    
    def __init__(
        self,
        download_service,
        download_dir: Path,
        max_retries: int = 2,
        retry_delay: int = 5,
        tamanho_lote: int = 10
    ):
        super().__init__(download_service, download_dir, max_retries, retry_delay)
        self.tamanho_lote = tamanho_lote
    
    def processar_generator(
        self,
        assunto: AssuntoPrincipal,
        limite: int = None,
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa downloads de um assunto principal.
        
        Args:
            assunto: Assunto com lista de processos
            limite: Limite de processos (None = todos)
            tipo_documento: Tipo de documento
            aguardar_download: Se deve aguardar downloads
            tempo_espera: Tempo máximo de espera
        
        Yields:
            Estado atual do processamento
        
        Returns:
            Relatório final
        """
        # Reset e preparação
        self._reset_cancelamento()
        self.download_service.limpar_diagnosticos()
        
        # Criar diretório
        nome_pasta = normalizar_nome_pasta(f"assunto_{assunto.nome[:50]}")
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        # Obter processos
        processos = assunto.processos
        if limite:
            processos = processos[:limite]
        
        # Inicializar relatório
        relatorio = self._criar_relatorio_base(
            "download_por_assunto",
            diretorio,
            len(processos)
        )
        relatorio["assunto"] = assunto.nome
        
        yield relatorio
        
        try:
            self.logger.section(f"PROCESSANDO ASSUNTO: {assunto.nome}")
            self.logger.info(f"Total de processos: {len(processos)}")
            
            if not processos:
                relatorio["status"] = "concluido"
                relatorio["erros"].append("Nenhum processo encontrado para este assunto")
                yield relatorio
                return relatorio
            
            # Estruturas de controle
            mapa_processos = {p.numero_processo: p for p in processos}
            processos_esperados = list(mapa_processos.keys())
            processos_pendentes = []
            total = len(processos)
            
            relatorio["status"] = "processando"
            
            #  FASE 1: PROCESSAR PROCESSOS 
            for i, proc in enumerate(processos, 1):
                # Verificar cancelamento
                self._check_cancelado_raise(f"processamento de {proc.numero_processo}")
                
                relatorio["processo_atual"] = proc.numero_processo
                relatorio["progresso"] = i
                self.logger.info(f"[{i}/{total}] {proc.numero_processo}")
                yield relatorio
                
                # Solicitar download
                sucesso, detalhes = self.download_service.solicitar_download(
                    proc.id_processo,
                    proc.numero_processo,
                    tipo_documento,
                    diretorio_download=diretorio
                )
                
                if sucesso:
                    if detalhes.get("arquivo_baixado"):
                        arquivo_path = Path(detalhes["arquivo_baixado"])
                        if self._verificar_arquivo_valido(arquivo_path):
                            relatorio["arquivos"].append(str(arquivo_path))
                            relatorio["sucesso"] += 1
                        else:
                            processos_pendentes.append(proc.numero_processo)
                    else:
                        processos_pendentes.append(proc.numero_processo)
                else:
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Falha ao solicitar: {proc.numero_processo}")
                
                yield relatorio
                time.sleep(2)
                
                #  DOWNLOAD EM LOTES 
                if len(processos_pendentes) >= self.tamanho_lote:
                    self._check_cancelado_raise("download em lote")
                    
                    relatorio["status"] = "baixando_lote"
                    yield relatorio
                    
                    arquivos = self._baixar_pendentes_verificado(
                        processos_pendentes,
                        diretorio,
                        tempo_espera=60
                    )
                    
                    for arq in arquivos:
                        if arq not in relatorio["arquivos"]:
                            relatorio["arquivos"].append(arq)
                            relatorio["sucesso"] += 1
                    
                    processos_pendentes.clear()
                    relatorio["status"] = "processando"
                    yield relatorio
            
            #  FASE 2: AGUARDAR DOWNLOADS FINAIS 
            if aguardar_download and processos_pendentes:
                self._check_cancelado_raise("aguardar downloads finais")
                
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
            
            #  FASE 3: VERIFICAR INTEGRIDADE 
            self._check_cancelado_raise("verificação de integridade")
            
            relatorio["status"] = "verificando_integridade"
            relatorio["processo_atual"] = "Verificando arquivos"
            yield relatorio
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            relatorio["integridade"] = integridade["integridade"]
            processos_faltantes = integridade["processos_faltantes"]
            
            #  FASE 4: RETRIES 
            if processos_faltantes:
                # Converter para formato esperado pelo _executar_retries
                mapa_para_retry = {
                    num: {"id_processo": mapa_processos[num].id_processo}
                    for num in processos_faltantes
                    if num in mapa_processos
                }
                
                processos_faltantes = self._executar_retries(
                    processos_faltantes,
                    mapa_para_retry,
                    diretorio,
                    tipo_documento,
                    relatorio
                )
                
                if processos_faltantes:
                    relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
            
            #  FINALIZAÇÃO 
            relatorio = self._finalizar_relatorio(
                relatorio,
                diretorio,
                processos_esperados,
                cancelado=False
            )
            
            yield relatorio
            return relatorio
        
        except InterruptedError as e:
            # Cancelamento
            self.logger.warning(f"⚠️ Processamento CANCELADO: {e}")
            relatorio["status"] = "cancelado"
            relatorio["erros"].append(f"Cancelado: {str(e)}")
            
            processos_esperados = list(mapa_processos.keys()) if 'mapa_processos' in locals() else []
            relatorio = self._finalizar_relatorio(
                relatorio,
                diretorio,
                processos_esperados,
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