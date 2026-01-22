"""
Processador para download de processos por tarefa.
"""

import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator

from .base_processor import BaseProcessor
from ..utils import normalizar_nome_pasta


class TaskProcessor(BaseProcessor):
    """
    Processador especializado para downloads por tarefa.
    
    Implementa:
    - Busca de tarefas
    - Listagem de processos da tarefa
    - Download em lotes
    """
    
    def __init__(
        self,
        download_service,
        task_service,
        download_dir: Path,
        max_retries: int = 2,
        retry_delay: int = 5,
        tamanho_lote: int = 10
    ):
        super().__init__(download_service, download_dir, max_retries, retry_delay)
        self.task_service = task_service
        self.tamanho_lote = tamanho_lote
    
    def processar_generator(
        self,
        nome_tarefa: str,
        usar_favoritas: bool = False,
        limite: int = None,
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa downloads de uma tarefa.
        
        Args:
            nome_tarefa: Nome da tarefa
            usar_favoritas: Se deve buscar em favoritas
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
        nome_pasta = normalizar_nome_pasta(nome_tarefa)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        # Inicializar relatório
        relatorio = self._criar_relatorio_base(
            "download_por_tarefa",
            diretorio,
            0  # Será atualizado após listar processos
        )
        relatorio["tarefa"] = nome_tarefa
        relatorio["usar_favoritas"] = usar_favoritas
        
        yield relatorio
        
        try:
            self.logger.section(f"PROCESSANDO TAREFA: {nome_tarefa}")
            
            # ============ FASE 1: BUSCAR TAREFA ============
            self._check_cancelado_raise("busca de tarefa")
            
            relatorio["status"] = "buscando_tarefa"
            yield relatorio
            
            tarefa = self.task_service.buscar_tarefa_por_nome(nome_tarefa, usar_favoritas)
            
            if not tarefa:
                relatorio["status"] = "erro"
                relatorio["erros"].append("Tarefa não encontrada")
                yield relatorio
                return relatorio
            
            # ============ FASE 2: LISTAR PROCESSOS ============
            self._check_cancelado_raise("listagem de processos")
            
            relatorio["status"] = "listando_processos"
            yield relatorio
            
            processos = self.task_service.listar_todos_processos_tarefa(
                tarefa.nome,
                usar_favoritas
            )
            
            if limite:
                processos = processos[:limite]
            
            relatorio["processos"] = len(processos)
            
            if not processos:
                relatorio["status"] = "concluido"
                relatorio["erros"].append("Nenhum processo encontrado")
                yield relatorio
                return relatorio
            
            # Estruturas de controle
            mapa_processos = {p.numero_processo: p for p in processos}
            processos_esperados = list(mapa_processos.keys())
            processos_pendentes = []
            total = len(processos)
            
            relatorio["status"] = "processando"
            
            # ============ FASE 3: PROCESSAR PROCESSOS ============
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
                
                yield relatorio
                time.sleep(2)
                
                # ============ DOWNLOAD EM LOTES ============
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
            
            # ============ FASE 4: AGUARDAR DOWNLOADS FINAIS ============
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
            
            # ============ FASE 5: VERIFICAR INTEGRIDADE ============
            self._check_cancelado_raise("verificação de integridade")
            
            relatorio["status"] = "verificando_integridade"
            relatorio["processo_atual"] = "Verificando arquivos"
            yield relatorio
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            relatorio["integridade"] = integridade["integridade"]
            processos_faltantes = integridade["processos_faltantes"]
            
            # ============ FASE 6: RETRIES ============
            if processos_faltantes:
                processos_faltantes = self._executar_retries(
                    processos_faltantes,
                    mapa_processos,
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
