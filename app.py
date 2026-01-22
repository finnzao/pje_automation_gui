import streamlit as st

st.set_page_config(
    page_title="PJE Download Manager",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import time
import os
import subprocess
import platform
import json
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List

os.environ['PYTHONUNBUFFERED'] = '1'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(Path(__file__).parent))

from pje_lib import PJEClient
from pje_lib.models import Perfil, Tarefa, Etiqueta
from ui.credential_manager import CredentialManager, PreferencesManager

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton > button {
        border-radius: 4px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }
    .stProgress > div > div > div {
        background-color: #1f77b4;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .status-success {
        background-color: #d4edda;
        color: #155724;
    }
    .status-warning {
        background-color: #fff3cd;
        color: #856404;
    }
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
    }
    .status-info {
        background-color: #d1ecf1;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    defaults = {
        'page': 'login',
        'logged_in': False,
        'user_name': None,
        'perfil_selecionado': None,
        'perfis': [],
        'tarefas': [],
        'tarefas_favoritas': [],
        'pje_client': None,
        'relatorio': None,
        'download_dir': './downloads',
        'cancelamento_solicitado': False,
        'show_cancel_confirm': False,
        'perfil_sendo_selecionado': False,
        'processing_iteration': 0,  # Contador para chaves únicas
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_pje_client() -> Optional[PJEClient]:
    if st.session_state.pje_client is None:
        st.session_state.pje_client = PJEClient(
            download_dir=st.session_state.download_dir,
            debug=True
        )
    return st.session_state.pje_client


def verificar_sessao_ou_redirecionar():
    """Verifica saúde da sessão de forma OTIMIZADA - usa cache"""
    pje = get_pje_client()
    
    if not pje or not pje.usuario:
        st.error("Sessão expirada. Redirecionando para login...")
        time.sleep(1)
        limpar_sessao_completa()
        return False
    
    if hasattr(pje._auth, 'validar_saude_sessao_rapida'):
        if not pje._auth.validar_saude_sessao_rapida():
            st.error("Sessão corrompida detectada. Fazendo logout...")
            time.sleep(1)
            limpar_sessao_completa()
            return False
    
    return True

def limpar_sessao_completa():
    """Limpa completamente a sessão e volta para login"""
    if st.session_state.pje_client:
        try:
            st.session_state.pje_client.close()
        except:
            pass
    
    # Limpar diretórios
    pastas_para_limpar = ['.config', '.session']
    for pasta in pastas_para_limpar:
        pasta_path = Path(pasta)
        if pasta_path.exists():
            try:
                shutil.rmtree(pasta_path)
            except:
                pass
    
    # Recriar diretórios vazios
    for pasta in pastas_para_limpar:
        Path(pasta).mkdir(parents=True, exist_ok=True)
    
    # Limpar session_state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Reinicializar
    init_session_state()
    st.session_state.page = 'login'
    st.rerun()


def open_folder(path: str):
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def get_status_text(status: str) -> str:
    texts = {
        "iniciando": "Iniciando",
        "buscando_tarefa": "Buscando tarefa",
        "buscando_etiqueta": "Buscando etiqueta",
        "buscando_processo": "Buscando processo",
        "listando_processos": "Listando processos",
        "processando": "Processando",
        "baixando_lote": "Baixando arquivos",
        "aguardando_downloads": "Aguardando downloads",
        "verificando_integridade": "Verificando integridade",
        "retry_1": "Tentativa 1/2",
        "retry_2": "Tentativa 2/2",
        "concluido": "Concluído",
        "concluido_com_falhas": "Concluído com falhas",
        "cancelado": "Cancelado",
        "erro": "Erro"
    }
    return texts.get(status, status)


def get_status_badge(status: str) -> str:
    """Retorna HTML para badge de status"""
    badges = {
        "concluido": '<span class="status-badge status-success">Concluído</span>',
        "concluido_com_falhas": '<span class="status-badge status-warning">Concluído com falhas</span>',
        "cancelado": '<span class="status-badge status-error">Cancelado</span>',
        "erro": '<span class="status-badge status-error">Erro</span>',
        "processando": '<span class="status-badge status-info">Processando</span>',
    }
    return badges.get(status, f'<span class="status-badge status-info">{get_status_text(status)}</span>')


def validar_numero_processo(numero: str) -> bool:
    numero = numero.strip()
    padrao = r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$'
    return bool(re.match(padrao, numero))


def formatar_numero_processo(numero: str) -> Optional[str]:
    apenas_numeros = re.sub(r'[^\d]', '', numero)
    if len(apenas_numeros) != 20:
        return None
    return f"{apenas_numeros[:7]}-{apenas_numeros[7:9]}.{apenas_numeros[9:13]}.{apenas_numeros[13]}.{apenas_numeros[14:16]}.{apenas_numeros[16:20]}"


def page_login():
    st.title("PJE Download Manager")
    st.caption("Sistema de download automatizado de processos judiciais")
    
    st.markdown("---")
    
    cred_manager = CredentialManager()
    saved_user, saved_pass = cred_manager.load_credentials()
    has_saved = saved_user is not None and saved_pass is not None
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if has_saved:
            st.info(f"Credenciais salvas para: {saved_user}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Entrar com credenciais salvas", use_container_width=True, type="primary", key="btn_login_saved"):
                    do_login(saved_user, saved_pass)
            with c2:
                if st.button("Limpar credenciais", use_container_width=True, key="btn_clear_cred"):
                    cred_manager.clear_credentials()
                    st.rerun()
            st.markdown("---")
        
        with st.form("login_form", clear_on_submit=False):
            st.subheader("Login")
            username = st.text_input("CPF", value=saved_user or "", placeholder="Digite seu CPF")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            save_cred = st.checkbox("Salvar credenciais neste computador", value=has_saved)
            
            submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")
            
            if submit:
                if not username or not password:
                    st.error("Por favor, preencha CPF e senha")
                else:
                    if save_cred:
                        cred_manager.save_credentials(username, password)
                    do_login(username, password)


def do_login(username: str, password: str):
    with st.spinner("Autenticando..."):
        try:
            pje = get_pje_client()
            if pje.login(username, password, validar_saude=True):
                st.session_state.logged_in = True
                st.session_state.user_name = pje.usuario.nome if pje.usuario else username
                st.session_state.page = 'select_profile'
                st.success("Login realizado com sucesso!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Falha na autenticação. Verifique suas credenciais e tente novamente.")
        except Exception as e:
            st.error(f"Erro ao conectar: {str(e)}")


def page_select_profile():
    if not verificar_sessao_ou_redirecionar():
        return
    
    st.title("Selecionar Perfil")
    st.caption(f"Usuário: {st.session_state.user_name}")
    
    st.markdown("---")
    
    pje = get_pje_client()
    
    # Barra de ações
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        if st.button("Atualizar lista", use_container_width=True, key="btn_refresh_profiles"):
            st.session_state.perfis = []
            st.rerun()
    
    with col2:
        if st.button("Verificar sessão", use_container_width=True, key="btn_check_session_profile"):
            with st.spinner("Verificando..."):
                if hasattr(pje._auth, 'validar_saude_sessao'):
                    if pje._auth.validar_saude_sessao():
                        st.success("Sessão válida")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Sessão inválida")
                        time.sleep(1)
                        limpar_sessao_completa()
    
    # Carregar perfis
    if not st.session_state.perfis:
        with st.spinner("Carregando perfis..."):
            st.session_state.perfis = pje.listar_perfis()
            
            if not st.session_state.perfis:
                st.error("Nenhum perfil encontrado")
                st.warning("Isso pode indicar que sua sessão está corrompida.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Tentar novamente", type="primary", use_container_width=True, key="btn_retry_profiles"):
                        limpar_sessao_completa()
                
                with col2:
                    if st.button("Sair", use_container_width=True, key="btn_exit_profiles"):
                        limpar_sessao_completa()
                
                return
    
    perfis = st.session_state.perfis
    
    st.info(f"Encontrados {len(perfis)} perfil(is) disponível(is)")
    
    # Busca
    busca_perfil = st.text_input("Filtrar perfis", placeholder="Digite para buscar...", key="input_filter_profiles")
    
    if busca_perfil:
        perfis_filtrados = [p for p in perfis if busca_perfil.lower() in p.nome_completo.lower()]
    else:
        perfis_filtrados = perfis
    
    st.markdown("---")
    
    # Lista de perfis - SEM DUPLICAÇÃO
    if not st.session_state.get('perfil_sendo_selecionado', False):
        for perfil in perfis_filtrados:
            col1, col2 = st.columns([4, 1])
            
            with col1:
                nome_display = f"**{perfil.nome}**"
                detalhes = []
                if perfil.orgao:
                    detalhes.append(perfil.orgao)
                if perfil.cargo:
                    detalhes.append(perfil.cargo)
                if detalhes:
                    nome_display += f" - {' / '.join(detalhes)}"
                if hasattr(perfil, 'favorito') and perfil.favorito:
                    nome_display += " ★"
                st.markdown(nome_display)
            
            with col2:
                if st.button("Selecionar", key=f"perfil_{perfil.index}_{perfil.nome[:10]}", use_container_width=True):
                    st.session_state.perfil_sendo_selecionado = True
                    with st.spinner(f"Selecionando {perfil.nome}..."):
                        if pje.select_profile_by_index(perfil.index):
                            st.session_state.perfil_selecionado = perfil
                            st.session_state.tarefas = []
                            st.session_state.tarefas_favoritas = []
                            st.session_state.perfil_sendo_selecionado = False
                            st.session_state.page = 'main_menu'
                            st.success(f"Perfil selecionado: {perfil.nome}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.session_state.perfil_sendo_selecionado = False
                            st.error(f"Erro ao selecionar perfil")
            
            st.markdown("---")
    else:
        st.info("Selecionando perfil, aguarde...")
    
    # Botão de sair
    if st.button("Sair do sistema", use_container_width=True, key="btn_logout_profile"):
        limpar_sessao_completa()


def page_main_menu():
    if not verificar_sessao_ou_redirecionar():
        return
    
    perfil = st.session_state.perfil_selecionado
    
    st.title("Menu Principal")
    st.caption(f"Usuário: {st.session_state.user_name} | Perfil: {perfil.nome if perfil else 'Não selecionado'}")
    
    st.markdown("---")
    
    # Cards de opções
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Download por Tarefa")
        st.markdown("Baixar processos vinculados a uma tarefa específica do sistema")
        if st.button("Acessar", key="btn_task", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_task'
            st.rerun()
    
    with col2:
        st.subheader("Download por Etiqueta")
        st.markdown("Baixar processos marcados com uma etiqueta específica")
        if st.button("Acessar", key="btn_tag", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_tag'
            st.rerun()
    
    with col3:
        st.subheader("Download por Número")
        st.markdown("Baixar processo(s) informando o número CNJ completo")
        if st.button("Acessar", key="btn_numero", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_number'
            st.rerun()
    
    st.markdown("---")
    
    # Seção de ações
    st.subheader("Ações")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Trocar perfil", use_container_width=True, key="btn_change_profile"):
            st.session_state.tarefas = []
            st.session_state.tarefas_favoritas = []
            st.session_state.page = 'select_profile'
            st.rerun()
    
    with col2:
        if st.button("Abrir pasta de downloads", use_container_width=True, key="btn_open_downloads"):
            open_folder(st.session_state.download_dir)
    
    with col3:
        if st.button("Verificar sessão", use_container_width=True, key="btn_check_session_main"):
            pje = get_pje_client()
            if hasattr(pje._auth, 'validar_saude_sessao'):
                with st.spinner("Verificando..."):
                    if pje._auth.validar_saude_sessao():
                        st.success("Sessão válida")
                    else:
                        st.error("Sessão corrompida. Fazendo logout...")
                        time.sleep(1)
                        limpar_sessao_completa()
    
    with col4:
        if st.button("Sair do sistema", use_container_width=True, key="btn_logout_main"):
            limpar_sessao_completa()


def page_download_by_task():
    if not verificar_sessao_ou_redirecionar():
        return
    
    st.title("Download por Tarefa")
    
    pje = get_pje_client()
    
    with st.sidebar:
        st.header("Configurações")
        usar_favoritas = st.checkbox("Apenas tarefas favoritas", key="chk_favoritas")
        limite = st.number_input("Limite de processos (0 = todos)", min_value=0, max_value=500, value=0, key="input_limite_task")
        tamanho_lote = st.slider("Tamanho do lote de download", 5, 30, 10, key="slider_lote_task")
        
        st.markdown("---")
        
        if st.button("Atualizar lista de tarefas", use_container_width=True, key="btn_refresh_tasks"):
            st.session_state.tarefas = []
            st.session_state.tarefas_favoritas = []
            st.rerun()
        
        st.markdown("---")
        
        if st.button("Voltar ao menu", use_container_width=True, key="btn_back_task"):
            st.session_state.page = 'main_menu'
            st.rerun()
    
    # Carregar tarefas
    if usar_favoritas:
        if not st.session_state.tarefas_favoritas:
            with st.spinner("Carregando tarefas favoritas..."):
                st.session_state.tarefas_favoritas = pje.listar_tarefas_favoritas(force=True)
        tarefas = st.session_state.tarefas_favoritas
    else:
        if not st.session_state.tarefas:
            with st.spinner("Carregando tarefas..."):
                st.session_state.tarefas = pje.listar_tarefas(force=True)
        tarefas = st.session_state.tarefas
    
    if not tarefas:
        st.warning("Nenhuma tarefa encontrada para este perfil")
        return
    
    st.info(f"Total: {len(tarefas)} tarefa(s)")
    
    # Busca
    busca = st.text_input("Filtrar tarefas", placeholder="Digite para buscar...", key="input_filter_tasks")
    tarefas_filtradas = [t for t in tarefas if busca.lower() in t.nome.lower()] if busca else tarefas
    
    st.markdown("---")
    
    # Lista de tarefas
    for idx, tarefa in enumerate(tarefas_filtradas):
        col1, col2, col3 = st.columns([5, 1, 1])
        
        with col1:
            st.markdown(f"**{tarefa.nome}**")
        
        with col2:
            st.caption(f"{tarefa.quantidade_pendente} pendente(s)")
        
        with col3:
            if st.button("Baixar", key=f"tarefa_{idx}_{tarefa.id}", use_container_width=True):
                st.session_state.selected_task = tarefa
                st.session_state.task_limit = limite if limite > 0 else None
                st.session_state.task_usar_favoritas = usar_favoritas
                st.session_state.task_tamanho_lote = tamanho_lote
                st.session_state.cancelamento_solicitado = False
                st.session_state.show_cancel_confirm = False
                st.session_state.processing_iteration = 0
                st.session_state.page = 'processing_task'
                st.rerun()
        
        st.markdown("---")


def page_download_by_tag():
    if not verificar_sessao_ou_redirecionar():
        return
    
    st.title("Download por Etiqueta")
    
    pje = get_pje_client()
    
    with st.sidebar:
        st.header("Configurações")
        limite = st.number_input("Limite de processos (0 = todos)", min_value=0, max_value=500, value=0, key="input_limite_tag")
        tamanho_lote = st.slider("Tamanho do lote de download", 5, 30, 10, key="slider_lote_tag")
        
        st.markdown("---")
        
        if st.button("Voltar ao menu", use_container_width=True, key="btn_back_tag"):
            st.session_state.page = 'main_menu'
            st.rerun()
    
    # Busca de etiquetas
    busca = st.text_input("Nome da etiqueta", placeholder="Digite o nome da etiqueta...", key="input_search_tag")
    
    if busca:
        with st.spinner("Buscando etiquetas..."):
            etiquetas = pje.buscar_etiquetas(busca)
        
        # Remover duplicadas
        etiquetas_unicas = []
        ids_vistos = set()
        for et in etiquetas:
            if et.id not in ids_vistos:
                etiquetas_unicas.append(et)
                ids_vistos.add(et.id)
        etiquetas = etiquetas_unicas
        
        if etiquetas:
            st.info(f"Encontradas {len(etiquetas)} etiqueta(s)")
            st.markdown("---")
            
            for idx, etiqueta in enumerate(etiquetas):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.markdown(f"**{etiqueta.nome}**")
                
                with col2:
                    if st.button("Baixar", key=f"etiqueta_{idx}_{etiqueta.id}", use_container_width=True):
                        st.session_state.selected_tag = etiqueta
                        st.session_state.tag_limit = limite if limite > 0 else None
                        st.session_state.tag_tamanho_lote = tamanho_lote
                        st.session_state.cancelamento_solicitado = False
                        st.session_state.show_cancel_confirm = False
                        st.session_state.processing_iteration = 0
                        st.session_state.page = 'processing_tag'
                        st.rerun()
                
                st.markdown("---")
        else:
            st.warning(f"Nenhuma etiqueta encontrada para: '{busca}'")
    else:
        st.info("Digite o nome de uma etiqueta para buscar")


def page_download_by_number():
    if not verificar_sessao_ou_redirecionar():
        return
    
    st.title("Download por Número de Processo")
    
    with st.sidebar:
        st.header("Configurações")
        tipo_documento = st.selectbox(
            "Tipo de documento",
            ["Selecione", "Petição Inicial", "Petição", "Sentença", "Decisão", "Despacho", "Acórdão", "Outros documentos"],
            index=0,
            key="select_tipo_doc"
        )
        
        st.markdown("---")
        
        if st.button("Voltar ao menu", use_container_width=True, key="btn_back_number"):
            st.session_state.page = 'main_menu'
            st.rerun()
    
    st.markdown("""
    ### Instruções
    
    Digite os números dos processos que deseja baixar, um por linha.
    
    **Formatos aceitos:**
    - Com formatação: `0000001-23.2024.8.05.0001`
    - Sem formatação: `00000012320248050001`
    
    **Observação:** Os processos devem estar acessíveis no seu perfil atual.
    """)
    
    numeros_input = st.text_area(
        "Números dos processos",
        placeholder="0000001-23.2024.8.05.0001\n0000002-45.2024.8.05.0001",
        height=150,
        key="textarea_numeros"
    )
    
    if numeros_input:
        linhas = [l.strip() for l in numeros_input.strip().split('\n') if l.strip()]
        processos_validos = []
        processos_invalidos = []
        
        for linha in linhas:
            numero_formatado = formatar_numero_processo(linha)
            if numero_formatado:
                processos_validos.append(numero_formatado)
            elif validar_numero_processo(linha):
                processos_validos.append(linha)
            else:
                processos_invalidos.append(linha)
        
        # Remover duplicados
        processos_validos = list(dict.fromkeys(processos_validos))
        
        # Mostrar estatísticas
        col1, col2 = st.columns(2)
        with col1:
            if processos_validos:
                st.success(f"Válidos: {len(processos_validos)}")
        with col2:
            if processos_invalidos:
                st.error(f"Inválidos: {len(processos_invalidos)}")
        
        if processos_validos:
            with st.expander("Ver processos válidos"):
                for p in processos_validos:
                    st.code(p)
            
            st.markdown("---")
            
            if st.button("Iniciar download", type="primary", use_container_width=True, key="btn_start_number"):
                st.session_state.processos_para_baixar = processos_validos
                st.session_state.tipo_documento_numero = tipo_documento
                st.session_state.cancelamento_solicitado = False
                st.session_state.show_cancel_confirm = False
                st.session_state.processing_iteration = 0
                st.session_state.page = 'processing_number'
                st.rerun()
    else:
        st.info("Digite pelo menos um número de processo para continuar")


def render_processing_page(generator, title, back_page, processing_type):
    """Template comum para páginas de processamento"""
    
    st.title(title)
    
    # Usar processing_type para criar chaves únicas
    key_prefix = f"{processing_type}_{st.session_state.get('processing_iteration', 0)}"
    
    status_container = st.empty()
    progress_bar = st.progress(0)
    processo_container = st.empty()
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    metric_total = col1.empty()
    metric_prog = col2.empty()
    metric_ok = col3.empty()
    metric_files = col4.empty()
    
    st.markdown("---")
    
    # Detalhes
    details_container = st.empty()
    
    st.markdown("---")
    
    # Controle de cancelamento - FORA DO LOOP para evitar duplicação
    cancel_placeholder = st.empty()
    
    pje = get_pje_client()
    tempo_inicio = time.time()
    iteration = 0
    
    try:
        for estado in generator:
            iteration += 1
            status = estado.get('status', '')
            progresso = estado.get('progresso', 0)
            total = estado.get('processos', 0)
            proc_atual = estado.get('processo_atual', '')
            
            # Status
            status_html = get_status_badge(status)
            status_container.markdown(status_html, unsafe_allow_html=True)
            
            # Progresso
            if total > 0:
                progress_bar.progress(min(progresso / total, 1.0))
            
            # Processo atual
            if proc_atual:
                processo_container.caption(f"Processando: {proc_atual}")
            else:
                processo_container.empty()
            
            # Métricas
            metric_total.metric("Total", total)
            metric_prog.metric("Progresso", f"{progresso}/{total}")
            metric_ok.metric("Sucesso", estado.get('sucesso', 0))
            metric_files.metric("Arquivos", len(estado.get('arquivos', [])))
            
            # Detalhes de tempo
            tempo_decorrido = int(time.time() - tempo_inicio)
            mins, secs = divmod(tempo_decorrido, 60)
            
            with details_container.container():
                cols = st.columns(3)
                cols[0].metric("Tempo decorrido", f"{mins}m {secs}s")
                
                if progresso > 0 and total > 0:
                    tempo_por_processo = tempo_decorrido / progresso
                    tempo_restante = int((total - progresso) * tempo_por_processo)
                    mins_rest, secs_rest = divmod(tempo_restante, 60)
                    cols[1].metric("Tempo estimado", f"{mins_rest}m {secs_rest}s")
                
                taxa_sucesso = (estado.get('sucesso', 0) / progresso * 100) if progresso > 0 else 0
                cols[2].metric("Taxa de sucesso", f"{taxa_sucesso:.1f}%")
            
            # Controle de cancelamento com chaves únicas baseadas na iteração
            with cancel_placeholder.container():
                if st.session_state.get('cancelamento_solicitado', False):
                    st.error("Cancelamento solicitado. Aguarde a interrupção...")
                elif st.session_state.get('show_cancel_confirm', False):
                    st.warning("Confirmar cancelamento?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Sim, cancelar", type="primary", use_container_width=True, 
                                   key=f"{key_prefix}_confirm_cancel_{iteration}"):
                            st.session_state.cancelamento_solicitado = True
                            st.session_state.show_cancel_confirm = False
                            pje.cancelar_processamento()
                            st.rerun()
                    with col2:
                        if st.button("Não, continuar", use_container_width=True, 
                                   key=f"{key_prefix}_deny_cancel_{iteration}"):
                            st.session_state.show_cancel_confirm = False
                            st.rerun()
                else:
                    if st.button("Cancelar processamento", use_container_width=True, 
                               key=f"{key_prefix}_request_cancel_{iteration}"):
                        st.session_state.show_cancel_confirm = True
                        st.rerun()
            
            # Verificar conclusão
            if status in ['concluido', 'concluido_com_falhas', 'cancelado', 'erro']:
                st.session_state.relatorio = estado
                st.session_state.cancelamento_solicitado = False
                st.session_state.show_cancel_confirm = False
                time.sleep(0.5)
                st.session_state.page = 'result'
                st.rerun()
                break
            
            time.sleep(0.05)
    
    except InterruptedError:
        st.error("Processamento cancelado")
        time.sleep(1)
        st.session_state.cancelamento_solicitado = False
        st.session_state.show_cancel_confirm = False
        st.session_state.page = back_page
        st.rerun()
    
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        if st.button("Voltar", key=f"{key_prefix}_back_error"):
            st.session_state.page = back_page
            st.rerun()


def page_processing_number():
    if not verificar_sessao_ou_redirecionar():
        return
    
    processos = st.session_state.get('processos_para_baixar', [])
    tipo_documento = st.session_state.get('tipo_documento_numero', 'Selecione')
    
    if not processos:
        st.session_state.page = 'download_by_number'
        st.rerun()
        return
    
    pje = get_pje_client()
    generator = pje.processar_numeros_generator(
        numeros_processos=processos,
        tipo_documento=tipo_documento,
        aguardar_download=True
    )
    
    render_processing_page(
        generator,
        f"Processando {len(processos)} processo(s)",
        'download_by_number',
        'number'
    )


def page_processing_task():
    if not verificar_sessao_ou_redirecionar():
        return
    
    tarefa = st.session_state.get('selected_task')
    limite = st.session_state.get('task_limit')
    usar_favoritas = st.session_state.get('task_usar_favoritas', False)
    tamanho_lote = st.session_state.get('task_tamanho_lote', 10)
    
    if not tarefa:
        st.session_state.page = 'download_by_task'
        st.rerun()
        return
    
    pje = get_pje_client()
    generator = pje.processar_tarefa_generator(
        nome_tarefa=tarefa.nome,
        usar_favoritas=usar_favoritas,
        limite=limite,
        aguardar_download=True,
        tamanho_lote=tamanho_lote
    )
    
    render_processing_page(
        generator,
        f"Processando tarefa: {tarefa.nome}",
        'download_by_task',
        'task'
    )


def page_processing_tag():
    if not verificar_sessao_ou_redirecionar():
        return
    
    etiqueta = st.session_state.get('selected_tag')
    limite = st.session_state.get('tag_limit')
    tamanho_lote = st.session_state.get('tag_tamanho_lote', 10)
    
    if not etiqueta:
        st.session_state.page = 'download_by_tag'
        st.rerun()
        return
    
    pje = get_pje_client()
    generator = pje.processar_etiqueta_generator(
        nome_etiqueta=etiqueta.nome,
        limite=limite,
        aguardar_download=True,
        tamanho_lote=tamanho_lote
    )
    
    render_processing_page(
        generator,
        f"Processando etiqueta: {etiqueta.nome}",
        'download_by_tag',
        'tag'
    )


def page_result():
    if not verificar_sessao_ou_redirecionar():
        return
    
    relatorio = st.session_state.get('relatorio', {})
    status = relatorio.get('status', 'concluido')
    
    # Título baseado no status
    if status == 'concluido':
        st.title("Processamento Concluído")
    elif status == 'concluido_com_falhas':
        st.title("Concluído com Falhas")
    elif status == 'cancelado':
        st.title("Processamento Cancelado")
    else:
        st.title("Resultado do Processamento")
    
    st.markdown("---")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de processos", relatorio.get('processos', 0))
    col2.metric("Bem-sucedidos", relatorio.get('sucesso', 0))
    col3.metric("Falhas", relatorio.get('falha', 0))
    col4.metric("Arquivos baixados", len(relatorio.get('arquivos', [])))
    
    # Status de integridade
    integridade = relatorio.get('integridade', 'pendente')
    retries = relatorio.get('retries', {})
    
    if integridade == 'ok':
        st.success("Integridade verificada: Todos os arquivos foram baixados corretamente")
    elif integridade == 'inconsistente':
        falhas_count = len(retries.get('processos_falha_definitiva', []))
        st.warning(f"Integridade inconsistente: {falhas_count} arquivo(s) não puderam ser baixados")
    
    # Erros
    erros = relatorio.get('erros', [])
    if erros:
        with st.expander(f"Ver erros ({len(erros)})"):
            for erro in erros:
                st.error(erro)
    
    st.markdown("---")
    
    # Informações do diretório
    diretorio = relatorio.get('diretorio', st.session_state.download_dir)
    st.text(f"Diretório de download: {diretorio}")
    
    # Ações
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Abrir pasta de downloads", use_container_width=True, type="primary", key="btn_open_result"):
            open_folder(diretorio)
    
    with col2:
        st.download_button(
            "Baixar relatório (JSON)",
            data=json.dumps(relatorio, ensure_ascii=False, indent=2),
            file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="btn_download_report"
        )
    
    # Detalhes adicionais
    falhas_def = retries.get('processos_falha_definitiva', [])
    if falhas_def:
        with st.expander(f"Processos com falha definitiva ({len(falhas_def)})"):
            for proc in falhas_def:
                st.code(proc)
    
    arquivos = relatorio.get('arquivos', [])
    if arquivos:
        with st.expander(f"Arquivos baixados ({len(arquivos)})"):
            for arq in arquivos[:50]:
                st.text(Path(arq).name)
            if len(arquivos) > 50:
                st.caption(f"... e mais {len(arquivos) - 50} arquivo(s)")
    
    st.markdown("---")
    
    # Navegação
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Novo download", use_container_width=True, type="primary", key="btn_new_download"):
            st.session_state.relatorio = None
            st.session_state.page = 'main_menu'
            st.rerun()
    
    with col2:
        if st.button("Sair do sistema", use_container_width=True, key="btn_logout_result"):
            limpar_sessao_completa()


def main():
    init_session_state()
    
    pages = {
        'login': page_login,
        'select_profile': page_select_profile,
        'main_menu': page_main_menu,
        'download_by_task': page_download_by_task,
        'download_by_tag': page_download_by_tag,
        'download_by_number': page_download_by_number,
        'processing_task': page_processing_task,
        'processing_tag': page_processing_tag,
        'processing_number': page_processing_number,
        'result': page_result
    }
    
    page_func = pages.get(st.session_state.page, page_login)
    page_func()


if __name__ == "__main__":
    main()