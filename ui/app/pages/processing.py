import streamlit as st
import time
from typing import Dict, Any, Generator, Optional, List
from abc import abstractmethod

from .base import BasePage, ProcessingPageBase
from ..config import PAGE_CONFIG, STATUS_CONFIG
from ..components.progress import (
    ProgressBar,
    ProcessingStatus,
    TimeEstimate,
    ProcessingContainer,
)
from ..components.buttons import CancelButton, ConfirmationDialog
from ..components.metrics import MetricsRow


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
        """Valida se há tarefa selecionada."""
        task = self._state.get("selected_task")
        return task is not None
    
    def _get_generator(self):
        """Retorna generator de processamento de tarefa."""
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
        """Renderiza cabeçalho com nome da tarefa."""
        task = self._state.get("selected_task")
        task_name = task.nome if task else "Desconhecida"
        
        st.title(f"📋 Processando: {task_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
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
        """Valida se há etiqueta selecionada."""
        tag = self._state.get("selected_tag")
        return tag is not None
    
    def _get_generator(self):
        """Retorna generator de processamento de etiqueta."""
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
        """Renderiza cabeçalho com nome da etiqueta."""
        tag = self._state.get("selected_tag")
        tag_name = tag.nome if tag else "Desconhecida"
        
        st.title(f"🏷️ Processando: {tag_name}")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
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
        """Valida se há processos para baixar."""
        processes = self._state.get("processos_para_baixar", [])
        return len(processes) > 0
    
    def _get_generator(self):
        """Retorna generator de processamento por número."""
        processes = self._state.get("processos_para_baixar", [])
        document_type = self._state.get("tipo_documento_numero", "Selecione")
        
        return self.download_manager.process_numbers_generator(
            process_numbers=processes,
            document_type=document_type,
            wait_download=True
        )
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com quantidade de processos."""
        processes = self._state.get("processos_para_baixar", [])
        count = len(processes)
        
        st.title(f"🔢 Processando {count} processo(s)")
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        if not self._validate_params():
            st.error("Nenhum processo para baixar")
            self._navigation.go_to_download_by_number()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "number")


class ProcessingSubjectPage(BaseProcessingPage):
    """Página de processamento de download por assunto principal."""
    
    PAGE_TITLE = "Processando Assunto"
    
    def _get_back_page(self) -> str:
        return PAGE_CONFIG.DOWNLOAD_BY_SUBJECT
    
    def _get_subject_name(self, subject) -> str:
        """Obtém nome do assunto de forma segura."""
        if subject is None:
            return "Desconhecido"
        if isinstance(subject, dict):
            return subject.get('nome', 'Desconhecido')
        if hasattr(subject, 'nome'):
            return subject.nome or 'Desconhecido'
        return str(subject)
    
    def _get_subject_quantidade(self, subject) -> int:
        """Obtém quantidade de processos do assunto de forma segura."""
        if subject is None:
            return 0
        if isinstance(subject, dict):
            return subject.get('quantidade', len(subject.get('processos', [])))
        if hasattr(subject, 'quantidade'):
            qty = subject.quantidade
            if callable(qty):
                return qty()
            return qty if qty is not None else 0
        if hasattr(subject, 'processos'):
            return len(subject.processos or [])
        return 0
    
    def _get_subject_processos(self, subject) -> list:
        """Obtém lista de processos do assunto de forma segura."""
        if subject is None:
            return []
        if isinstance(subject, dict):
            return subject.get('processos', [])
        if hasattr(subject, 'processos'):
            return subject.processos or []
        return []
    
    def _get_numero_processo(self, processo) -> str:
        """Obtém número do processo de forma segura."""
        field_names = ['numeroProcesso', 'numero_processo', 'numero', 'number']
        
        if isinstance(processo, dict):
            for field in field_names:
                if field in processo and processo[field]:
                    return str(processo[field])
            return str(processo)
        
        for field in field_names:
            if hasattr(processo, field):
                value = getattr(processo, field, None)
                if value:
                    return str(value)
        
        return str(processo)
    
    def _validate_params(self) -> bool:
        """Valida se há assunto selecionado."""
        subject = self._state.get("selected_subject")
        return subject is not None
    
    def _get_generator(self):
        """
        Retorna generator de processamento de assunto.
        Usa os processos diretamente do assunto selecionado.
        """
        subject = self._state.get("selected_subject")
        limit = self._state.get("subject_limit", 0)
        batch_size = self._state.get("subject_tamanho_lote", 10)
        
        # Usar processamento direto com os processos já coletados
        return self._process_subject_directly(subject, limit, batch_size)
    
    def _process_subject_directly(self, subject, limit, batch_size):
        """
        Processa os processos do assunto diretamente.
        Usa os processos já coletados na análise.
        """
        processos = self._get_subject_processos(subject)
        subject_name = self._get_subject_name(subject)
        
        if not processos:
            yield {
                "status": "Erro",
                "progresso": 0,
                "processos": 0,
                "sucesso": 0,
                "falhas": 0,
                "arquivos": [],
                "processo_atual": "",
                "mensagem": f"Nenhum processo encontrado para o assunto: {subject_name}"
            }
            return
        
        if limit and limit > 0:
            processos = processos[:limit]
        
        total = len(processos)
        
        yield {
            "status": "Iniciando",
            "progresso": 0,
            "processos": total,
            "sucesso": 0,
            "falhas": 0,
            "arquivos": [],
            "processo_atual": ""
        }
        
        sucesso = 0
        falhas = 0
        arquivos = []
        
        client = self.session_service.client
        
        # Extrair números dos processos primeiro
        numeros_processos = []
        for processo in processos:
            numero = self._get_numero_processo(processo)
            if numero:
                numeros_processos.append(numero)
        
        # Usar o método processar_numeros_generator se disponível
        if hasattr(client, 'processar_numeros_generator'):
            try:
                for state in client.processar_numeros_generator(
                    numeros_processos=numeros_processos,
                    tipo_documento="Selecione",
                    aguardar_download=True,
                    tempo_espera=300
                ):
                    # Verificar cancelamento
                    if self._state.is_cancellation_requested:
                        state['status'] = 'Cancelado'
                        yield state
                        return
                    
                    yield state
                return
            except Exception as e:
                print(f"Erro usando processar_numeros_generator: {e}")
                # Continuar com processamento individual
        
        # Fallback: processar individualmente
        for idx, numero in enumerate(numeros_processos):
            # Verificar cancelamento
            if self._state.is_cancellation_requested:
                yield {
                    "status": "Cancelado",
                    "progresso": idx,
                    "processos": total,
                    "sucesso": sucesso,
                    "falhas": falhas,
                    "arquivos": arquivos,
                    "processo_atual": ""
                }
                return
            
            yield {
                "status": "Processando",
                "progresso": idx,
                "processos": total,
                "sucesso": sucesso,
                "falhas": falhas,
                "arquivos": arquivos,
                "processo_atual": numero
            }
            
            try:
                resultado = None
                
                # Tentar diferentes métodos de download
                # Método 1: solicitar_download com argumento nomeado
                if hasattr(client, 'solicitar_download'):
                    try:
                        resultado = client.solicitar_download(numero_processo=numero)
                    except TypeError:
                        # Tentar com outro nome de parâmetro
                        try:
                            resultado = client.solicitar_download(processo=numero)
                        except TypeError:
                            pass
                
                # Método 2: download_service
                if not resultado and hasattr(client, '_download_service'):
                    ds = client._download_service
                    if hasattr(ds, 'solicitar_download'):
                        try:
                            resultado = ds.solicitar_download(numero_processo=numero)
                        except TypeError:
                            try:
                                resultado = ds.solicitar_download(numero)
                            except:
                                pass
                
                # Método 3: baixar_processo
                if not resultado and hasattr(client, 'baixar_processo'):
                    try:
                        resultado = client.baixar_processo(numero_processo=numero)
                    except TypeError:
                        try:
                            resultado = client.baixar_processo(numero)
                        except:
                            pass
                
                if resultado:
                    sucesso += 1
                    if isinstance(resultado, str):
                        arquivos.append(resultado)
                    elif isinstance(resultado, dict):
                        if 'arquivo' in resultado:
                            arquivos.append(resultado['arquivo'])
                        elif 'path' in resultado:
                            arquivos.append(resultado['path'])
                else:
                    falhas += 1
                    
            except Exception as e:
                falhas += 1
                print(f"Erro ao processar {numero}: {str(e)}")
            
            # Pequeno delay entre processos
            time.sleep(0.3)
        
        # Status final
        status_final = "Concluído" if falhas == 0 else "Concluído com falhas"
        
        yield {
            "status": status_final,
            "progresso": total,
            "processos": total,
            "sucesso": sucesso,
            "falhas": falhas,
            "arquivos": arquivos,
            "processo_atual": ""
        }
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com nome do assunto."""
        subject = self._state.get("selected_subject")
        subject_name = self._get_subject_name(subject)
        quantidade = self._get_subject_quantidade(subject)
        
        # Truncar nome se muito longo
        if len(subject_name) > 50:
            subject_name_display = subject_name[:50] + "..."
        else:
            subject_name_display = subject_name
        
        st.title(f"📚 Processando: {subject_name_display}")
        
        if quantidade > 0:
            st.caption(f"Total de processos: {quantidade}")
        
        st.markdown("---")
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        if not self._validate_params():
            st.error("Nenhum assunto selecionado")
            self._navigation.go_to_download_by_subject()
            return
        
        generator = self._get_generator()
        self._run_processing_loop(generator, "subject")