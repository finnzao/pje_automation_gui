import streamlit as st

st.set_page_config(
    page_title="PJE Download Manager",
    page_icon="",
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
    .stButton > button {border-radius: 4px; font-weight: 500;}
    .block-container {padding-top: 2rem;}
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
        "iniciando": "Iniciando...",
        "buscando_tarefa": "Buscando tarefa...",
        "buscando_etiqueta": "Buscando etiqueta...",
        "buscando_processo": "Buscando processo...",
        "listando_processos": "Listando processos...",
        "processando": "Processando...",
        "baixando_lote": "Baixando arquivos...",
        "aguardando_downloads": "Aguardando downloads...",
        "verificando_integridade": "Verificando integridade...",
        "retry_1": "Retry 1/2...",
        "retry_2": "Retry 2/2...",
        "concluido": "Concluido",
        "concluido_com_falhas": "Concluido com falhas",
        "cancelado": "Cancelado",
        "erro": "Erro"
    }
    return texts.get(status, status)


def limpar_sessao_e_config():
    pastas_para_limpar = ['.config', '.session']
    for pasta in pastas_para_limpar:
        pasta_path = Path(pasta)
        if pasta_path.exists():
            try:
                shutil.rmtree(pasta_path)
            except Exception as e:
                st.warning(f"Nao foi possivel limpar {pasta}: {e}")
    for pasta in pastas_para_limpar:
        Path(pasta).mkdir(parents=True, exist_ok=True)


def do_logout(limpar_tudo: bool = False):
    if st.session_state.pje_client:
        try:
            st.session_state.pje_client.close()
        except:
            pass
    if limpar_tudo:
        limpar_sessao_e_config()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


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
    st.caption("Sistema de download de processos do PJE-TJBA")
    
    cred_manager = CredentialManager()
    saved_user, saved_pass = cred_manager.load_credentials()
    has_saved = saved_user is not None and saved_pass is not None
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if has_saved:
            st.info(f"Usuario salvo: {saved_user}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Entrar", use_container_width=True, type="primary"):
                    do_login(saved_user, saved_pass)
            with c2:
                if st.button("Limpar", use_container_width=True):
                    cred_manager.clear_credentials()
                    st.rerun()
            st.divider()
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("CPF", value=saved_user or "", placeholder="00000000000")
            password = st.text_input("Senha", type="password")
            save_cred = st.checkbox("Salvar login", value=has_saved)
            
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if not username or not password:
                    st.error("Preencha CPF e senha")
                else:
                    if save_cred:
                        cred_manager.save_credentials(username, password)
                    do_login(username, password)


def do_login(username: str, password: str):
    with st.spinner("Conectando..."):
        try:
            pje = get_pje_client()
            if pje.login(username, password):
                st.session_state.logged_in = True
                st.session_state.user_name = pje.usuario.nome if pje.usuario else username
                st.session_state.page = 'select_profile'
                st.rerun()
            else:
                st.error("Falha no login")
        except Exception as e:
            st.error(f"Erro: {str(e)}")


def page_select_profile():
    st.title("Selecionar Perfil")
    st.caption(f"Usuario: {st.session_state.user_name}")
    
    pje = get_pje_client()
    
    col_reload, col_spacer = st.columns([1, 4])
    with col_reload:
        if st.button("Atualizar", help="Recarregar lista de perfis"):
            st.session_state.perfis = []
            st.rerun()
    
    if not st.session_state.perfis:
        with st.spinner("Carregando perfis..."):
            st.session_state.perfis = pje.listar_perfis()
    
    perfis = st.session_state.perfis
    
    if not perfis:
        st.warning("Nenhum perfil encontrado")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Tentar novamente", use_container_width=True):
                st.session_state.perfis = []
                st.rerun()
        with col2:
            if st.button("Sair", use_container_width=True):
                do_logout(limpar_tudo=True)
        return
    
    st.info(f"{len(perfis)} perfil(is) disponivel(is)")
    
    busca_perfil = st.text_input("Buscar perfil", placeholder="Digite para filtrar...")
    
    if busca_perfil:
        perfis_filtrados = [p for p in perfis if busca_perfil.lower() in p.nome_completo.lower()]
    else:
        perfis_filtrados = perfis
    
    st.markdown("---")
    
    for perfil in perfis_filtrados:
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                nome_display = f"**{perfil.nome}**"
                if perfil.orgao:
                    nome_display += f" - {perfil.orgao}"
                if perfil.cargo:
                    nome_display += f" ({perfil.cargo})"
                if hasattr(perfil, 'favorito') and perfil.favorito:
                    nome_display += " ⭐"
                st.markdown(nome_display)
            with col2:
                if st.button("Selecionar", key=f"perfil_btn_{perfil.index}_{hash(perfil.nome)}"):
                    with st.spinner(f"Selecionando {perfil.nome}..."):
                        if pje.select_profile_by_index(perfil.index):
                            st.session_state.perfil_selecionado = perfil
                            st.session_state.tarefas = []
                            st.session_state.tarefas_favoritas = []
                            st.session_state.page = 'main_menu'
                            st.rerun()
                        else:
                            st.error(f"Erro ao selecionar perfil: {perfil.nome}")
    
    st.markdown("---")
    if st.button("Sair", use_container_width=True):
        do_logout(limpar_tudo=True)


def page_main_menu():
    perfil = st.session_state.perfil_selecionado
    st.title("Menu Principal")
    st.caption(f"{st.session_state.user_name} | {perfil.nome if perfil else '-'}")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Por Tarefa")
        st.caption("Baixar processos de uma tarefa")
        if st.button("Abrir", key="btn_task", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_task'
            st.rerun()
    
    with col2:
        st.subheader("Por Etiqueta")
        st.caption("Baixar processos de uma etiqueta")
        if st.button("Abrir", key="btn_tag", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_tag'
            st.rerun()
    
    with col3:
        st.subheader("Por Número")
        st.caption("Baixar processo específico")
        if st.button("Abrir", key="btn_numero", use_container_width=True, type="primary"):
            st.session_state.page = 'download_by_number'
            st.rerun()
    
    st.divider()
    
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Trocar Perfil", use_container_width=True):
            st.session_state.tarefas = []
            st.session_state.tarefas_favoritas = []
            st.session_state.page = 'select_profile'
            st.rerun()
    with c2:
        if st.button("Abrir Downloads", use_container_width=True):
            open_folder(st.session_state.download_dir)
    with c3:
        if st.button("Sair", use_container_width=True):
            do_logout(limpar_tudo=True)


def page_download_by_task():
    st.title("Download por Tarefa")
    
    pje = get_pje_client()
    
    with st.sidebar:
        st.subheader("Opcoes")
        usar_favoritas = st.checkbox("Apenas favoritas")
        limite = st.number_input("Limite (0=todos)", min_value=0, max_value=500, value=0)
        tamanho_lote = st.slider("Tamanho lote", 5, 30, 10)
        st.divider()
        if st.button("Atualizar Tarefas", use_container_width=True):
            st.session_state.tarefas = []
            st.session_state.tarefas_favoritas = []
            st.rerun()
        st.divider()
        if st.button("Voltar", use_container_width=True):
            st.session_state.page = 'main_menu'
            st.rerun()
    
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
        st.warning("Nenhuma tarefa encontrada para este perfil.")
        return
    
    st.caption(f"{len(tarefas)} tarefa(s)")
    
    busca = st.text_input("Buscar", placeholder="Filtrar tarefas...")
    tarefas_filtradas = [t for t in tarefas if busca.lower() in t.nome.lower()] if busca else tarefas
    
    st.markdown("---")
    
    for idx, tarefa in enumerate(tarefas_filtradas):
        with st.container():
            col1, col2, col3 = st.columns([5, 1, 1])
            with col1:
                st.markdown(f"**{tarefa.nome}**")
            with col2:
                st.caption(f"{tarefa.quantidade_pendente}")
            with col3:
                if st.button("Baixar", key=f"tarefa_dl_{idx}_{tarefa.id}"):
                    st.session_state.selected_task = tarefa
                    st.session_state.task_limit = limite if limite > 0 else None
                    st.session_state.task_usar_favoritas = usar_favoritas
                    st.session_state.task_tamanho_lote = tamanho_lote
                    st.session_state.cancelamento_solicitado = False
                    st.session_state.page = 'processing_task'
                    st.rerun()


def page_download_by_tag():
    st.title("Download por Etiqueta")
    
    pje = get_pje_client()
    
    with st.sidebar:
        st.subheader("Opcoes")
        limite = st.number_input("Limite (0=todos)", min_value=0, max_value=500, value=0)
        tamanho_lote = st.slider("Tamanho lote", 5, 30, 10)
        st.divider()
        if st.button("Voltar", use_container_width=True):
            st.session_state.page = 'main_menu'
            st.rerun()
    
    busca = st.text_input("Nome da etiqueta", placeholder="Buscar etiqueta...")
    
    if busca:
        with st.spinner("Buscando etiquetas..."):
            etiquetas = pje.buscar_etiquetas(busca)
        
        etiquetas_unicas = []
        ids_vistos = set()
        for et in etiquetas:
            if et.id not in ids_vistos:
                etiquetas_unicas.append(et)
                ids_vistos.add(et.id)
        etiquetas = etiquetas_unicas
        
        if etiquetas:
            st.caption(f"{len(etiquetas)} etiqueta(s)")
            st.markdown("---")
            
            for idx, etiqueta in enumerate(etiquetas):
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{etiqueta.nome}**")
                    with col2:
                        if st.button("Baixar", key=f"etiqueta_dl_{idx}_{etiqueta.id}"):
                            st.session_state.selected_tag = etiqueta
                            st.session_state.tag_limit = limite if limite > 0 else None
                            st.session_state.tag_tamanho_lote = tamanho_lote
                            st.session_state.cancelamento_solicitado = False
                            st.session_state.page = 'processing_tag'
                            st.rerun()
        else:
            st.warning(f"Nenhuma etiqueta encontrada para: '{busca}'")
    else:
        st.info("Digite o nome da etiqueta para buscar")


def page_download_by_number():
    st.title("Download por Número de Processo")
    
    with st.sidebar:
        st.subheader("Opcoes")
        tipo_documento = st.selectbox(
            "Tipo de documento",
            ["Selecione", "Peticao Inicial", "Peticao", "Sentenca", "Decisao", "Despacho", "Acordao", "Outros documentos"],
            index=0
        )
        st.divider()
        if st.button("Voltar", use_container_width=True):
            st.session_state.page = 'main_menu'
            st.rerun()
    
    st.markdown("""
    ### Instruções
    Digite o(s) número(s) do(s) processo(s) que deseja baixar.
    
    **Formatos aceitos:**
    - Com formatação: `0000001-23.2024.8.05.0001`
    - Sem formatação: `00000012320248050001`
    
    **Importante:** O processo deve estar acessível no seu perfil atual (em alguma tarefa ou etiqueta).
    """)
    
    numeros_input = st.text_area(
        "Número(s) do(s) processo(s)",
        placeholder="0000001-23.2024.8.05.0001\n0000002-45.2024.8.05.0001",
        height=150
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
        
        processos_validos = list(dict.fromkeys(processos_validos))
        
        col1, col2 = st.columns(2)
        with col1:
            if processos_validos:
                st.success(f"✓ {len(processos_validos)} processo(s) válido(s)")
        with col2:
            if processos_invalidos:
                st.error(f"✗ {len(processos_invalidos)} processo(s) inválido(s)")
        
        if processos_validos:
            with st.expander("Ver processos válidos", expanded=True):
                for p in processos_validos:
                    st.code(p)
            
            st.divider()
            
            if st.button("Baixar Processo(s)", type="primary", use_container_width=True):
                st.session_state.processos_para_baixar = processos_validos
                st.session_state.tipo_documento_numero = tipo_documento
                st.session_state.cancelamento_solicitado = False
                st.session_state.page = 'processing_number'
                st.rerun()
    else:
        st.info("Digite pelo menos um número de processo para continuar.")


def page_processing_number():
    processos = st.session_state.get('processos_para_baixar', [])
    tipo_documento = st.session_state.get('tipo_documento_numero', 'Selecione')
    
    if not processos:
        st.session_state.page = 'download_by_number'
        st.rerun()
        return
    
    st.title("Processando")
    st.caption(f"{len(processos)} processo(s)")
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    processo_text = st.empty()
    
    col1, col2, col3, col4 = st.columns(4)
    metric_total = col1.empty()
    metric_prog = col2.empty()
    metric_ok = col3.empty()
    metric_files = col4.empty()
    
    st.divider()
    
    cancel_message = st.empty()
    
    cancel_col = st.columns([1, 1, 1])[1]
    with cancel_col:
        cancel_clicked = st.button("Cancelar", use_container_width=True, key="cancel_btn_number", type="secondary")
    
    pje = get_pje_client()
    
    if cancel_clicked or st.session_state.get('cancelamento_solicitado', False):
        st.session_state.cancelamento_solicitado = True
        pje.cancelar_processamento()
        cancel_message.warning("⚠️ Cancelamento solicitado. Aguarde...")
    
    try:
        generator = pje.processar_numeros_generator(
            numeros_processos=processos,
            tipo_documento=tipo_documento,
            aguardar_download=True
        )
        
        for estado in generator:
            status = estado.get('status', '')
            progresso = estado.get('progresso', 0)
            total = estado.get('processos', 0)
            proc_atual = estado.get('processo_atual', '')
            
            status_text.markdown(f"**Status:** {get_status_text(status)}")
            
            if total > 0:
                progress_bar.progress(min(progresso / total, 1.0))
            
            processo_text.text(proc_atual if proc_atual else "")
            
            metric_total.metric("Total", total)
            metric_prog.metric("Progresso", f"{progresso}/{total}")
            metric_ok.metric("OK", estado.get('sucesso', 0))
            metric_files.metric("Arquivos", len(estado.get('arquivos', [])))
            
            if status in ['concluido', 'concluido_com_falhas', 'cancelado', 'erro']:
                st.session_state.relatorio = estado
                st.session_state.cancelamento_solicitado = False
                time.sleep(0.5)
                st.session_state.page = 'result'
                st.rerun()
                break
        
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        if st.button("Voltar"):
            st.session_state.cancelamento_solicitado = False
            st.session_state.page = 'download_by_number'
            st.rerun()


def page_processing_task():
    tarefa = st.session_state.get('selected_task')
    limite = st.session_state.get('task_limit')
    usar_favoritas = st.session_state.get('task_usar_favoritas', False)
    tamanho_lote = st.session_state.get('task_tamanho_lote', 10)
    
    if not tarefa:
        st.session_state.page = 'download_by_task'
        st.rerun()
        return
    
    st.title("Processando")
    st.caption(tarefa.nome)
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    processo_text = st.empty()
    
    col1, col2, col3, col4 = st.columns(4)
    metric_total = col1.empty()
    metric_prog = col2.empty()
    metric_ok = col3.empty()
    metric_files = col4.empty()
    
    st.divider()
    
    cancel_message = st.empty()
    
    cancel_col = st.columns([1, 1, 1])[1]
    with cancel_col:
        cancel_clicked = st.button("Cancelar", use_container_width=True, key="cancel_btn", type="secondary")
    
    pje = get_pje_client()
    
    if cancel_clicked or st.session_state.get('cancelamento_solicitado', False):
        st.session_state.cancelamento_solicitado = True
        pje.cancelar_processamento()
        cancel_message.warning("⚠️ Cancelamento solicitado. Aguarde...")
    
    try:
        generator = pje.processar_tarefa_generator(
            nome_tarefa=tarefa.nome,
            usar_favoritas=usar_favoritas,
            limite=limite,
            aguardar_download=True,
            tamanho_lote=tamanho_lote
        )
        
        for estado in generator:
            status = estado.get('status', '')
            progresso = estado.get('progresso', 0)
            total = estado.get('processos', 0)
            proc_atual = estado.get('processo_atual', '')
            
            status_text.markdown(f"**Status:** {get_status_text(status)}")
            
            if total > 0:
                progress_bar.progress(min(progresso / total, 1.0))
            
            processo_text.text(proc_atual if proc_atual else "")
            
            metric_total.metric("Total", total)
            metric_prog.metric("Progresso", f"{progresso}/{total}")
            metric_ok.metric("OK", estado.get('sucesso', 0))
            metric_files.metric("Arquivos", len(estado.get('arquivos', [])))
            
            if status in ['concluido', 'concluido_com_falhas', 'cancelado', 'erro']:
                st.session_state.relatorio = estado
                st.session_state.cancelamento_solicitado = False
                time.sleep(0.5)
                st.session_state.page = 'result'
                st.rerun()
                break
        
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        if st.button("Voltar"):
            st.session_state.cancelamento_solicitado = False
            st.session_state.page = 'download_by_task'
            st.rerun()


def page_processing_tag():
    etiqueta = st.session_state.get('selected_tag')
    limite = st.session_state.get('tag_limit')
    tamanho_lote = st.session_state.get('tag_tamanho_lote', 10)
    
    if not etiqueta:
        st.session_state.page = 'download_by_tag'
        st.rerun()
        return
    
    st.title("Processando")
    st.caption(etiqueta.nome)
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    processo_text = st.empty()
    
    col1, col2, col3, col4 = st.columns(4)
    metric_total = col1.empty()
    metric_prog = col2.empty()
    metric_ok = col3.empty()
    metric_files = col4.empty()
    
    st.divider()
    
    cancel_message = st.empty()
    
    cancel_col = st.columns([1, 1, 1])[1]
    with cancel_col:
        cancel_clicked = st.button("Cancelar", use_container_width=True, key="cancel_btn_tag", type="secondary")
    
    pje = get_pje_client()
    
    if cancel_clicked or st.session_state.get('cancelamento_solicitado', False):
        st.session_state.cancelamento_solicitado = True
        pje.cancelar_processamento()
        cancel_message.warning("⚠️ Cancelamento solicitado. Aguarde...")
    
    try:
        generator = pje.processar_etiqueta_generator(
            nome_etiqueta=etiqueta.nome,
            limite=limite,
            aguardar_download=True,
            tamanho_lote=tamanho_lote
        )
        
        for estado in generator:
            status = estado.get('status', '')
            progresso = estado.get('progresso', 0)
            total = estado.get('processos', 0)
            proc_atual = estado.get('processo_atual', '')
            
            status_text.markdown(f"**Status:** {get_status_text(status)}")
            
            if total > 0:
                progress_bar.progress(min(progresso / total, 1.0))
            
            processo_text.text(proc_atual if proc_atual else "")
            
            metric_total.metric("Total", total)
            metric_prog.metric("Progresso", f"{progresso}/{total}")
            metric_ok.metric("OK", estado.get('sucesso', 0))
            metric_files.metric("Arquivos", len(estado.get('arquivos', [])))
            
            if status in ['concluido', 'concluido_com_falhas', 'cancelado', 'erro']:
                st.session_state.relatorio = estado
                st.session_state.cancelamento_solicitado = False
                time.sleep(0.5)
                st.session_state.page = 'result'
                st.rerun()
                break
        
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        if st.button("Voltar"):
            st.session_state.cancelamento_solicitado = False
            st.session_state.page = 'download_by_tag'
            st.rerun()


def page_result():
    relatorio = st.session_state.get('relatorio', {})
    status = relatorio.get('status', 'concluido')
    
    if status == 'concluido':
        st.title("✅ Concluido")
    elif status == 'concluido_com_falhas':
        st.title("⚠️ Concluido com falhas")
    elif status == 'cancelado':
        st.title("🚫 Cancelado")
    else:
        st.title("Resultado")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", relatorio.get('processos', 0))
    col2.metric("OK", relatorio.get('sucesso', 0))
    col3.metric("Falhas", relatorio.get('falha', 0))
    col4.metric("Arquivos", len(relatorio.get('arquivos', [])))
    
    integridade = relatorio.get('integridade', 'pendente')
    retries = relatorio.get('retries', {})
    
    if integridade == 'ok':
        st.success("Integridade: OK - Todos os arquivos confirmados")
    elif integridade == 'inconsistente':
        falhas_count = len(retries.get('processos_falha_definitiva', []))
        st.warning(f"Integridade: Inconsistente - {falhas_count} arquivo(s) faltando")
    
    erros = relatorio.get('erros', [])
    if erros:
        with st.expander(f"Erros ({len(erros)})", expanded=False):
            for erro in erros:
                st.error(erro)
    
    st.divider()
    
    diretorio = relatorio.get('diretorio', st.session_state.download_dir)
    st.text(f"Diretorio: {diretorio}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abrir Pasta", use_container_width=True, type="primary"):
            open_folder(diretorio)
    with col2:
        st.download_button(
            "Baixar Relatorio",
            data=json.dumps(relatorio, ensure_ascii=False, indent=2),
            file_name="relatorio.json",
            mime="application/json",
            use_container_width=True
        )
    
    falhas_def = retries.get('processos_falha_definitiva', [])
    if falhas_def:
        with st.expander(f"Falhas definitivas ({len(falhas_def)})", expanded=False):
            for proc in falhas_def:
                st.code(proc)
    
    arquivos = relatorio.get('arquivos', [])
    if arquivos:
        with st.expander(f"Arquivos baixados ({len(arquivos)})", expanded=False):
            for arq in arquivos[:50]:
                st.text(f"  {Path(arq).name}")
            if len(arquivos) > 50:
                st.caption(f"... +{len(arquivos) - 50} arquivo(s)")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Novo Download", use_container_width=True, type="primary"):
            st.session_state.relatorio = None
            st.session_state.page = 'main_menu'
            st.rerun()
    with col2:
        if st.button("Sair", use_container_width=True):
            do_logout(limpar_tudo=True)


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
