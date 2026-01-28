import streamlit as st
import time
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List
from abc import abstractmethod

from .base import BasePage, ProcessingPageBase
from ..config import PAGE_CONFIG, STATUS_CONFIG, APP_CONFIG
from ..components.progress import (
    ProgressBar,
    ProcessingStatus,
    TimeEstimate,
    ProcessingContainer,
)
from ..components.buttons import CancelButton, ConfirmationDialog
from ..components.metrics import MetricsRow

# Configurar logger
logger = logging.getLogger("pje.processing")


class BaseProcessingPage(ProcessingPageBase):
    """
    Classe base para todas as páginas de processamento.
    """
    
    def _render_sidebar(self) -> None:
        """Sem sidebar nas páginas de processamento."""
        pass
    
    def _render_cancel_controls(self, key_prefix: str, iteration: int) -> None:
        """Renderiza controles de cancelamento."""
        if self._state.is_cancellation_requested:
            st.error("🛑 Cancelamento solicitado. Aguarde a interrupção...")
        
        elif self._state.get("show_cancel_confirm", False):
            st.warning("⚠️ Confirmar cancelamento?")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(
                    "Sim, cancelar",
                    type="primary",
                    use_container_width=True,
                    key=f"{key_prefix}_confirm_cancel_{iteration}"
                ):
                    self._handle_cancel_confirm()
            
            with col2:
                if st.button(
                    "Não, continuar",
                    use_container_width=True,
                    key=f"{key_prefix}_deny_cancel_{iteration}"
                ):
                    self._handle_cancel_deny()
        
        else:
            if st.button(
                "🛑 Cancelar processamento",
                use_container_width=True,
                key=f"{key_prefix}_request_cancel_{iteration}"
            ):
                self._handle_cancel_request()
    
    def _render_processing_ui(
        self,
        state: Dict[str, Any],
        start_time: float,
        key_prefix: str,
        iteration: int
    ) -> None:
        """Renderiza a interface de processamento."""
        status = state.get("status", "")
        progress = state.get("progresso", 0)
        total = state.get("processos", 0)
        current_process = state.get("processo_atual", "")
        success = state.get("sucesso", 0)
        files_count = len(state.get("arquivos", []))
        
        # Status
        status_component = ProcessingStatus(status, current_process)
        status_component.render()
        
        # Barra de progresso
        progress_value = progress / total if total > 0 else 0
        st.progress(progress_value)
        
        # Processo atual
        if current_process:
            st.caption(f"Processando: {current_process}")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("Progresso", f"{progress}/{total}")
        with col3:
            st.metric("Sucesso", success)
        with col4:
            st.metric("Arquivos", files_count)
        
        st.markdown("---")
        
        # Métricas de tempo
        elapsed_seconds = int(time.time() - start_time)
        mins, secs = divmod(elapsed_seconds, 60)
        
        cols = st.columns(3)
        
        with cols[0]:
            st.metric("Tempo decorrido", f"{mins}m {secs}s")
        
        with cols[1]:
            if progress > 0 and total > 0:
                time_per_process = elapsed_seconds / progress
                remaining = int((total - progress) * time_per_process)
                mins_rest, secs_rest = divmod(remaining, 60)
                st.metric("Tempo estimado", f"{mins_rest}m {secs_rest}s")
            else:
                st.metric("Tempo estimado", "-")
        
        with cols[2]:
            success_rate = (success / progress * 100) if progress > 0 else 0
            st.metric("Taxa de sucesso", f"{success_rate:.1f}%")
        
        st.markdown("---")
        
        # Controles de cancelamento
        self._render_cancel_controls(key_prefix, iteration)
    
    def _run_processing_loop(
        self,
        generator: Generator[Dict[str, Any], None, Dict[str, Any]],
        key_prefix: str
    ) -> None:
        """Executa o loop de processamento."""
        start_time = time.time()
        iteration = 0
        
        # Container para atualização
        status_container = st.empty()
        
        try:
            for state in generator:
                iteration += 1
                status = state.get("status", "")
                
                # Renderizar UI
                with status_container.container():
                    self._render_processing_ui(
                        state,
                        start_time,
                        key_prefix,
                        iteration
                    )
                
                # Verificar se terminou
                if STATUS_CONFIG.is_final_status(status):
                    self._state.report = state
                    self._state.reset_processing_state()
                    time.sleep(0.5)
                    self._navigation.go_to_result(state)
                    break
                
                # Pequeno delay para atualização da UI
                time.sleep(0.05)
        
        except InterruptedError:
            st.error("Processamento cancelado")
            time.sleep(1)
            self._state.reset_processing_state()
            self._navigation.navigate_to(self._get_back_page())
        
        except Exception as e:
            st.error(f"Erro durante processamento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            
            if st.button("Voltar", key=f"{key_prefix}_back_error"):
                self._navigation.navigate_to(self._get_back_page())


class ProcessingTaskPage(BaseProcessingPage):
    """Página de processamento de download por tarefa."""
    
    PAGE_TITLE = "Processando Tarefa"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_TASK
    
    def _validate_params(self) -> bool:
        task = self._state.get("selected_task")
        return task is not None
    
    def _get_generator(self):
        task = self._state.get("selected_task")
        limit = self._state.get("task_limit")
        use_favorites = self._state.get("task_usar_favoritas", False)
        batch_size = self._state.get("task_tamanho_lote", 10)
        
        return self.download_manager.process_task_generator(
            task_name=task.nome,
            use_favorites=use_favorites,
            limit=limit,
            batch_size=batch_size,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        task = self._state.get("selected_task")
        task_name = task.nome if task else "Desconhecida"
        st.title(f"📋 Processando: {task_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        if not self._validate_params():
            st.error("Nenhuma tarefa selecionada")
            self._navigation.go_to_download_by_task()
            return
        generator = self._get_generator()
        self._run_processing_loop(generator, "task")


class ProcessingTagPage(BaseProcessingPage):
    """Página de processamento de download por etiqueta."""
    
    PAGE_TITLE = "Processando Etiqueta"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_TAG
    
    def _validate_params(self) -> bool:
        tag = self._state.get("selected_tag")
        return tag is not None
    
    def _get_generator(self):
        tag = self._state.get("selected_tag")
        limit = self._state.get("tag_limit")
        batch_size = self._state.get("tag_tamanho_lote", 10)
        
        return self.download_manager.process_tag_generator(
            tag_name=tag.nome,
            limit=limit,
            batch_size=batch_size,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        tag = self._state.get("selected_tag")
        tag_name = tag.nome if tag else "Desconhecida"
        st.title(f"🏷️ Processando: {tag_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        if not self._validate_params():
            st.error("Nenhuma etiqueta selecionada")
            self._navigation.go_to_download_by_tag()
            return
        generator = self._get_generator()
        self._run_processing_loop(generator, "tag")


class ProcessingNumberPage(BaseProcessingPage):
    """Página de processamento de download por número."""
    
    PAGE_TITLE = "Processando Processos"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_NUMBER
    
    def _validate_params(self) -> bool:
        processes = self._state.get("processos_para_baixar", [])
        return len(processes) > 0
    
    def _get_generator(self):
        processes = self._state.get("processos_para_baixar", [])
        document_type = self._state.get("tipo_documento_numero", "Selecione")
        
        return self.download_manager.process_numbers_generator(
            process_numbers=processes,
            document_type=document_type,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        processes = self._state.get("processos_para_baixar", [])
        count = len(processes)
        st.title(f"🔢 Processando {count} processo(s)")
        st.markdown("---")
    
    def _render_content(self) -> None:
        if not self._validate_params():
            st.error("Nenhum processo para baixar")
            self._navigation.go_to_download_by_number()
            return
        generator = self._get_generator()
        self._run_processing_loop(generator, "number")


class ProcessingSubjectPage(BaseProcessingPage):
    """
    Página de processamento de download por assunto principal.
    
    CORREÇÃO PRINCIPAL: Usa idProcesso do cache para download direto,
    sem precisar buscar novamente via processar_numeros_generator.
    
    Fluxo corrigido:
    1. Para processos COM idProcesso: download_service.solicitar_download() DIRETO
    2. Para processos SEM idProcesso: fallback para busca por número
    """
    
    PAGE_TITLE = "Processando Assunto"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_SUBJECT
    
    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """Remove caracteres inválidos para nomes de pasta."""
        invalid_chars = r'[\\/:*?"<>|]'
        sanitized = re.sub(invalid_chars, '_', name)
        sanitized = ' '.join(sanitized.split())
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized.strip()
    
    @staticmethod
    def _create_subject_folder(subject_name: str, base_dir: str) -> str:
        """Cria pasta para downloads do assunto: NomeDoAssunto_(YYYYMMDD_HHMMSS)"""
        safe_name = ProcessingSubjectPage._sanitize_folder_name(subject_name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{safe_name}_({timestamp})"
        folder_path = os.path.join(base_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path
    
    def _get_subject_name(self, subject) -> str:
        if subject is None:
            return "Desconhecido"
        if isinstance(subject, dict):
            return subject.get('nome', 'Desconhecido')
        if hasattr(subject, 'nome'):
            return subject.nome or 'Desconhecido'
        return str(subject)
    
    def _get_subject_quantidade(self, subject) -> int:
        if subject is None:
            return 0
        if isinstance(subject, dict):
            return subject.get('quantidade', len(subject.get('processos', [])))
        if hasattr(subject, 'quantidade'):
            qty = subject.quantidade
            return qty() if callable(qty) else (qty or 0)
        if hasattr(subject, 'processos'):
            return len(subject.processos or [])
        return 0
    
    def _get_subject_processos(self, subject) -> List[Dict]:
        if subject is None:
            return []
        if isinstance(subject, dict):
            return subject.get('processos', [])
        if hasattr(subject, 'processos'):
            return subject.processos or []
        return []
    
    def _get_numero_processo(self, processo) -> str:
        """Obtém número do processo dos dados em cache."""
        if isinstance(processo, dict):
            return processo.get('numeroProcesso', '') or processo.get('numero_processo', '') or ''
        
        for field in ['numeroProcesso', 'numero_processo', 'numero']:
            if hasattr(processo, field):
                value = getattr(processo, field, None)
                if value:
                    return str(value)
        return str(processo)
    
    def _get_id_processo(self, processo) -> Optional[int]:
        """Obtém idProcesso dos dados em cache."""
        if isinstance(processo, dict):
            id_val = processo.get('idProcesso') or processo.get('id_processo')
            if id_val:
                try:
                    return int(id_val)
                except (ValueError, TypeError):
                    return None
        
        for field in ['idProcesso', 'id_processo', 'id']:
            if hasattr(processo, field):
                value = getattr(processo, field, None)
                if value:
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        continue
        return None
    
    def _validate_params(self) -> bool:
        subject = self._state.get("selected_subject")
        return subject is not None
    
    def _get_generator(self):
        """Retorna generator usando download DIRETO com idProcesso do cache."""
        subject = self._state.get("selected_subject")
        limit = self._state.get("subject_limit", 0)
        batch_size = self._state.get("subject_tamanho_lote", 10)
        
        return self._process_subject_direct(subject, limit, batch_size)
    
    def _process_subject_direct(self, subject, limit, batch_size):
        """
        Processa downloads usando idProcesso do cache para download DIRETO.
        
        CORREÇÃO PRINCIPAL:
        - Para processos COM idProcesso: chama download_service.solicitar_download() DIRETO
        - Para processos SEM idProcesso: fallback para busca por número
        
        Isso evita as 16 tentativas de busca em endpoints diferentes!
        """
        processos = self._get_subject_processos(subject)
        subject_name = self._get_subject_name(subject)
        
        logger.info(f"[SUBJECT_DIRECT] ===== INICIANDO DOWNLOAD =====")
        logger.info(f"[SUBJECT_DIRECT] Assunto: {subject_name}")
        logger.info(f"[SUBJECT_DIRECT] Total de processos no cache: {len(processos)}")
        
        if not processos:
            logger.error(f"[SUBJECT_DIRECT] Nenhum processo encontrado para: {subject_name}")
            yield {
                "status": "erro",
                "progresso": 0,
                "processos": 0,
                "sucesso": 0,
                "falha": 0,
                "arquivos": [],
                "processo_atual": "",
                "erros": [f"Nenhum processo encontrado para o assunto: {subject_name}"]
            }
            return
        
        if limit and limit > 0:
            processos = processos[:limit]
            logger.info(f"[SUBJECT_DIRECT] Limitado a {limit} processos")
        
        total = len(processos)
        
        # Criar pasta para este download
        base_dir = self._state.get("download_dir", APP_CONFIG.DOWNLOAD_DIR)
        download_folder = self._create_subject_folder(subject_name, base_dir)
        download_path = Path(download_folder)
        
        logger.info(f"[SUBJECT_DIRECT] Pasta de download: {download_folder}")
        
        # Separar processos com e sem ID
        processos_com_id = []
        processos_sem_id = []
        
        for proc in processos:
            id_processo = self._get_id_processo(proc)
            numero = self._get_numero_processo(proc)
            
            if id_processo:
                processos_com_id.append({
                    'idProcesso': id_processo,
                    'numeroProcesso': numero,
                    'dados': proc
                })
            else:
                processos_sem_id.append({
                    'numeroProcesso': numero,
                    'dados': proc
                })
        
        logger.info(f"[SUBJECT_DIRECT] Processos com ID (download direto): {len(processos_com_id)}")
        logger.info(f"[SUBJECT_DIRECT] Processos sem ID (precisam busca): {len(processos_sem_id)}")
        
        # Inicializar relatório
        relatorio = {
            "status": "iniciando",
            "progresso": 0,
            "processos": total,
            "sucesso": 0,
            "falha": 0,
            "arquivos": [],
            "erros": [],
            "processo_atual": "",
            "pasta_download": download_folder,
            "integridade": "pendente",
            "retries": {
                "tentativas": 0,
                "processos_reprocessados": [],
                "processos_falha_definitiva": []
            }
        }
        
        yield relatorio
        
        # Obter serviços
        client = self.session_service.client
        download_service = client._downloads
        
        processos_pendentes = []
        
        # ========== FASE 1: Download DIRETO para processos com ID ==========
        logger.info(f"[SUBJECT_DIRECT] ===== FASE 1: DOWNLOAD DIRETO =====")
        relatorio["status"] = "processando"
        
        for i, proc_info in enumerate(processos_com_id, 1):
            # Verificar cancelamento
            if self._state.is_cancellation_requested:
                logger.warning("[SUBJECT_DIRECT] Cancelamento solicitado")
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuário")
                yield relatorio
                return
            
            id_processo = proc_info['idProcesso']
            numero = proc_info['numeroProcesso']
            
            relatorio["processo_atual"] = numero
            relatorio["progresso"] = i
            
            logger.info(f"[SUBJECT_DIRECT] [{i}/{len(processos_com_id)}] Download direto: {numero} (ID={id_processo})")
            
            yield relatorio
            
            try:
                # DOWNLOAD DIRETO usando idProcesso!
                sucesso, detalhes = download_service.solicitar_download(
                    id_processo=id_processo,
                    numero_processo=numero,
                    tipo_documento="Selecione",
                    diretorio_download=download_path
                )
                
                if sucesso:
                    logger.info(f"[SUBJECT_DIRECT]   ✅ Solicitação OK")
                    
                    if detalhes.get("arquivo_baixado"):
                        arquivo = Path(detalhes["arquivo_baixado"])
                        if arquivo.exists() and arquivo.stat().st_size > 0:
                            relatorio["arquivos"].append(str(arquivo))
                            relatorio["sucesso"] += 1
                            logger.info(f"[SUBJECT_DIRECT]   📁 Arquivo baixado: {arquivo.name}")
                        else:
                            processos_pendentes.append(numero)
                            logger.info(f"[SUBJECT_DIRECT]   ⏳ Arquivo pendente (será aguardado)")
                    else:
                        processos_pendentes.append(numero)
                        logger.info(f"[SUBJECT_DIRECT]   ⏳ Download pendente (área de download)")
                else:
                    relatorio["falha"] += 1
                    relatorio["erros"].append(f"Falha ao solicitar download: {numero}")
                    logger.error(f"[SUBJECT_DIRECT]   ❌ Falha ao solicitar download")
                
            except Exception as e:
                relatorio["falha"] += 1
                relatorio["erros"].append(f"Erro em {numero}: {str(e)}")
                logger.error(f"[SUBJECT_DIRECT]   ❌ Exceção: {type(e).__name__}: {str(e)}")
            
            yield relatorio
            time.sleep(2)  # Delay entre requisições
        
        # ========== FASE 2: Busca e download para processos SEM ID ==========
        if processos_sem_id:
            logger.info(f"[SUBJECT_DIRECT] ===== FASE 2: BUSCA E DOWNLOAD =====")
            logger.info(f"[SUBJECT_DIRECT] {len(processos_sem_id)} processos precisam busca")
            
            relatorio["status"] = "buscando_processos"
            
            # Extrair números para busca
            numeros_para_buscar = [p['numeroProcesso'] for p in processos_sem_id if p['numeroProcesso']]
            
            if numeros_para_buscar:
                base_progress = len(processos_com_id)
                
                # Usar processar_numeros_generator como fallback
                for state in client.processar_numeros_generator(
                    numeros_processos=numeros_para_buscar,
                    tipo_documento="Selecione",
                    aguardar_download=False,  # Vamos aguardar tudo junto depois
                    tempo_espera=60
                ):
                    # Verificar cancelamento
                    if self._state.is_cancellation_requested:
                        logger.warning("[SUBJECT_DIRECT] Cancelamento solicitado na fase 2")
                        relatorio["status"] = "cancelado"
                        yield relatorio
                        return
                    
                    # Atualizar progresso
                    sub_progress = state.get("progresso", 0)
                    relatorio["progresso"] = base_progress + sub_progress
                    relatorio["processo_atual"] = state.get("processo_atual", "")
                    
                    # Agregar resultados
                    for arq in state.get("arquivos", []):
                        if arq not in relatorio["arquivos"]:
                            relatorio["arquivos"].append(arq)
                    
                    relatorio["erros"].extend(state.get("erros", []))
                    
                    yield relatorio
                
                # Atualizar contadores
                relatorio["sucesso"] = len(relatorio["arquivos"])
        
        # ========== FASE 3: Aguardar downloads pendentes ==========
        if processos_pendentes:
            logger.info(f"[SUBJECT_DIRECT] ===== FASE 3: AGUARDAR DOWNLOADS =====")
            logger.info(f"[SUBJECT_DIRECT] {len(processos_pendentes)} downloads pendentes")
            
            relatorio["status"] = "aguardando_downloads"
            relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
            yield relatorio
            
            # Aguardar e baixar
            time.sleep(5)  # Tempo inicial para geração
            
            inicio = time.time()
            tempo_espera = 300  # 5 minutos
            processos_restantes = set(processos_pendentes)
            
            while processos_restantes and (time.time() - inicio) < tempo_espera:
                if self._state.is_cancellation_requested:
                    break
                
                try:
                    downloads = download_service.listar_downloads_disponiveis()
                    
                    for download in downloads:
                        if self._state.is_cancellation_requested:
                            break
                        
                        numeros = download.get_numeros_processos()
                        for num in numeros:
                            if num in processos_restantes:
                                arquivo = download_service.baixar_arquivo(download, download_path)
                                if arquivo and arquivo.exists() and arquivo.stat().st_size > 0:
                                    relatorio["arquivos"].append(str(arquivo))
                                    relatorio["sucesso"] += 1
                                    processos_restantes.discard(num)
                                    logger.info(f"[SUBJECT_DIRECT] ✅ Download concluído: {num}")
                    
                    if processos_restantes:
                        relatorio["processo_atual"] = f"Restantes: {len(processos_restantes)}"
                        yield relatorio
                        time.sleep(10)
                    
                except Exception as e:
                    logger.error(f"[SUBJECT_DIRECT] Erro ao verificar downloads: {e}")
                    time.sleep(10)
        
        # ========== FASE 4: Verificar integridade ==========
        logger.info(f"[SUBJECT_DIRECT] ===== FASE 4: VERIFICAR INTEGRIDADE =====")
        
        relatorio["status"] = "verificando_integridade"
        relatorio["processo_atual"] = "Verificando arquivos"
        yield relatorio
        
        # Verificar quais processos foram baixados
        arquivos_baixados = set()
        for arq in relatorio["arquivos"]:
            arquivo_path = Path(arq)
            if arquivo_path.exists():
                # Extrair número do nome do arquivo
                match = re.match(r'^(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', arquivo_path.name)
                if match:
                    arquivos_baixados.add(match.group(1))
        
        # Comparar com esperado
        todos_numeros = set()
        for proc in processos:
            numero = self._get_numero_processo(proc)
            if numero:
                todos_numeros.add(numero)
        
        processos_faltantes = todos_numeros - arquivos_baixados
        
        if processos_faltantes:
            relatorio["integridade"] = "inconsistente"
            relatorio["retries"]["processos_falha_definitiva"] = list(processos_faltantes)
            logger.warning(f"[SUBJECT_DIRECT] {len(processos_faltantes)} processos faltantes")
        else:
            relatorio["integridade"] = "ok"
            logger.info(f"[SUBJECT_DIRECT] ✅ Integridade OK")
        
        # ========== FINALIZAÇÃO ==========
        logger.info(f"[SUBJECT_DIRECT] ===== FINALIZAÇÃO =====")
        
        # Recalcular contadores finais
        relatorio["sucesso"] = len([a for a in relatorio["arquivos"] if Path(a).exists()])
        relatorio["falha"] = relatorio["processos"] - relatorio["sucesso"]
        relatorio["processo_atual"] = ""
        
        if self._state.is_cancellation_requested:
            relatorio["status"] = "cancelado"
        elif relatorio["integridade"] == "ok":
            relatorio["status"] = "concluido"
        elif processos_faltantes:
            relatorio["status"] = "concluido_com_falhas"
        else:
            relatorio["status"] = "concluido"
        
        logger.info(f"[SUBJECT_DIRECT] Status final: {relatorio['status']}")
        logger.info(f"[SUBJECT_DIRECT] Sucesso: {relatorio['sucesso']}")
        logger.info(f"[SUBJECT_DIRECT] Falha: {relatorio['falha']}")
        logger.info(f"[SUBJECT_DIRECT] Arquivos: {len(relatorio['arquivos'])}")
        logger.info(f"[SUBJECT_DIRECT] ===== FIM =====")
        
        yield relatorio
    
    def _render_header(self) -> None:
        subject = self._state.get("selected_subject")
        subject_name = self._get_subject_name(subject)
        quantidade = self._get_subject_quantidade(subject)
        
        if len(subject_name) > 50:
            subject_name_display = subject_name[:50] + "..."
        else:
            subject_name_display = subject_name
        
        st.title(f"📚 Processando: {subject_name_display}")
        
        if quantidade > 0:
            # Contar processos com ID
            processos = self._get_subject_processos(subject)
            com_id = sum(1 for p in processos if self._get_id_processo(p))
            
            st.caption(f"Total de processos: {quantidade} ({com_id} com download direto)")
        
        st.markdown("---")
    
    def _render_content(self) -> None:
        if not self._validate_params():
            st.error("Nenhum assunto selecionado")
            self._navigation.go_to_download_by_subject()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "subject")