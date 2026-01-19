"""
Servico de autenticacao do PJE.
"""

import os
import re
import time
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
        
        from pathlib import Path
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
    
    def ensure_logged_in(self) -> bool:
        """Garante que esta logado."""
        if self.verificar_sessao_ativa():
            return True
        return self.login()
    
    def limpar_sessao(self):
        """Limpa sessao salva."""
        self.session_manager.clear_session()
        self.client.session.cookies.clear()
      
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        """Extrai perfis do HTML de uma pagina."""
        perfis = []
        
        pattern = r"dtPerfil:(\d+):j_id70'[^>]*>([^<]+)</a>"
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]*onclick="[^"]*dtPerfil:(\d+)[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
        
        for index_str, nome in matches:
            nome = nome.replace("&ccedil;", "c").replace("&atilde;", "a")
            nome = nome.replace("&aacute;", "a").replace("&eacute;", "e")
            nome = nome.replace("&iacute;", "i").replace("&oacute;", "o")
            nome = nome.replace("&uacute;", "u").replace("&amp;", "&")
            
            partes = nome.strip().split(" / ")
            perfis.append(Perfil(
                index=int(index_str),
                nome=partes[0] if partes else nome.strip(),
                orgao=partes[1] if len(partes) > 1 else "",
                cargo=partes[2] if len(partes) > 2 else ""
            ))
        
        return perfis
    
    def _tem_paginacao_visivel(self, html: str) -> bool:
        """Verifica se o DataScroller de perfis esta visivel."""
        scroller_pattern = r'id="[^"]*scPerfil"[^>]*style="[^"]*"'
        match = re.search(scroller_pattern, html)
        
        if not match:
            return False
        
        scroller_tag = match.group(0)
        
        if 'display: none' in scroller_tag or 'display:none' in scroller_tag:
            return False
        
        return True
    
    def _extrair_info_paginacao(self, html: str) -> dict:
        """Extrai informacoes de paginacao do HTML."""
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
        """Navega para uma pagina especifica de perfis via requisicao AJAX."""
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
        """Lista TODOS os perfis disponiveis."""
        if not self.ensure_logged_in():
            return []
        
        todos_perfis = []
        indices_vistos = set()
        
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
                if perfil.index not in indices_vistos:
                    todos_perfis.append(perfil)
                    indices_vistos.add(perfil.index)
            
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
                        if perfil.index not in indices_vistos:
                            todos_perfis.append(perfil)
                            indices_vistos.add(perfil.index)
                            novos_perfis += 1
                    
                    self.logger.info(f"Pagina {pagina_atual}: {novos_perfis} novos perfis")
                    
                    if novos_perfis == 0:
                        break

                    html = html_pagina
                    info_pag = self._extrair_info_paginacao(html)
            
            self.perfis_disponiveis = todos_perfis
            self.logger.info(f"Total: {len(todos_perfis)} perfis encontrados")
            return todos_perfis
            
        except Exception as e:
            self.logger.error(f"Erro ao listar perfis: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        """Seleciona perfil pelo indice."""
        if not self.ensure_logged_in():
            return False
        try:
            resp = self.client.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.client.timeout)
            
            viewstate_match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
            viewstate = viewstate_match.group(1) if viewstate_match else "j_id1"
            
            delay()
            
            form_data = {
                "papeisUsuarioForm": "papeisUsuarioForm",
                "papeisUsuarioForm:j_id60": "",
                "papeisUsuarioForm:j_id72": "papeisUsuarioForm:j_id72",
                "javax.faces.ViewState": viewstate,
                f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70": f"papeisUsuarioForm:dtPerfil:{profile_index}:j_id70"
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
        """Seleciona perfil pelo nome."""
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
