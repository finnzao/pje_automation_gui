import streamlit as st
from typing import List, Optional, Dict, Any, Union
import logging

from .base import BasePage
from ..config import PAGE_CONFIG, STATUS_CONFIG, APP_CONFIG

# Configurar logger para esta página
logger = logging.getLogger("pje.download_by_subject")


class DownloadBySubjectPage(BasePage):
    """
    Página de download por assunto principal.
    Fluxo em 3 etapas:
    1. Selecionar tarefas a ignorar
    2. Analisar assuntos dos processos (armazena dados completos para download direto)
    3. Selecionar assunto e baixar
    
    CORREÇÕES IMPLEMENTADAS:
    - Cache de tarefas na Etapa 1 (evita requisições desnecessárias)
    - Lógica de duplicatas usando idProcesso ao invés de numeroProcesso
    - Logging detalhado para debug
    - Dados completos armazenados para download direto
    """
    
    PAGE_TITLE = "Download por Assunto"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _extract_processo_data(self, processo) -> Dict[str, Any]:
        """
        Extrai todos os dados relevantes do processo para cache.
        Isso evita ter que buscar novamente no momento do download.
        
        IMPORTANTE: Armazena idProcesso que será usado para download direto.
        
        Campos importantes para download direto:
        - idProcesso: ID interno do processo (ESSENCIAL para download)
        - numeroProcesso: Número CNJ
        - idTaskInstance: ID da instância da tarefa
        - nomeTarefa: Nome da tarefa onde está
        - assuntoPrincipal: Assunto principal
        """
        data = {
            'numeroProcesso': None,
            'idProcesso': None,
            'idTaskInstance': None,
            'nomeTarefa': None,
            'assuntoPrincipal': None,
            'poloAtivo': None,
            'poloPassivo': None,
            'classeJudicial': None,
            'orgaoJulgador': None,
            'sigiloso': False,
            'prioridade': False,
            'ca': None,  # Chave de acesso se disponível
            '_raw': None,  # Dados brutos originais
        }
        
        # Se é dicionário (dados brutos da API)
        if isinstance(processo, dict):
            data['_raw'] = processo
            data['numeroProcesso'] = processo.get('numeroProcesso')
            data['idProcesso'] = processo.get('idProcesso')
            data['idTaskInstance'] = processo.get('idTaskInstance')
            data['nomeTarefa'] = processo.get('nomeTarefa')
            data['assuntoPrincipal'] = processo.get('assuntoPrincipal')
            data['poloAtivo'] = processo.get('poloAtivo')
            data['poloPassivo'] = processo.get('poloPassivo')
            data['classeJudicial'] = processo.get('classeJudicial')
            data['orgaoJulgador'] = processo.get('orgaoJulgador')
            data['sigiloso'] = processo.get('sigiloso', False)
            data['prioridade'] = processo.get('prioridade', False)
            return data
        
        # Se é objeto (ProcessoTarefa ou similar)
        field_mappings = {
            'numeroProcesso': ['numeroProcesso', 'numero_processo', 'numero'],
            'idProcesso': ['idProcesso', 'id_processo', 'id'],
            'idTaskInstance': ['idTaskInstance', 'id_task_instance', 'task_id'],
            'nomeTarefa': ['nomeTarefa', 'nome_tarefa', 'tarefa'],
            'assuntoPrincipal': ['assuntoPrincipal', 'assunto_principal', 'assunto'],
            'poloAtivo': ['poloAtivo', 'polo_ativo'],
            'poloPassivo': ['poloPassivo', 'polo_passivo'],
            'classeJudicial': ['classeJudicial', 'classe_judicial', 'classe'],
            'orgaoJulgador': ['orgaoJulgador', 'orgao_julgador'],
            'sigiloso': ['sigiloso'],
            'prioridade': ['prioridade'],
        }
        
        for target_field, source_fields in field_mappings.items():
            for source in source_fields:
                if hasattr(processo, source):
                    value = getattr(processo, source, None)
                    if value is not None:
                        data[target_field] = value
                        break
        
        # Tentar acessar dados raw se existirem
        raw_sources = ['_data', 'raw', 'data', '__dict__']
        for raw_attr in raw_sources:
            if hasattr(processo, raw_attr):
                raw = getattr(processo, raw_attr, None)
                if isinstance(raw, dict):
                    data['_raw'] = raw
                    # Preencher campos faltantes do raw
                    for target_field, source_fields in field_mappings.items():
                        if data[target_field] is None:
                            for source in source_fields:
                                if source in raw and raw[source] is not None:
                                    data[target_field] = raw[source]
                                    break
                    break
        
        return data
    
    def _get_assunto_from_processo_data(self, processo_data: Dict) -> str:
        """Obtém assunto do processo a partir dos dados extraídos."""
        assunto = processo_data.get('assuntoPrincipal')
        if assunto:
            return str(assunto)
        return "Sem assunto definido"
    
    def _get_numero_from_processo_data(self, processo_data: Dict) -> str:
        """Obtém número do processo a partir dos dados extraídos."""
        numero = processo_data.get('numeroProcesso')
        if numero:
            return str(numero)
        return ""
    
    def _get_id_from_processo_data(self, processo_data: Dict) -> Optional[int]:
        """Obtém idProcesso a partir dos dados extraídos."""
        id_proc = processo_data.get('idProcesso')
        if id_proc:
            try:
                return int(id_proc)
            except (ValueError, TypeError):
                return None
        return None
    
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
            return assunto.get('quantidade', len(assunto.get('processos', [])))
        if hasattr(assunto, 'quantidade'):
            qty = assunto.quantidade
            if callable(qty):
                return qty()
            return qty if qty is not None else 0
        if hasattr(assunto, 'processos'):
            return len(assunto.processos or [])
        return 0
    
    def _get_assunto_processos(self, assunto) -> List[Dict]:
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
            
            if st.button("🏠 Menu Principal", use_container_width=True):
                self._state.set("subject_step", 1)
                self._navigation.go_to_main_menu()
            
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
        # NÃO limpar cache de tarefas aqui para evitar requisições desnecessárias
    
    def _load_tasks(self, force_refresh: bool = False) -> List:
        """
        Carrega lista de tarefas disponíveis.
        
        CORREÇÃO: Usa cache do session_state para evitar requisições desnecessárias.
        Só faz nova requisição se force_refresh=True ou cache vazio.
        """
        cache_key = "subject_tasks_cache"
        
        # Verificar cache primeiro
        if not force_refresh:
            cached_tasks = self._state.get(cache_key, [])
            if cached_tasks:
                logger.debug(f"[LOAD_TASKS] Usando cache: {len(cached_tasks)} tarefas")
                return cached_tasks
        
        # Fazer requisição apenas se necessário
        logger.info("[LOAD_TASKS] Carregando tarefas da API...")
        
        try:
            client = self.session_service.client
            if hasattr(client, 'listar_tarefas_para_analise'):
                tasks = client.listar_tarefas_para_analise(force=True)
            else:
                tasks = client.listar_tarefas(force=True)
            
            tasks = tasks if tasks else []
            
            # Salvar no cache
            self._state.set(cache_key, tasks)
            logger.info(f"[LOAD_TASKS] Carregadas {len(tasks)} tarefas da API")
            
            return tasks
        except Exception as e:
            logger.error(f"[LOAD_TASKS] Erro ao carregar tarefas: {str(e)}")
            st.error(f"Erro ao carregar tarefas: {str(e)}")
            return []
    
    def _render_step1_select_tasks(self) -> None:
        """
        Etapa 1: Selecionar tarefas a ignorar.
        
        CORREÇÃO: Cache de tarefas para evitar requisições a cada checkbox.
        """
        st.header("Etapa 1: Selecionar Tarefas")
        st.markdown(
            "Selecione as tarefas que deseja **ignorar** na análise de assuntos. "
            "Tarefas favoritas são automaticamente ignoradas."
        )
        
        # Botão para forçar atualização
        col_refresh, col_spacer = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 Atualizar lista", key="refresh_tasks_btn"):
                self._state.set("subject_tasks_cache", [])
                st.rerun()
        
        # Carregar tarefas do cache ou API
        tasks = self._load_tasks(force_refresh=False)
        
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
        
        # Usar cache para tarefas ignoradas
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
        
        # Usar form para evitar reruns a cada checkbox
        with st.form(key="tasks_selection_form"):
            new_ignoradas = []
            
            for idx, task in enumerate(tasks_filtered):
                is_favorita = task.nome in nomes_favoritas
                is_ignored = task.nome in tarefas_ignoradas
                
                col1, col2 = st.columns([0.1, 0.9])
                
                with col1:
                    if is_favorita:
                        st.checkbox(
                            "Ignorar",
                            value=True,
                            disabled=True,
                            key=f"task_form_{idx}",
                            label_visibility="collapsed"
                        )
                    else:
                        checked = st.checkbox(
                            "Ignorar",
                            value=is_ignored,
                            key=f"task_form_{idx}",
                            label_visibility="collapsed"
                        )
                        if checked:
                            new_ignoradas.append(task.nome)
                
                with col2:
                    label = f"**{task.nome}**"
                    if is_favorita:
                        label += " ⭐ (favorita)"
                    if hasattr(task, 'quantidade_pendente') and task.quantidade_pendente:
                        label += f" ({task.quantidade_pendente} processos)"
                    st.markdown(label)
            
            # Botão de submissão do form
            submitted = st.form_submit_button("Confirmar seleção", use_container_width=True)
            
            if submitted:
                self._state.set("tarefas_ignoradas", new_ignoradas)
                st.rerun()
        
        st.markdown("---")
        
        total_ignoradas = len(tarefas_ignoradas) + len(nomes_favoritas)
        total_para_analisar = len(tasks) - total_ignoradas
        
        st.markdown(f"**Resumo:**")
        st.markdown(f"- Tarefas a ignorar: {len(tarefas_ignoradas)}")
        st.markdown(f"- Tarefas favoritas (ignoradas): {len(nomes_favoritas)}")
        st.markdown(f"- **Tarefas a analisar: {total_para_analisar}**")
        
        if total_para_analisar > 0:
            if st.button(
                "▶️ Próxima etapa: Analisar assuntos",
                type="primary",
                use_container_width=True,
                key="btn_next_step1"
            ):
                todas_ignoradas = list(set(tarefas_ignoradas + nomes_favoritas))
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
            "Clique no botão abaixo para analisar os processos e agrupar por assunto principal. "
            "**Os dados dos processos serão armazenados para download direto (sem busca adicional).**"
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
        """Executa a análise de assuntos armazenando dados completos."""
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        stats_container = st.empty()
        
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
            
            # Usar análise manual para armazenar dados completos
            assuntos = self._analyze_and_cache_data(update_progress, stats_container)
            
            progress_bar.progress(1.0)
            status_text.text("Análise concluída!")
            
            self._state.set("assuntos_analisados", assuntos if assuntos else [])
            
            if assuntos:
                total_processos = sum(a.get('quantidade', 0) for a in assuntos)
                st.success(f"✅ Encontrados {len(assuntos)} assuntos com {total_processos} processos!")
                st.info("💡 Dados dos processos armazenados para download direto (sem busca adicional)")
                self._state.set("subject_step", 3)
                st.rerun()
            else:
                st.warning("Nenhum assunto encontrado nos processos analisados.")
            
        except Exception as e:
            logger.error(f"[ANALYSIS] Erro durante análise: {str(e)}")
            st.error(f"Erro durante análise: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            progress_bar.empty()
            status_text.empty()
    
    def _analyze_and_cache_data(self, callback, stats_container=None) -> List[Dict]:
        """
        Análise que armazena dados completos dos processos.
        Isso permite download direto sem buscar novamente.
        
        CORREÇÕES:
        - Usa idProcesso para detectar duplicatas (não numeroProcesso)
        - Logging detalhado para debug
        - Mantém todos os processos mesmo com número duplicado se tiverem IDs diferentes
        """
        client = self.session_service.client
        tarefas_ignoradas = self._state.get("tarefas_ignoradas", [])
        
        # Obter todas as tarefas
        todas_tarefas = client.listar_tarefas(force=True)
        
        # Filtrar tarefas não ignoradas
        tarefas_para_analisar = [
            t for t in todas_tarefas 
            if t.nome not in tarefas_ignoradas
        ]
        
        logger.info(f"[ANALYSIS] Total de tarefas: {len(todas_tarefas)}")
        logger.info(f"[ANALYSIS] Tarefas ignoradas: {len(tarefas_ignoradas)}")
        logger.info(f"[ANALYSIS] Tarefas a analisar: {len(tarefas_para_analisar)}")
        
        # Dicionário para agrupar por assunto
        assuntos_dict: Dict[str, Dict] = {}
        
        # Estatísticas detalhadas
        stats = {
            'total_tarefas': len(tarefas_para_analisar),
            'tarefas_processadas': 0,
            'total_processos_encontrados': 0,
            'processos_com_id': 0,
            'processos_sem_id': 0,
            'processos_adicionados': 0,
            'processos_duplicados_por_id': 0,
            'processos_duplicados_por_numero': 0,
        }
        
        total_tarefas = len(tarefas_para_analisar)
        
        for idx, tarefa in enumerate(tarefas_para_analisar):
            callback(idx + 1, total_tarefas, f"Analisando tarefa: {tarefa.nome}")
            stats['tarefas_processadas'] = idx + 1
            
            logger.info(f"[ANALYSIS] [{idx+1}/{total_tarefas}] Tarefa: {tarefa.nome}")
            
            try:
                # Listar processos da tarefa
                processos = client.listar_processos_tarefa(tarefa.nome)
                
                logger.info(f"[ANALYSIS]   Processos retornados: {len(processos)}")
                
                for processo in processos:
                    stats['total_processos_encontrados'] += 1
                    
                    # Extrair TODOS os dados relevantes do processo
                    processo_data = self._extract_processo_data(processo)
                    
                    # Adicionar nome da tarefa se não veio nos dados
                    if not processo_data.get('nomeTarefa'):
                        processo_data['nomeTarefa'] = tarefa.nome
                    
                    # Obter identificadores
                    id_processo = self._get_id_from_processo_data(processo_data)
                    numero = self._get_numero_from_processo_data(processo_data)
                    assunto_nome = self._get_assunto_from_processo_data(processo_data)
                    
                    # Verificar se tem ID (importante para download direto)
                    if id_processo:
                        stats['processos_com_id'] += 1
                    else:
                        stats['processos_sem_id'] += 1
                        logger.warning(f"[ANALYSIS]   Processo sem ID: {numero}")
                    
                    # Criar entrada para o assunto se não existir
                    if assunto_nome not in assuntos_dict:
                        assuntos_dict[assunto_nome] = {
                            'nome': assunto_nome,
                            'processos': [],
                            'ids_vistos': set(),      # Para detectar duplicatas por ID
                            'numeros_vistos': set(),  # Para log de números duplicados
                            'quantidade': 0
                        }
                    
                    assunto_entry = assuntos_dict[assunto_nome]
                    
                    # CORREÇÃO: Usar idProcesso para detectar duplicatas (é mais confiável)
                    if id_processo:
                        if id_processo in assunto_entry['ids_vistos']:
                            stats['processos_duplicados_por_id'] += 1
                            logger.debug(f"[ANALYSIS]   Duplicata por ID: {id_processo} ({numero})")
                            continue
                        assunto_entry['ids_vistos'].add(id_processo)
                    else:
                        # Fallback: usar número se não tiver ID
                        if numero and numero in assunto_entry['numeros_vistos']:
                            stats['processos_duplicados_por_numero'] += 1
                            logger.debug(f"[ANALYSIS]   Duplicata por número: {numero}")
                            continue
                    
                    # Registrar número visto (para log)
                    if numero:
                        assunto_entry['numeros_vistos'].add(numero)
                    
                    # Adicionar processo
                    assunto_entry['processos'].append(processo_data)
                    assunto_entry['quantidade'] += 1
                    stats['processos_adicionados'] += 1
                    
            except Exception as e:
                logger.error(f"[ANALYSIS]   Erro ao analisar tarefa {tarefa.nome}: {str(e)}")
                st.warning(f"Erro ao analisar tarefa {tarefa.nome}: {str(e)}")
                continue
            
            # Atualizar estatísticas na UI
            if stats_container:
                with stats_container.container():
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Encontrados", stats['total_processos_encontrados'])
                    with col2:
                        st.metric("Adicionados", stats['processos_adicionados'])
                    with col3:
                        st.metric("Com ID", stats['processos_com_id'])
                    with col4:
                        st.metric("Assuntos", len(assuntos_dict))
        
        # Log final de estatísticas
        logger.info(f"[ANALYSIS] ===== ESTATÍSTICAS FINAIS =====")
        logger.info(f"[ANALYSIS] Total processos encontrados: {stats['total_processos_encontrados']}")
        logger.info(f"[ANALYSIS] Processos adicionados: {stats['processos_adicionados']}")
        logger.info(f"[ANALYSIS] Processos com ID: {stats['processos_com_id']}")
        logger.info(f"[ANALYSIS] Processos sem ID: {stats['processos_sem_id']}")
        logger.info(f"[ANALYSIS] Duplicatas por ID: {stats['processos_duplicados_por_id']}")
        logger.info(f"[ANALYSIS] Duplicatas por número: {stats['processos_duplicados_por_numero']}")
        logger.info(f"[ANALYSIS] Total assuntos: {len(assuntos_dict)}")
        
        # Remover sets antes de retornar (não são serializáveis)
        for assunto in assuntos_dict.values():
            del assunto['ids_vistos']
            del assunto['numeros_vistos']
        
        # Converter para lista e ordenar por quantidade
        assuntos_list = list(assuntos_dict.values())
        assuntos_list.sort(key=lambda x: x['quantidade'], reverse=True)
        
        return assuntos_list
    
    def _show_analysis_result(self, assuntos: List) -> None:
        """Mostra resultado da análise."""
        total_processos = sum(self._get_assunto_quantidade(a) for a in assuntos)
        
        # Contar processos com ID (prontos para download direto)
        processos_com_id = 0
        processos_sem_id = 0
        for assunto in assuntos:
            for proc in self._get_assunto_processos(assunto):
                if proc.get('idProcesso'):
                    processos_com_id += 1
                else:
                    processos_sem_id += 1
        
        st.success(f"✅ Análise concluída!")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Assuntos", len(assuntos))
        with col2:
            st.metric("Total de Processos", total_processos)
        with col3:
            st.metric("Com ID (direto)", processos_com_id)
        with col4:
            st.metric("Sem ID (busca)", processos_sem_id)
        
        if processos_com_id == total_processos:
            st.info("💡 Todos os processos têm ID - download será direto (sem busca adicional)")
        elif processos_com_id > 0:
            st.info(f"💡 {processos_com_id}/{total_processos} processos com download direto")
        
        if processos_sem_id > 0:
            st.warning(f"⚠️ {processos_sem_id} processos precisarão de busca (mais lento)")
        
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
                
                # Contar processos com ID
                processos = self._get_assunto_processos(assunto)
                com_id = sum(1 for p in processos if p.get('idProcesso'))
                
                with col1:
                    if len(nome) > 60:
                        nome_display = nome[:60] + "..."
                    else:
                        nome_display = nome
                    st.markdown(f"**{nome_display}**")
                
                with col2:
                    if com_id == quantidade:
                        st.markdown(f"📁 {quantidade} ✅")
                    else:
                        st.markdown(f"📁 {quantidade} ({com_id} ✅)")
                
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
        # Garantir que assunto é dicionário com dados completos
        if not isinstance(assunto, dict):
            assunto = {
                'nome': self._get_assunto_nome(assunto),
                'quantidade': self._get_assunto_quantidade(assunto),
                'processos': self._get_assunto_processos(assunto),
            }
        
        logger.info(f"[SELECT] Assunto selecionado: {assunto.get('nome')}")
        logger.info(f"[SELECT] Quantidade de processos: {assunto.get('quantidade')}")
        
        # Contar processos com ID
        processos = assunto.get('processos', [])
        com_id = sum(1 for p in processos if p.get('idProcesso'))
        logger.info(f"[SELECT] Processos com ID (download direto): {com_id}")
        
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