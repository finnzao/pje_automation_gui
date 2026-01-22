"""
Servico de autenticacao do PJE - VERSÃO OTIMIZADA.
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
        self.sessao_corrompida_detectada = False
        
        # OTIMIZAÇÃO: Cache de validação
        self._ultima_validacao: float = 0
        self._intervalo_validacao: int = 300  # 5 minutos
        self._sessao_validada: bool = False
        self._cache_perfis_timestamp: float = 0
        self._cache_perfis_duracao: int = 600  # 10 minutos
    
    @property
    def usuario(self) -> Optional[Usuario]:
        return self.client.usuario
    
    @usuario.setter
    def usuario(self, value: Usuario):
        self.client.usuario = value
    
    def _invalidar_cache_validacao(self):
        """Invalida cache de validação."""
        self._sessao_validada = False
        self._ultima_validacao = 0
    
    def marcar_sessao_corrompida(self):
        """Marca que foi detectada sessao corrompida."""
        self.sessao_corrompida_detectada = True
        self._invalidar_cache_validacao()
        self.logger.warning("Sessao marcada como corrompida")
    
    def tem_sessao_corrompida(self) -> bool:
        return self.sessao_corrompida_detectada
    
    def limpar_flag_corrompida(self):
        self.sessao_corrompida_detectada = False
    
    def verificar_sessao_ativa(self) -> bool:
        """Verifica se ha sessao ativa no servidor."""
        try:
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                self.usuario = Usuario.from_dict(data)
                self.logger.debug(f"Usuario atualizado: {self.usuario.nome}")
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
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                self.usuario = Usuario.from_dict(data)
                self.logger.info(f"Usuario atualizado: {self.usuario.nome}")
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
            self._sessao_validada = True
            self._ultima_validacao = time.time()
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
        
        # OTIMIZAÇÃO: Verificar sessão existente
        if not force:
            if self.verificar_sessao_ativa():
                self.logger.info(f"Ja logado: {self.usuario.nome}")
                self._sessao_validada = True
                self._ultima_validacao = time.time()
                return True
            if self.restaurar_sessao():
                return True
        else:
            self.session_manager.clear_session()
            self._invalidar_cache_validacao()
        
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
                self.limpar_flag_corrompida()
                self._sessao_validada = True
                self._ultima_validacao = time.time()
                return True
            else:
                self.logger.error("Falha na verificacao pos-login")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro no login: {e}")
            return False
    
    # OTIMIZAÇÃO: Validação rápida com cache
    def validar_saude_sessao_rapida(self) -> bool:
        """
        Validação RÁPIDA - usa cache temporal.
        Apenas 1 request se cache expirou.
        """
        agora = time.time()
        
        # Cache válido? Retorna imediatamente
        if self._sessao_validada and (agora - self._ultima_validacao) < self._intervalo_validacao:
            return True
        
        if not self.usuario:
            self._sessao_validada = False
            return False
        
        try:
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("idUsuario"):
                    self._sessao_validada = True
                    self._ultima_validacao = agora
                    return True
            
            self._sessao_validada = False
            self.marcar_sessao_corrompida()
            return False
            
        except Exception:
            self._sessao_validada = False
            return False
    
    def validar_saude_sessao(self, completa: bool = False) -> bool:
        """
        Valida sessão.
        
        Args:
            completa: Se True, faz 3 requests. Se False, usa cache.
        """
        # Modo rápido (padrão)
        if not completa:
            return self.validar_saude_sessao_rapida()
        
        # Modo completo (quando explicitamente solicitado)
        if not self.usuario:
            self.logger.warning("Sessao sem usuario")
            self.marcar_sessao_corrompida()
            return False
        
        try:
            headers = self.client.get_api_headers()
            resp = self.client.session.get(
                f"{API_BASE}/usuario/currentUser",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code != 200:
                self.logger.warning(f"currentUser retornou {resp.status_code}")
                self.marcar_sessao_corrompida()
                return False
            
            user_data = resp.json()
            if not user_data.get("idUsuario"):
                self.logger.warning("currentUser sem ID")
                self.marcar_sessao_corrompida()
                return False
            
            # Validação completa bem-sucedida
            self._sessao_validada = True
            self._ultima_validacao = time.time()
            self.limpar_flag_corrompida()
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao validar saude da sessao: {e}")
            self.marcar_sessao_corrompida()
            return False
    
    def forcar_reset_sessao(self) -> bool:
        """Forca reset completo da sessao."""
        self.logger.warning("Forcando reset completo da sessao")
        
        try:
            self.client.session.cookies.clear()
            self.session_manager.clear_session()
            
            config_dir = Path(".config")
            if config_dir.exists():
                try:
                    shutil.rmtree(config_dir)
                except Exception as e:
                    self.logger.warning(f"Erro ao remover .config: {e}")
            
            config_dir.mkdir(parents=True, exist_ok=True)
            
            self.usuario = None
            self.perfis_disponiveis = []
            self.limpar_flag_corrompida()
            self._invalidar_cache_validacao()
            self._cache_perfis_timestamp = 0
            
            self.logger.success("Reset completo concluido")
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
        """Login com validação automática."""
        tentativa = 0
        
        while tentativa < max_tentativas:
            tentativa += 1
            
            if not self.login(username, password, force):
                self.logger.error(f"Falha no login (tentativa {tentativa}/{max_tentativas})")
                
                if tentativa == 1:
                    self.logger.warning("Forcando reset para proxima tentativa")
                    self.forcar_reset_sessao()
                    force = True
                    continue
                
                return False
            
            # OTIMIZAÇÃO: Validação rápida pós-login
            # O login já verificou currentUser, então a sessão está OK
            self._sessao_validada = True
            self._ultima_validacao = time.time()
            return True
        
        return False
    
    def ensure_logged_in(self) -> bool:
        """Garante que está logado - OTIMIZADO."""
        # Se já validado recentemente, retorna direto
        if self._sessao_validada and self.usuario:
            agora = time.time()
            if (agora - self._ultima_validacao) < self._intervalo_validacao:
                return True
        
        # Validação rápida
        if self.usuario and self.validar_saude_sessao_rapida():
            return True
        
        # Sessão inválida, tentar login
        if self.sessao_corrompida_detectada:
            self.forcar_reset_sessao()
        
        return self.login_com_validacao()
    
    def limpar_sessao(self):
        """Limpa sessao salva."""
        self.session_manager.clear_session()
        self.client.session.cookies.clear()
        self._invalidar_cache_validacao()
    
    # ... (resto dos métodos permanecem iguais: _decode_html_entities, 
    #      _extrair_perfil_favorito_do_header, _extrair_perfis_da_pagina, etc.)
    
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
            
            return perfil
            
        except Exception:
            return None
    
    def _extrair_perfis_da_pagina(self, html: str) -> List[Perfil]:
        perfis = []
        
        perfil_favorito = self._extrair_perfil_favorito_do_header(html)
        if perfil_favorito:
            perfis.append(perfil_favorito)
        
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
                
        except Exception as e:
            self.logger.error(f"Erro ao navegar para pagina {pagina}: {e}")
        
        return None
    
    def listar_perfis(self) -> List[Perfil]:
        """Lista perfis - COM CACHE."""
        if not self.ensure_logged_in():
            return []
        
        now = time.time()
        if self.perfis_disponiveis and (now - self._cache_perfis_timestamp) < self._cache_perfis_duracao:
            self.logger.debug("Usando cache de perfis")
            return self.perfis_disponiveis
        
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
                self.marcar_sessao_corrompida()
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
                    
                    delay(0.3, 0.6)  # Delay reduzido
                    
                    html_pagina = self._navegar_pagina_perfis(pagina_atual, html)
                    
                    if not html_pagina:
                        break
                    
                    perfis_pagina = self._extrair_perfis_da_pagina(html_pagina)
                    
                    if not perfis_pagina:
                        break
                    
                    novos_perfis = 0
                    for perfil in perfis_pagina:
                        nome_key = perfil.nome_completo.lower()
                        if perfil.index not in indices_vistos and nome_key not in nomes_vistos:
                            todos_perfis.append(perfil)
                            indices_vistos.add(perfil.index)
                            nomes_vistos.add(nome_key)
                            novos_perfis += 1
                    
                    if novos_perfis == 0:
                        break

                    html = html_pagina
                    info_pag = self._extrair_info_paginacao(html)
            
            self.perfis_disponiveis = todos_perfis
            self._cache_perfis_timestamp = now  # Atualizar timestamp do cache
            
            if not todos_perfis:
                self.logger.warning("Nenhum perfil encontrado")
                self.marcar_sessao_corrompida()
                return []
            
            self.logger.info(f"Total: {len(todos_perfis)} perfis encontrados")
            return todos_perfis
            
        except Exception as e:
            self.logger.error(f"Erro ao listar perfis: {e}")
            self.marcar_sessao_corrompida()
        
        return []
    
    def select_profile_by_index(self, profile_index: int) -> bool:
        if not self.ensure_logged_in():
            return False
        try:
            resp = self.client.session.get(f"{BASE_URL}/pje/ng2/dev.seam", timeout=self.client.timeout)
            
            viewstate_match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
            viewstate = viewstate_match.group(1) if viewstate_match else "j_id1"
            
            delay(0.3, 0.6)  # Delay reduzido
            
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
            
            delay(0.5, 1.0)  # Delay reduzido
            
            if self.atualizar_usuario():
                self.logger.success(f"Perfil selecionado: {self.usuario.nome}")
                self.session_manager.save_session(self.client.session)
                self._sessao_validada = True
                self._ultima_validacao = time.time()
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