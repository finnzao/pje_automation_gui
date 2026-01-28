import streamlit as st
from typing import List, Optional, Dict, Any, Union

from .base import BasePage
from ..config import PAGE_CONFIG, STATUS_CONFIG, APP_CONFIG


class DownloadBySubjectPage(BasePage):
    """
    Página de download por assunto principal.
    Fluxo em 3 etapas:
    1. Selecionar tarefas a ignorar
    2. Analisar assuntos dos processos
    3. Selecionar assunto e baixar
    """
    
    PAGE_TITLE = "Download por Assunto"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _get_assunto_from_processo(self, processo) -> str:
        """
        Obtém o assunto principal de um processo.
        Tenta várias formas de acessar o campo.
        """
        # Lista de possíveis nomes do campo
        field_names = [
            'assuntoPrincipal',
            'assunto_principal', 
            'assunto',
            'subject',
        ]
        
        # Tentar como dicionário
        if isinstance(processo, dict):
            for field in field_names:
                if field in processo and processo[field]:
                    return str(processo[field])
            return "Sem assunto definido"
        
        # Tentar como objeto com atributos
        for field in field_names:
            if hasattr(processo, field):
                value = getattr(processo, field, None)
                if value:
                    return str(value)
        
        # Tentar acessar dados raw se existir
        if hasattr(processo, '_data') and isinstance(processo._data, dict):
            for field in field_names:
                if field in processo._data and processo._data[field]:
                    return str(processo._data[field])
        
        if hasattr(processo, 'raw') and isinstance(processo.raw, dict):
            for field in field_names:
                if field in processo.raw and processo.raw[field]:
                    return str(processo.raw[field])
        
        if hasattr(processo, 'data') and isinstance(processo.data, dict):
            for field in field_names:
                if field in processo.data and processo.data[field]:
                    return str(processo.data[field])
        
        # Tentar __dict__
        if hasattr(processo, '__dict__'):
            for field in field_names:
                if field in processo.__dict__ and processo.__dict__[field]:
                    return str(processo.__dict__[field])
        
        return "Sem assunto definido"
    
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
    
    def _get_assunto_nome(self, assunto) -> str:
        """Obtém nome do assunto de forma segura."""
        if isinstance(assunto, dict):
            return assunto.get('nome', 'Sem nome')
        elif hasattr(assunto, 'nome'):
            return assunto.nome or 'Sem nome'
        return str(assunto)
    
    def _get_assunto_quantidade(self, assunto) -> int:
        """Obtém quantidade de processos de um assunto de forma segura."""
        if isinstance(assunto, dict):
            if 'quantidade' in assunto:
                return assunto['quantidade']
            if 'processos' in assunto:
                return len(assunto['processos'])
            return 0
        
        if hasattr(assunto, 'quantidade'):
            qty = assunto.quantidade
            if callable(qty):
                return qty()
            return qty if qty is not None else 0
        
        if hasattr(assunto, 'processos'):
            processos = assunto.processos
            if isinstance(processos, list):
                return len(processos)
        
        return 0
    
    def _get_assunto_processos(self, assunto) -> List:
        """Obtém lista de processos de um assunto de forma segura."""
        if isinstance(assunto, dict):
            return assunto.get('processos', [])
        elif hasattr(assunto, 'processos'):
            return assunto.processos or []
        return []
    
    def _render_sidebar(self) -> None:
        """Renderiza sidebar com informações do fluxo."""
        with st.sidebar:
            st.subheader("📚 Download por Assunto")
            
            current_step = self._state.get("subject_step", 1)
            
            # Indicador de etapas
            steps = [
                ("1️⃣", "Selecionar tarefas", current_step >= 1),
                ("2️⃣", "Analisar assuntos", current_step >= 2),
                ("3️⃣", "Baixar processos", current_step >= 3),
            ]
            
            for icon, label, active in steps:
                if active and steps.index((icon, label, active)) + 1 == current_step:
                    st.markdown(f"**{icon} {label}** ← atual")
                elif active:
                    st.markdown(f"✅ {label}")
                else:
                    st.markdown(f"⬜ {label}")
            
            st.markdown("---")
            
            # Botão voltar
            if st.button("🏠 Menu Principal", use_container_width=True):
                self._state.set("subject_step", 1)
                self._navigation.go_to_main_menu()
            
            # Botão reiniciar
            if current_step > 1:
                if st.button("🔄 Reiniciar", use_container_width=True):
                    self._reset_flow()
                    st.rerun()
    
    def _reset_flow(self) -> None:
        """Reseta o fluxo para o início."""
        self._state.set("subject_step", 1)
        self._state.set("tarefas_ignoradas", [])
        self._state.set("assuntos_analisados", [])
        self._state.set("tarefas_para_analise", [])
        self._state.set("selected_subject", None)
    
    def _load_tasks(self) -> List:
        """Carrega lista de tarefas disponíveis."""
        try:
            client = self.session_service.client
            if hasattr(client, 'listar_tarefas_para_analise'):
                tasks = client.listar_tarefas_para_analise(force=True)
            else:
                tasks = client.listar_tarefas(force=True)
            return tasks if tasks else []
        except Exception as e:
            st.error(f"Erro ao carregar tarefas: {str(e)}")
            return []
    
    def _render_step1_select_tasks(self) -> None:
        """Etapa 1: Selecionar tarefas a ignorar."""
        st.header("Etapa 1: Selecionar Tarefas")
        st.markdown(
            "Selecione as tarefas que deseja **ignorar** na análise de assuntos. "
            "Tarefas favoritas são automaticamente ignoradas."
        )
        
        tasks = self._load_tasks()
        
        if not tasks:
            st.warning("Nenhuma tarefa encontrada.")
            return
        
        favoritas = self._state.get("tarefas_favoritas", [])
        nomes_favoritas = [t.nome for t in favoritas] if favoritas else []
        
        search_term = st.text_input(
            "🔍 Buscar tarefa",
            key="search_task_subject",
            placeholder="Digite para filtrar..."
        )
        
        if search_term:
            tasks_filtered = [
                t for t in tasks 
                if search_term.lower() in t.nome.lower()
            ]
        else:
            tasks_filtered = tasks
        
        tarefas_ignoradas = self._state.get("tarefas_ignoradas", [])
        
        st.markdown(f"**Total de tarefas:** {len(tasks_filtered)}")
        
        if nomes_favoritas:
            st.info(f"ℹ️ {len(nomes_favoritas)} tarefa(s) favorita(s) serão automaticamente ignoradas.")
        
        st.markdown("---")
        
        col_all, col_none = st.columns(2)
        
        with col_all:
            if st.button("Selecionar todas", key="select_all_tasks"):
                tarefas_ignoradas = [t.nome for t in tasks_filtered if t.nome not in nomes_favoritas]
                self._state.set("tarefas_ignoradas", tarefas_ignoradas)
                st.rerun()
        
        with col_none:
            if st.button("Desmarcar todas", key="deselect_all_tasks"):
                self._state.set("tarefas_ignoradas", [])
                st.rerun()
        
        st.markdown("---")
        
        new_ignoradas = []
        
        for idx, task in enumerate(tasks_filtered):
            is_favorita = task.nome in nomes_favoritas
            is_ignored = task.nome in tarefas_ignoradas
            
            col1, col2 = st.columns([0.1, 0.9])
            
            with col1:
                if is_favorita:
                    st.checkbox(
                        "Ignorar tarefa",
                        value=True,
                        disabled=True,
                        key=f"task_ignore_{idx}_{hash(task.nome)}",
                        label_visibility="collapsed"
                    )
                else:
                    checked = st.checkbox(
                        "Ignorar tarefa",
                        value=is_ignored,
                        key=f"task_ignore_{idx}_{hash(task.nome)}",
                        label_visibility="collapsed"
                    )
                    if checked:
                        new_ignoradas.append(task.nome)
            
            with col2:
                label = f"**{task.nome}**"
                if is_favorita:
                    label += " ⭐ (favorita)"
                if hasattr(task, 'quantidade') and task.quantidade:
                    label += f" ({task.quantidade} processos)"
                st.markdown(label)
        
        self._state.set("tarefas_ignoradas", new_ignoradas)
        
        st.markdown("---")
        
        total_ignoradas = len(new_ignoradas) + len(nomes_favoritas)
        total_para_analisar = len(tasks) - total_ignoradas
        
        st.markdown(f"**Resumo:**")
        st.markdown(f"- Tarefas a ignorar: {len(new_ignoradas)}")
        st.markdown(f"- Tarefas favoritas (ignoradas): {len(nomes_favoritas)}")
        st.markdown(f"- **Tarefas a analisar: {total_para_analisar}**")
        
        if total_para_analisar > 0:
            if st.button(
                "▶️ Próxima etapa: Analisar assuntos",
                type="primary",
                use_container_width=True,
                key="btn_next_step1"
            ):
                todas_ignoradas = list(set(new_ignoradas + nomes_favoritas))
                self._state.set("tarefas_ignoradas", todas_ignoradas)
                self._state.set("subject_step", 2)
                st.rerun()
        else:
            st.warning("Selecione pelo menos uma tarefa para analisar.")
    
    def _render_step2_analyze_subjects(self) -> None:
        """Etapa 2: Analisar assuntos dos processos."""
        st.header("Etapa 2: Analisar Assuntos")
        
        assuntos = self._state.get("assuntos_analisados", [])
        
        if assuntos:
            self._show_analysis_result(assuntos)
            return
        
        st.markdown(
            "Clique no botão abaixo para analisar os processos e agrupar por assunto principal."
        )
        
        tarefas_ignoradas = self._state.get("tarefas_ignoradas", [])
        st.info(f"ℹ️ {len(tarefas_ignoradas)} tarefa(s) serão ignoradas na análise.")
        
        if st.button(
            "🔍 Iniciar Análise",
            type="primary",
            use_container_width=True,
            key="btn_start_analysis"
        ):
            self._run_analysis()
    
    def _run_analysis(self) -> None:
        """Executa a análise de assuntos."""
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        debug_container = st.empty()
        
        progress_state = {"current": 0, "total": 1, "message": "Iniciando..."}
        
        def update_progress(*args, **kwargs):
            if len(args) >= 2:
                try:
                    current = int(args[0]) if args[0] is not None else 0
                    total = int(args[1]) if args[1] is not None else 1
                    message = str(args[2]) if len(args) > 2 else f"Analisando... {current}/{total}"
                except (ValueError, TypeError):
                    current = progress_state["current"]
                    total = progress_state["total"]
                    message = str(args[0]) if args else progress_state["message"]
            elif len(args) == 1:
                if isinstance(args[0], dict):
                    current = args[0].get("current", progress_state["current"])
                    total = args[0].get("total", progress_state["total"])
                    message = args[0].get("message", progress_state["message"])
                else:
                    current = progress_state["current"]
                    total = progress_state["total"]
                    message = str(args[0])
            else:
                current = kwargs.get("current", progress_state["current"])
                total = kwargs.get("total", progress_state["total"])
                message = kwargs.get("message", progress_state["message"])
            
            progress_state["current"] = current
            progress_state["total"] = max(total, 1)
            progress_state["message"] = message
            
            progress_value = min(current / progress_state["total"], 1.0)
            progress_bar.progress(progress_value)
            status_text.text(message)
        
        try:
            client = self.session_service.client
            tarefas_ignoradas = self._state.get("tarefas_ignoradas", [])
            
            if hasattr(client, 'definir_tarefas_ignoradas'):
                client.definir_tarefas_ignoradas(tarefas_ignoradas)
            
            status_text.text("Iniciando análise de assuntos...")
            
            # Sempre usar análise manual para garantir que pegamos o campo correto
            assuntos = self._analyze_manually(update_progress, debug_container)
            
            progress_bar.progress(1.0)
            status_text.text("Análise concluída!")
            
            self._state.set("assuntos_analisados", assuntos if assuntos else [])
            
            if assuntos:
                st.success(f"✅ Encontrados {len(assuntos)} assuntos distintos!")
                self._state.set("subject_step", 3)
                st.rerun()
            else:
                st.warning("Nenhum assunto encontrado nos processos analisados.")
            
        except Exception as e:
            st.error(f"Erro durante análise: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            progress_bar.empty()
            status_text.empty()
    
    def _analyze_manually(self, callback, debug_container=None) -> List[Dict]:
        """Análise manual buscando assuntoPrincipal dos processos."""
        client = self.session_service.client
        tarefas_ignoradas = self._state.get("tarefas_ignoradas", [])
        
        # Obter todas as tarefas
        todas_tarefas = client.listar_tarefas(force=True)
        
        # Filtrar tarefas não ignoradas
        tarefas_para_analisar = [
            t for t in todas_tarefas 
            if t.nome not in tarefas_ignoradas
        ]
        
        # Dicionário para agrupar por assunto
        assuntos_dict: Dict[str, Dict] = {}
        
        # Para debug
        debug_info = []
        processos_sem_assunto = 0
        total_processos = 0
        
        total_tarefas = len(tarefas_para_analisar)
        
        for idx, tarefa in enumerate(tarefas_para_analisar):
            callback(idx + 1, total_tarefas, f"Analisando tarefa: {tarefa.nome}")
            
            try:
                # Listar processos da tarefa
                processos = client.listar_processos_tarefa(tarefa.nome)
                
                for processo in processos:
                    total_processos += 1
                    
                    # Obter assunto principal usando o método robusto
                    assunto_nome = self._get_assunto_from_processo(processo)
                    
                    # Debug: guardar info do primeiro processo
                    if len(debug_info) < 3:
                        debug_info.append({
                            'numero': self._get_numero_processo(processo),
                            'assunto': assunto_nome,
                            'tipo': type(processo).__name__,
                            'attrs': dir(processo) if hasattr(processo, '__dir__') else 'N/A'
                        })
                    
                    if assunto_nome == "Sem assunto definido":
                        processos_sem_assunto += 1
                    
                    # Obter número do processo
                    numero = self._get_numero_processo(processo)
                    
                    # Adicionar ao dicionário
                    if assunto_nome not in assuntos_dict:
                        assuntos_dict[assunto_nome] = {
                            'nome': assunto_nome,
                            'processos': [],
                            'numeros': set(),  # Para evitar duplicatas
                            'quantidade': 0
                        }
                    
                    # Verificar duplicatas
                    if numero not in assuntos_dict[assunto_nome]['numeros']:
                        assuntos_dict[assunto_nome]['processos'].append(processo)
                        assuntos_dict[assunto_nome]['numeros'].add(numero)
                        assuntos_dict[assunto_nome]['quantidade'] += 1
                    
            except Exception as e:
                st.warning(f"Erro ao analisar tarefa {tarefa.nome}: {str(e)}")
                continue
        
        # Mostrar debug se houver problemas
        if debug_container and processos_sem_assunto > 0:
            with debug_container.expander("🔍 Debug - Informações dos processos", expanded=False):
                st.write(f"Total de processos analisados: {total_processos}")
                st.write(f"Processos sem assunto: {processos_sem_assunto}")
                if debug_info:
                    st.write("Amostra de processos:")
                    for info in debug_info:
                        st.json(info)
        
        # Remover set de numeros antes de retornar (não é serializável)
        for assunto in assuntos_dict.values():
            del assunto['numeros']
        
        # Converter para lista e ordenar por quantidade
        assuntos_list = list(assuntos_dict.values())
        assuntos_list.sort(key=lambda x: x['quantidade'], reverse=True)
        
        return assuntos_list
    
    def _show_analysis_result(self, assuntos: List) -> None:
        """Mostra resultado da análise."""
        total_processos = sum(self._get_assunto_quantidade(a) for a in assuntos)
        
        st.success(f"✅ Análise concluída!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Assuntos", len(assuntos))
        with col2:
            st.metric("Total de Processos", total_processos)
        
        st.markdown("---")
        
        if st.button(
            "▶️ Próxima etapa: Selecionar assunto",
            type="primary",
            use_container_width=True,
            key="btn_next_step2"
        ):
            self._state.set("subject_step", 3)
            st.rerun()
        
        if st.button(
            "🔄 Refazer análise",
            use_container_width=True,
            key="btn_redo_analysis"
        ):
            self._state.set("assuntos_analisados", [])
            st.rerun()
    
    def _render_step3_select_subject(self) -> None:
        """Etapa 3: Selecionar assunto e baixar."""
        st.header("Etapa 3: Selecionar Assunto")
        
        assuntos = self._state.get("assuntos_analisados", [])
        
        if not assuntos:
            st.warning("Nenhum assunto analisado. Volte para a etapa anterior.")
            if st.button("← Voltar", key="btn_back_step3"):
                self._state.set("subject_step", 2)
                st.rerun()
            return
        
        total_processos = sum(self._get_assunto_quantidade(a) for a in assuntos)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Assuntos", len(assuntos))
        with col2:
            st.metric("Total de Processos", total_processos)
        
        st.markdown("---")
        
        search_term = st.text_input(
            "🔍 Buscar assunto",
            key="search_subject",
            placeholder="Digite para filtrar..."
        )
        
        if search_term:
            assuntos_filtered = [
                a for a in assuntos 
                if search_term.lower() in self._get_assunto_nome(a).lower()
            ]
        else:
            assuntos_filtered = assuntos
        
        st.markdown(f"**Exibindo:** {len(assuntos_filtered)} assuntos")
        
        st.markdown("---")
        
        MAX_DISPLAY = 50
        if len(assuntos_filtered) > MAX_DISPLAY:
            st.info(f"ℹ️ Exibindo apenas os {MAX_DISPLAY} primeiros. Use a busca para encontrar outros.")
            assuntos_display = assuntos_filtered[:MAX_DISPLAY]
        else:
            assuntos_display = assuntos_filtered
        
        for idx, assunto in enumerate(assuntos_display):
            with st.container():
                col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
                
                nome = self._get_assunto_nome(assunto)
                quantidade = self._get_assunto_quantidade(assunto)
                
                with col1:
                    if len(nome) > 60:
                        nome_display = nome[:60] + "..."
                    else:
                        nome_display = nome
                    st.markdown(f"**{nome_display}**")
                
                with col2:
                    st.markdown(f"📁 {quantidade} processos")
                
                with col3:
                    if st.button(
                        "⬇️ Baixar",
                        key=f"btn_download_{idx}_{hash(nome)}",
                        use_container_width=True
                    ):
                        self._handle_subject_selection(assunto)
                
                st.markdown("---")
    
    def _handle_subject_selection(self, assunto) -> None:
        """Processa a seleção de um assunto para download."""
        # Garantir que assunto é dicionário
        if not isinstance(assunto, dict):
            assunto = {
                'nome': self._get_assunto_nome(assunto),
                'quantidade': self._get_assunto_quantidade(assunto),
                'processos': self._get_assunto_processos(assunto),
            }
        
        st.session_state["selected_subject"] = assunto
        st.session_state["subject_limit"] = 0
        st.session_state["subject_tamanho_lote"] = APP_CONFIG.DEFAULT_BATCH_SIZE
        
        self._navigation.go_to_processing_subject(
            assunto=assunto,
            limit=0,
            batch_size=APP_CONFIG.DEFAULT_BATCH_SIZE
        )
    
    def _render_content(self) -> None:
        """Renderiza conteúdo baseado na etapa atual."""
        current_step = self._state.get("subject_step", 1)
        
        if current_step == 1:
            self._render_step1_select_tasks()
        elif current_step == 2:
            self._render_step2_analyze_subjects()
        elif current_step == 3:
            self._render_step3_select_subject()
        else:
            self._state.set("subject_step", 1)
            st.rerun()