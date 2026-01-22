"""
Servico de autenticacao do PJE.
"""

import os
import re
import time
import shutil
from pathlib import Path
from typing import Optional, List

from ..config import BASE_URL, SSO_URL, API_BASE
from ..core import SessionManager, PJEHttpClient
from ..models import Usuario, Perfil
from ..utils import delay, get_logger, buscar_texto_similar, extrair_viewstate


class AuthService:
    """Servico de autenticacao e gerenciamento de perfil."""
    
    def __init__(self, http_client: PJEHttpClient, session_manager: SessionManager):
        self.client = http_client
        self.session_manager = session_manager
        self.logger = get_logger()
        self.perfis_disponiveis: List[Perfil] = []
    
    @property
    def usuario(self) -> Optional[Usuario]:
        return self.client.usuario
    
    @usuario.setter
    def usuario(self, value: Usuario):
        self.client.usuario = value
    
    def verificar_sessao_ativa(self) -> bool:
        """Verifica se ha sessao ativa no servidor."""
        try:
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=self.client.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                self.usuario = Usuario.from_dict(data)
                self.logger.debug(f"Usuario atualizado: {self.usuario.nome}, localizacao: {self.usuario.id_usuario_localizacao}")
                return True
        except Exception as e:
            self.logger.debug(f"Erro ao verificar sessao: {e}")
        return False
    
    def atualizar_usuario(self) -> bool:
        """Atualiza dados do usuario atual."""
        try:
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=self.client.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                self.usuario = Usuario.from_dict(data)
                self.logger.info(f"Usuario atualizado: {self.usuario.nome}")
                self.logger.info(f"ID Usuario Localizacao: {self.usuario.id_usuario_localizacao}")
                self.logger.info(f"ID Orgao Julgador: {self.usuario.id_orgao_julgador}")
                return True
        except Exception as e:
            self.logger.error(f"Erro ao atualizar usuario: {e}")
        return False
    
    def restaurar_sessao(self) -> bool:
        """Tenta restaurar sessao salva."""
        if not self.session_manager.is_session_valid():
            return False
        if not self.session_manager.load_session(self.client.session):
            return False
        if self.verificar_sessao_ativa():
            self.logger.info(f"Sessao restaurada: {self.usuario.nome}")
            return True
        return False
    
    def read_env(self) -> tuple:
        username = None
        password = None
        
        env_path = Path.cwd() / ".env"
        
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key in ('USER', 'PJE_USER') and not username:
                            username = value
                        elif key in ('PASSWORD', 'PJE_PASSWORD') and not password:
                            password = value
        
        return username, password
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        """Realiza login no PJE via SSO."""
        if not username or not password:
            env_user = os.getenv("PJE_USER") or os.getenv("USER")
            env_pass = os.getenv("PJE_PASSWORD") or os.getenv("PASSWORD")
            
            if not env_user or not env_pass:
                env_user, env_pass = self.read_env()
            
            username = username or env_user
            password = password or env_pass
        
        if not username or not password:
            self.logger.error("Credenciais nao fornecidas")
            return False
        
        if not force:
            if self.verificar_sessao_ativa():
                self.logger.info(f"Ja logado: {self.usuario.nome}")
                return True
            if self.restaurar_sessao():
                return True
        else:
            self.session_manager.clear_session()
        
        self.logger.info(f"Iniciando login: {username}...")
        
        try:
            self.client.session.cookies.clear()
            
            resp = self.client.session.get(
                f"{BASE_URL}/pje/login.seam",
                allow_redirects=True,
                timeout=self.client.timeout
            )
            
            if "sso.cloud.pje.jus.br" not in resp.url:
                self.logger.error("Nao redirecionou para SSO")
                return False
            
            action_match = re.search(r'action="([^"]*)"', resp.text)
            if not action_match:
                self.logger.error("URL de autenticacao nao encontrada")
                return False
            
            auth_url = action_match.group(1).replace("&amp;", "&")
            if not auth_url.startswith("http"):
                auth_url = f"{SSO_URL}{auth_url}"
            
            delay(0.5, 1)
            
            resp = self.client.session.post(
                auth_url,
                data={
                    "username": username,
                    "password": password,
                    "credentialId": "",
                },
                allow_redirects=True,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": SSO_URL,
                    "Referer": auth_url,
                }
            )
            
            delay(0.5, 1)
            
            if self.verificar_sessao_ativa():
                self.logger.success(f"Login OK: {self.usuario.nome}")
                self.session_manager.save_session(self.client.session)
                return True
            else:
                self.logger.error("Falha na verificacao pos-login")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro no login: {e}")
            return False
    
    def validar_saude_sessao(self) -> bool:
        """
        Valida se a sessao esta realmente funcional.
        
        Verifica:
        - Usuario esta autenticado
        - Consegue listar tarefas OU etiquetas
        - Dados retornados fazem sentido
        
        Returns:
            True se sessao esta saudavel, False se corrompida
        """
        if not self.usuario:
            self.logger.warning("Sessao sem usuario")
            return False
        
        try:
            # Teste 1: Verificar currentUser
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code != 200:
                self.logger.warning(f"currentUser retornou {resp.status_code}")
                return False
            
            user_data = resp.json()
            if not user_data.get("idUsuario"):
                self.logger.warning("currentUser sem ID")
                return False
            
            # Teste 2: Tentar listar tarefas
            resp_tarefas = self.client.api_post(
                "painelUsuario/tarefas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            
            # Teste 3: Tentar listar etiquetas
            resp_etiquetas = self.client.api_post(
                "painelUsuario/etiquetas",
                {"page": 0, "maxResults": 10, "tagsString": ""}
            )
            
            # Pelo menos um dos endpoints deve funcionar
            tarefas_ok = resp_tarefas.status_code == 200
            etiquetas_ok = resp_etiquetas.status_code == 200
            
            if not (tarefas_ok or etiquetas_ok):
                self.logger.warning("Nenhum endpoint de dados funcionou")
                return False
            
            # Verificar se retornou estrutura valida
            if tarefas_ok:
                tarefas = resp_tarefas.json()
                if not isinstance(tarefas, list):
                    self.logger.warning("Tarefas retornou estrutura invalida")
                    return False
            
            if etiquetas_ok:
                etiquetas_data = resp_etiquetas.json()
                if not isinstance(etiquetas_data, dict):
                    self.logger.warning("Etiquetas retornou estrutura invalida")
                    return False
            
            self.logger.info("✓ Sessao validada com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao validar saude da sessao: {e}")
            return False
    
    def forcar_reset_sessao(self) -> bool:
        """
        Forca reset completo da sessao.
        
        - Limpa cookies
        - Apaga arquivos de sessao
        - Apaga arquivos de config
        - Reinicializa estado
        """
        self.logger.warning("🔄 Forcando reset completo da sessao")
        
        try:
            # 1. Limpar cookies
            self.client.session.cookies.clear()
            
            # 2. Limpar sessao salva
            self.session_manager.clear_session()
            
            # 3. Limpar config (credenciais salvas)
            config_dir = Path(".config")
            if config_dir.exists():
                try:
                    shutil.rmtree(config_dir)
                    self.logger.info("✓ Diretorio .config removido")
                except Exception as e:
                    self.logger.warning(f"Erro ao remover .config: {e}")
            
            # Recriar diretorio vazio
            config_dir.mkdir(parents=True, exist_ok=True)
            
            # 4. Resetar estado interno
            self.usuario = None
            self.perfis_disponiveis = []
            
            self.logger.success("✓ Reset completo concluido")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao forcar reset: {e}")
            return False
    
    def login_com_validacao(
        self, 
        username: str = None, 
        password: str = None, 
        force: bool = False,
        max_tentativas: int = 2
    ) -> bool:
        """
        Login com validacao automatica de saude da sessao.
        
        Se detectar sessao corrompida, faz reset e tenta novamente.
        """
        tentativa = 0
        
        while tentativa < max_tentativas:
            tentativa += 1
            
            # Fazer login normal
            if not self.login(username, password, force):
                self.logger.error(f"Falha no login (tentativa {tentativa}/{max_tentativas})")
                
                # Na segunda tentativa, forcar reset
                if tentativa == 1:
                    self.logger.warning("Forcando reset para proxima tentativa")
                    self.forcar_reset_sessao()
                    force = True
                    continue
                
                return False
            
            # Validar saude da sessao
            self.logger.info("Validando saude da sessao...")
            
            if self.validar_saude_sessao():
                return True
            
            # Sessao corrompida detectada
            self.logger.error("❌ Sessao corrompida detectada!")
            
            if tentativa < max_tentativas:
                self.logger.warning(f"Tentando novamente ({tentativa + 1}/{max_tentativas})")
                self.forcar_reset_sessao()
                force = True
            else:
                self.logger.error("Numero maximo de tentativas atingido")
                return False
        
        return False
    
    def ensure_logged_in(self) -> bool:
        """
        Versao melhorada que valida saude da sessao.
        """
        # Se ja esta logado, validar saude
        if self.usuario:
            if self.validar_saude_sessao():
                return True
            
            # Sessao corrompida, forcar reset
            self.logger.warning("Sessao existente esta corrompida")
            self.forcar_reset_sessao()
        
        # Fazer login com validacao
        return self.login_com_validacao()
    
    def limpar_sessao(self):
        """Limpa sessao salva."""
        self.session_manager.clear_session()
        self.client.session.cookies.clear()
    
    def _decode_html_entities(self, nome: str) -> str:
        """Decodifica entidades HTML em texto."""
        nome = nome.replace("&ccedil;", "ç").replace("&Ccedil;", "Ç")
        nome = nome.replace("&atilde;", "ã").replace("&Atilde;", "Ã")
        nome = nome.replace("&aacute;", "á").replace("&Aacute;", "Á")
        nome = nome.replace("&eacute;", "é").replace("&Eacute;", "É")
        nome = nome.replace("&iacute;", "í").replace("&Iacute;", "Í")
        nome = nome.replace("&oacute;", "ó").replace("&Oacute;", "Ó")
        nome = nome.replace("&uacute;", "ú").replace("&Uacute;", "Ú")
        nome = nome.replace("&acirc;", "â").replace("&Acirc;", "Â")
        nome = nome.replace("&ecirc;", "ê").replace("&Ecirc;", "Ê")
        nome = nome.replace("&ocirc;", "ô").replace("&Ocirc;", "Ô")
        nome = nome.replace("&otilde;", "õ").replace("&Otilde;", "Õ")
        nome = nome.replace("&agrave;", "à").replace("&Agrave;", "À")
        nome = nome.replace("&amp;", "&")
        nome = nome.replace("&nbsp;", " ")
        return nome.strip()
    
    def _extrair_perfil_favorito_do_header(self, html: str) -> Optional[Perfil]:
        try:
            thead_pattern = r'<thead[^>]*class="rich-table-thead"[^>]*>.*?</thead>'
            thead_match = re.search(thead_pattern, html, re.IGNORECASE | re.DOTALL)
            
            if not thead_match:
                return None
            
            thead_html = thead_match.group(0)
            
            if 'favorite-16x16.png' not in thead_html or 'favorite-16x16-disabled.png' in thead_html:
                return None
            
            perfil_header_pattern = r"dtPerfil:j_id66[^>]*>([^<]+)</a>"
            match = re.search(perfil_header_pattern, thead_html, re.IGNORECASE)
            
            if not match:
                return None
            
            nome = self._decode_html_entities(match.group(1))
            partes = nome.split(" / ")
            
            perfil = Perfil(
                index=-1,
                nome=partes[0] if partes else nome,
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else "",
                favorito=True
            )
            
            self.logger.debug(f"Perfil favorito encontrado no header: {perfil.nome_completo}")
            return perfil
            
        except Exception as e:
            self.logger.debug(f"Erro ao extrair perfil favorito do header: {e}")
            return None
    
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        perfis = []
        
        perfil_favorito = self._extrair_perfil_favorito_do_header(html)
        if perfil_favorito:
            perfis.append(perfil_favorito)
            self.logger.debug(f"Adicionado perfil favorito: {perfil_favorito.nome_completo}")
        
        pattern = r"dtPerfil:(\d+):j_id70'[^>]*>([^<]+)</a>"
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*j_id70[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
        
        for index_str, nome in matches:
            nome = self._decode_html_entities(nome)
            partes = nome.split(" / ")
            
            perfil = Perfil(
                index=int(index_str),
                nome=partes[0] if partes else nome,
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else "",
                favorito=False
            )
            perfis.append(perfil)
        
        return perfis
    
    def _tem_paginacao_visivel(self, html: str) -> bool:
        scroller_pattern = r'id="[^"]*scPerfil"[^>]*style="[^"]*"'
        match = re.search(scroller_pattern, html)
        
        if not match:
            return False
        
        scroller_tag = match.group(0)
        
        if 'display: none' in scroller_tag or 'display:none' in scroller_tag:
            return False
        
        return True
    
    def _extrair_info_paginacao(self, html: str) -> dict:
        info = {
            "pagina_atual": 1,
            "total_paginas": 1,
            "tem_proxima": False,
            "tem_anterior": False
        }
        
        paginas_match = re.findall(r'rich-datascr-inact[^>]*>(\d+)<|rich-datascr-act[^>]*>(\d+)<', html)
        
        if paginas_match:
            todas_paginas = []
            pagina_atual = 1
            for inact, act in paginas_match:
                if act:
                    pagina_atual = int(act)
                    todas_paginas.append(int(act))
                elif inact:
                    todas_paginas.append(int(inact))
            
            if todas_paginas:
                info["pagina_atual"] = pagina_atual
                info["total_paginas"] = max(todas_paginas)
                info["tem_proxima"] = pagina_atual < max(todas_paginas)
                info["tem_anterior"] = pagina_atual > 1
        
        if 'rich-datascr-button' in html:
            if re.search(r'rich-datascr-button[^"]*"[^>]*onclick[^>]*fastnext|next', html):
                info["tem_proxima"] = True
        
        return info
    
    def _navegar_pagina_perfis(self, pagina: int, html_anterior: str) -> Optional[str]:
        viewstate = extrair_viewstate(html_anterior)
        if not viewstate:
            viewstate = "j_id1"
        
        form_id_match = re.search(r'id="([^"]*):scPerfil"', html_anterior)
        if not form_id_match:
            self.logger.warning("Nao foi possivel encontrar o ID do scroller")
            return None
        
        scroller_id = form_id_match.group(1) + ":scPerfil"
        form_id = form_id_match.group(1)
        
        form_data = {
            "AJAXREQUEST": "_viewRoot",
            form_id: form_id,
            scroller_id: str(pagina),
            "ajaxSingle": scroller_id,
            "javax.faces.ViewState": viewstate,
        }
        
        try:
            resp = self.client.session.post(
                f"{BASE_URL}/pje/ng2/dev.seam",
                data=form_data,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/ng2/dev.seam"
                }
            )
            
            if resp.status_code == 200:
                return resp.text
            else:
                self.logger.warning(f"Erro ao navegar pagina: status {resp.status_code}")
                
        except Exception as e:
            self.logger.error(f"Erro ao navegar para pagina {pagina}: {e}")
        
        return None
    
    def listar_perfis(self) -> List[Perfil]:
        if not self.ensure_logged_in():
            return []
        
        todos_perfis = []
        indices_vistos = set()
        nomes_vistos = set()

        try:
            resp = self.client.session.get(
                f"{BASE_URL}/pje/ng2/dev.seam", 
                timeout=self.client.timeout
            )
            
            if resp.status_code != 200:
                self.logger.error(f"Erro ao acessar pagina de perfis: {resp.status_code}")
                return []
            
            html = resp.text
            
            perfis_pagina = self._extrair_perfis_da_pagina(html)
            for perfil in perfis_pagina:
                nome_key = perfil.nome_completo.lower()
                if perfil.index not in indices_vistos and nome_key not in nomes_vistos:
                    todos_perfis.append(perfil)
                    indices_vistos.add(perfil.index)
                    nomes_vistos.add(nome_key)
            
            self.logger.info(f"Pagina 1: {len(perfis_pagina)} perfis encontrados")
            
            if self._tem_paginacao_visivel(html):
                info_pag = self._extrair_info_paginacao(html)
                self.logger.info(f"Paginacao detectada: {info_pag['total_paginas']} paginas")
                
                pagina_atual = 1
                max_tentativas = 20
                
                while pagina_atual < info_pag['total_paginas'] and pagina_atual < max_tentativas:
                    pagina_atual += 1
                    self.logger.info(f"Carregando pagina {pagina_atual} de perfis...")
                    
                    delay(0.5, 1.0)
                    
                    html_pagina = self._navegar_pagina_perfis(pagina_atual, html)
                    
                    if not html_pagina:
                        self.logger.warning(f"Falha ao carregar pagina {pagina_atual}")
                        break
                    
                    perfis_pagina = self._extrair_perfis_da_pagina(html_pagina)
                    
                    if not perfis_pagina:
                        self.logger.info(f"Pagina {pagina_atual} nao contem perfis, finalizando")
                        break
                    
                    novos_perfis = 0
                    for perfil in perfis_pagina:
                        nome_key = perfil.nome_completo.lower()
                        if perfil.index not in indices_vistos and nome_key not in nomes_vistos:
                            todos_perfis.append(perfil)
                            indices_vistos.add(perfil.index)
                            nomes_vistos.add(nome_key)
                            novos_perfis += 1
                    
                    self.logger.info(f"Pagina {pagina_atual}: {novos_perfis} novos perfis")
                    
                    if novos_perfis == 0:
                        break

                    html = html_pagina
                    info_pag = self._extrair_info_paginacao(html)
            
            self.perfis_disponiveis = todos_perfis
            
            favoritos = [p for p in todos_perfis if p.favorito]
            if favoritos:
                self.logger.info(f"Perfil(is) favorito(s): {[p.nome_completo for p in favoritos]}")
            
            self.logger.info(f"Total: {len(todos_perfis)} perfis encontrados")
            return todos_perfis
            
        except Exception as e:
            self.logger.error(f"Erro ao listar perfis: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        if not self.ensure_logged_in():
            return False
        try:
            resp = self.client.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.client.timeout)
            
            viewstate_match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
            viewstate = viewstate_match.group(1) if viewstate_match else "j_id1"
            
            delay()
            
            if profile_index == -1:
                element_id = "papeisUsuarioForm:dtPerfil:j_id66"
            else:
                element_id = f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70"
            
            form_data = {
                "papeisUsuarioForm": "papeisUsuarioForm",
                "papeisUsuarioForm:j_id60": "",
                "papeisUsuarioForm:j_id72": "papeisUsuarioForm:j_id72",
                "javax.faces.ViewState": viewstate,
                element_id: element_id
            }
            
            self.client.session.post(
                f"{BASE_URL}/pje/ng2/dev.seam",
                data=form_data,
                allow_redirects=True,
                timeout=self.client.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": BASE_URL}
            )
            
            delay(1.0, 2.0)
            
            if self.atualizar_usuario():
                self.logger.success(f"Perfil selecionado: {self.usuario.nome}")
                self.session_manager.save_session(self.client.session)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Erro ao selecionar perfil: {e}")
            return False
    
    def select_profile(self, nome_perfil: str) -> bool:
        if not self.perfis_disponiveis:
            self.listar_perfis()
        
        nomes = [p.nome_completo for p in self.perfis_disponiveis]
        idx = buscar_texto_similar(nome_perfil, nomes, threshold=0.4)
        
        if idx is not None:
            perfil = self.perfis_disponiveis[idx]
            self.logger.info(f"Perfil encontrado: {perfil.nome_completo}")
            return self.select_profile_by_index(perfil.index)
        
        self.logger.error(f"Perfil '{nome_perfil}' nao encontrado")
        return False