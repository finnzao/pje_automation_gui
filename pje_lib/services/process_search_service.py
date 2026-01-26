"""
Serviço especializado para busca de processos por número.

VERSÃO 2 - Com busca via API REST e salvamento de HTML para debug
"""

import re
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from ..config import BASE_URL
from ..core import PJEHttpClient
from ..utils import delay, extrair_viewstate, get_logger

# Diretório para salvar HTMLs de debug
DEBUG_HTML_DIR = Path.home() / "pje_debug_html"


@dataclass
class ResultadoBusca:
    """Resultado de uma busca de processo."""
    encontrado: bool = False
    id_processo: int = 0
    numero_processo: str = ""
    chave_acesso: str = ""
    metodo_busca: str = ""
    detalhes: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def url_autos(self) -> Optional[str]:
        """Retorna URL para autos digitais se disponível."""
        if self.id_processo and self.chave_acesso:
            return (
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/"
                f"listAutosDigitais.seam?idProcesso={self.id_processo}&ca={self.chave_acesso}"
            )
        elif self.id_processo:
            return (
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/"
                f"listAutosDigitais.seam?idProcesso={self.id_processo}"
            )
        return None


class ProcessSearchService:
    """
    Serviço para busca de processos por número.
    """
    
    def __init__(self, http_client: PJEHttpClient, salvar_debug_html: bool = True):
        self.client = http_client
        self.logger = get_logger()
        self._cache_resultados: Dict[str, ResultadoBusca] = {}
        self.salvar_debug_html = salvar_debug_html
        self._debug_dir = DEBUG_HTML_DIR
        
        # Criar diretório de debug se necessário
        if self.salvar_debug_html:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"[DEBUG] HTMLs serão salvos em: {self._debug_dir}")
    
    def _salvar_html_debug(self, html: str, prefixo: str, numero_processo: str = "") -> Optional[Path]:
        """
        Salva HTML para análise de debug.
        
        Args:
            html: Conteúdo HTML a salvar
            prefixo: Prefixo do arquivo (ex: 'busca_direta', 'api_response')
            numero_processo: Número do processo (opcional)
        
        Returns:
            Path do arquivo salvo ou None se debug desabilitado
        """
        if not self.salvar_debug_html:
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            numero_safe = numero_processo.replace('-', '_').replace('.', '_') if numero_processo else 'unknown'
            filename = f"{prefixo}_{numero_safe}_{timestamp}.html"
            filepath = self._debug_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- DEBUG HTML -->\n")
                f.write(f"<!-- Prefixo: {prefixo} -->\n")
                f.write(f"<!-- Processo: {numero_processo} -->\n")
                f.write(f"<!-- Timestamp: {timestamp} -->\n")
                f.write(f"<!-- Tamanho: {len(html)} bytes -->\n\n")
                f.write(html)
            
            self.logger.info(f"[DEBUG] HTML salvo: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"[DEBUG] Erro ao salvar HTML: {e}")
            return None
    
    def limpar_cache(self):
        """Limpa cache de resultados de busca."""
        self._cache_resultados.clear()
    
    def buscar_processo(
        self, 
        numero_processo: str,
        usar_cache: bool = True,
        metodos: List[str] = None
    ) -> ResultadoBusca:
        """
        Busca processo usando múltiplas estratégias.
        """
        self.logger.info(f"[BUSCA] ========== INICIANDO BUSCA ==========")
        self.logger.info(f"[BUSCA] Processo: {numero_processo}")
        
        numero_normalizado = self._normalizar_numero(numero_processo)
        if not numero_normalizado:
            self.logger.error(f"[BUSCA] ❌ Número de processo inválido: {numero_processo}")
            return ResultadoBusca(numero_processo=numero_processo)
        
        self.logger.debug(f"[BUSCA] Número normalizado: {numero_normalizado}")
        
        # Verificar cache
        if usar_cache and numero_normalizado in self._cache_resultados:
            cached = self._cache_resultados[numero_normalizado]
            self.logger.info(f"[BUSCA] ✓ Cache hit (ID={cached.id_processo})")
            return cached
        
        # Definir métodos de busca
        # MUDANÇA: api_processo primeiro por ser mais confiável
        # NOTA: etiquetas removido por ser muito lento
        if metodos is None:
            metodos = ['api_processo', 'painel_tarefas', 'busca_direta']
        
        self.logger.info(f"[BUSCA] Métodos a utilizar: {metodos}")
        
        resultado = ResultadoBusca(numero_processo=numero_normalizado)
        
        for i, metodo in enumerate(metodos, 1):
            self.logger.info(f"[BUSCA] [{i}/{len(metodos)}] ===== Método: {metodo} =====")
            
            try:
                if metodo == 'api_processo':
                    resultado = self._buscar_via_api_processo(numero_normalizado)
                elif metodo == 'busca_direta':
                    resultado = self._buscar_via_consulta_direta(numero_normalizado)
                elif metodo == 'consulta_publica':
                    resultado = self._buscar_via_consulta_publica(numero_normalizado)
                elif metodo == 'painel_tarefas':
                    resultado = self._buscar_via_painel_tarefas(numero_normalizado)
                elif metodo == 'etiquetas':
                    resultado = self._buscar_via_etiquetas(numero_normalizado)
                else:
                    self.logger.warning(f"[BUSCA] ⚠️ Método desconhecido: {metodo}")
                    continue
                
                if resultado.encontrado:
                    self.logger.info(f"[BUSCA] ✅ SUCESSO via {metodo}!")
                    self.logger.info(f"[BUSCA]    ID={resultado.id_processo}")
                    self.logger.info(f"[BUSCA]    CA={resultado.chave_acesso[:30] + '...' if resultado.chave_acesso else 'N/A'}")
                    break
                else:
                    self.logger.info(f"[BUSCA] ❌ Não encontrado via {metodo}")
                    
            except Exception as e:
                self.logger.error(f"[BUSCA] ❌ Erro no método {metodo}: {type(e).__name__}: {str(e)}")
                import traceback
                self.logger.debug(f"[BUSCA] Traceback:\n{traceback.format_exc()}")
        
        # Salvar no cache
        if usar_cache:
            self._cache_resultados[numero_normalizado] = resultado
        
        if not resultado.encontrado:
            self.logger.warning(f"[BUSCA] ⚠️ PROCESSO NÃO ENCONTRADO após todos os métodos")
        
        self.logger.info(f"[BUSCA] ========== FIM DA BUSCA ==========")
        return resultado
    
    def _normalizar_numero(self, numero: str) -> Optional[str]:
        """Normaliza número do processo para formato CNJ."""
        numero = numero.strip()
        
        if re.match(r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$', numero):
            return numero
        
        apenas_numeros = re.sub(r'[^\d]', '', numero)
        
        if len(apenas_numeros) != 20:
            self.logger.debug(f"[NORMALIZAR] Esperado 20 dígitos, encontrado {len(apenas_numeros)}")
            return None
        
        return (
            f"{apenas_numeros[:7]}-{apenas_numeros[7:9]}."
            f"{apenas_numeros[9:13]}.{apenas_numeros[13]}."
            f"{apenas_numeros[14:16]}.{apenas_numeros[16:20]}"
        )
    
    def _buscar_via_api_processo(self, numero_processo: str) -> ResultadoBusca:
        """
        Busca processo via múltiplos endpoints da API REST do PJE.
        
        Tenta diversos endpoints conhecidos e possíveis para encontrar
        o idProcesso a partir do número CNJ.
        """
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        self.logger.info(f"[API_PROCESSO] ----- Iniciando -----")
        self.logger.info(f"[API_PROCESSO] Buscando: {numero_processo}")
        
        # Lista de endpoints para tentar (ordem de prioridade)
        # Formato: (endpoint, método, dados)
        endpoints_para_tentar = [
            # Endpoints REST conhecidos
            ("GET", f"consultaProcessual/processo/{numero_processo}", None),
            ("GET", f"processo/numero/{numero_processo}", None),
            ("GET", f"processo/{numero_processo}", None),
            ("GET", f"processos/{numero_processo}", None),
            ("GET", f"consulta/processo/{numero_processo}", None),
            
            # Endpoints com POST
            ("POST", "painelUsuario/processo", {"numeroProcesso": numero_processo}),
            ("POST", "painelUsuario/buscarProcessos", {"numeroProcesso": numero_processo, "page": 0, "maxResults": 10}),
            ("POST", "consultaProcessual/pesquisar", {"numeroProcesso": numero_processo}),
            ("POST", "processo/pesquisar", {"numeroProcesso": numero_processo}),
            ("POST", "processo/buscar", {"numeroProcesso": numero_processo}),
            
            # Endpoints legados
            ("GET", f"seam/resource/rest/pje-legacy/processo/{numero_processo}", None),
            ("GET", f"seam/resource/rest/pje-legacy/consultaProcessual/{numero_processo}", None),
            ("POST", "seam/resource/rest/pje-legacy/processo/buscar", {"numeroProcesso": numero_processo}),
            
            # Outros possíveis
            ("GET", f"api/processo/{numero_processo}", None),
            ("GET", f"api/processos/numero/{numero_processo}", None),
            ("POST", "api/processo/buscar", {"numeroProcesso": numero_processo}),
        ]
        
        try:
            for i, (metodo, endpoint, dados) in enumerate(endpoints_para_tentar, 1):
                self.logger.debug(f"[API_PROCESSO] [{i}/{len(endpoints_para_tentar)}] Tentando: {metodo} {endpoint}")
                
                try:
                    if metodo == "GET":
                        resp = self.client.api_get(endpoint)
                    else:  # POST
                        resp = self.client.api_post(endpoint, dados)
                    
                    self.logger.debug(f"[API_PROCESSO]   Response: HTTP {resp.status_code}")
                    
                    # Salvar resposta para debug
                    self._salvar_html_debug(
                        resp.text, 
                        f"api_{endpoint.replace('/', '_')[:50]}", 
                        numero_processo
                    )
                    
                    if resp.status_code == 200:
                        # Tentar extrair idProcesso da resposta
                        id_processo = self._extrair_id_processo_de_resposta(resp.text, numero_processo)
                        
                        if id_processo:
                            resultado.encontrado = True
                            resultado.id_processo = id_processo
                            resultado.metodo_busca = f"api_{endpoint.split('/')[0]}"
                            
                            # Gerar chave de acesso
                            resultado.chave_acesso = self.gerar_chave_acesso(id_processo) or ""
                            
                            self.logger.info(f"[API_PROCESSO] ✅ Encontrado via {endpoint}!")
                            self.logger.info(f"[API_PROCESSO]   idProcesso: {id_processo}")
                            return resultado
                    
                    elif resp.status_code == 404:
                        self.logger.debug(f"[API_PROCESSO]   Endpoint não existe ou processo não encontrado")
                    
                    elif resp.status_code == 403:
                        self.logger.debug(f"[API_PROCESSO]   Sem permissão para este endpoint")
                    
                except Exception as e:
                    self.logger.debug(f"[API_PROCESSO]   Erro: {type(e).__name__}: {str(e)[:50]}")
                    continue
            
            self.logger.info("[API_PROCESSO] ❌ Não encontrado em nenhum endpoint de API")
            return resultado
            
        except Exception as e:
            self.logger.error(f"[API_PROCESSO] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.debug(f"[API_PROCESSO] Traceback:\n{traceback.format_exc()}")
            return resultado
    
    def _extrair_id_processo_de_resposta(self, texto: str, numero_processo: str) -> Optional[int]:
        """
        Tenta extrair o idProcesso de uma resposta da API.
        
        Suporta:
        - JSON com campo idProcesso, id, idProcessoTrf
        - JSON com lista de processos
        - Texto com padrão idProcesso=XXXXX
        """
        import json
        
        # Tentar parsear como JSON
        try:
            data = json.loads(texto)
            
            # Se for dict direto
            if isinstance(data, dict):
                # Verificar se é o processo correto
                num_proc = data.get("numeroProcesso", "")
                if num_proc and num_proc != numero_processo:
                    self.logger.debug(f"[EXTRAIR_ID] Processo diferente: {num_proc}")
                    return None
                
                # Extrair ID
                for campo in ["idProcesso", "id", "idProcessoTrf", "idProcessoDocumento"]:
                    if campo in data and data[campo]:
                        return int(data[campo])
            
            # Se for lista
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        num_proc = item.get("numeroProcesso", "")
                        if num_proc == numero_processo:
                            for campo in ["idProcesso", "id", "idProcessoTrf"]:
                                if campo in item and item[campo]:
                                    return int(item[campo])
            
            # Se tiver entities (paginado)
            if isinstance(data, dict) and "entities" in data:
                for item in data["entities"]:
                    if isinstance(item, dict):
                        num_proc = item.get("numeroProcesso", "")
                        if num_proc == numero_processo:
                            for campo in ["idProcesso", "id", "idProcessoTrf"]:
                                if campo in item and item[campo]:
                                    return int(item[campo])
        except json.JSONDecodeError:
            pass
        
        # Tentar extrair com regex
        patterns = [
            rf'"idProcesso"\s*:\s*(\d+)',
            rf'"id"\s*:\s*(\d+)',
            rf'idProcesso["\']?\s*[:=]\s*["\']?(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texto)
            if match:
                return int(match.group(1))
        
        return None

    def _extrair_partes_numero(self, numero: str) -> Optional[Dict[str, str]]:
        """Extrai partes do número CNJ para campos do formulário."""
        match = re.match(
            r'^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$', 
            numero
        )
        
        if not match:
            self.logger.debug(f"[PARTES] Não extraiu partes de: {numero}")
            return None
        
        partes = {
            "sequencial": match.group(1),
            "digito": match.group(2),
            "ano": match.group(3),
            "segmento": match.group(4),
            "tribunal": match.group(5),
            "origem": match.group(6)
        }
        
        self.logger.debug(f"[PARTES] seq={partes['sequencial']} dig={partes['digito']} ano={partes['ano']} seg={partes['segmento']} trib={partes['tribunal']} orig={partes['origem']}")
        
        return partes

    def _buscar_via_consulta_direta(self, numero_processo: str) -> ResultadoBusca:
        """
        Busca processo via endpoint de consulta direta.
        
        VERSÃO MELHORADA: Faz 2 requisições:
        1. Busca o processo no formulário
        2. Clica no resultado para obter idProcesso e ca
        """
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        self.logger.info(f"[BUSCA_DIRETA] ----- Iniciando -----")
        
        try:
            partes = self._extrair_partes_numero(numero_processo)
            if not partes:
                self.logger.error(f"[BUSCA_DIRETA] ❌ Falha ao extrair partes do número")
                return resultado
            
            # 1. Acessar página de consulta pública
            url_consulta = f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam"
            self.logger.info(f"[BUSCA_DIRETA] [1/4] Acessando página de consulta...")
            
            resp = self.client.session.get(
                url_consulta,
                params={"iframe": "true"},
                timeout=self.client.timeout
            )
            
            self.logger.info(f"[BUSCA_DIRETA] Response: HTTP {resp.status_code} ({len(resp.text)} bytes)")
            
            # Salvar HTML da página inicial para debug
            self._salvar_html_debug(resp.text, "busca_direta_pagina_inicial", numero_processo)
            
            if resp.status_code != 200:
                self.logger.error(f"[BUSCA_DIRETA] ❌ Erro HTTP {resp.status_code}")
                return resultado
            
            viewstate = extrair_viewstate(resp.text)
            if not viewstate:
                self.logger.error("[BUSCA_DIRETA] ❌ ViewState não encontrado!")
                return resultado
            
            self.logger.debug(f"[BUSCA_DIRETA] ViewState OK: {viewstate[:50]}...")
            
            delay(0.5, 1.0)
            
            # 2. Fazer a busca preenchendo os campos do formulário
            self.logger.info(f"[BUSCA_DIRETA] [2/4] Enviando formulário de busca...")
            
            # Encontrar o ID correto do botão de pesquisa analisando o HTML
            button_id = self._encontrar_botao_pesquisa(resp.text)
            self.logger.debug(f"[BUSCA_DIRETA] Botão de pesquisa: {button_id}")
            
            form_data = {
                "AJAXREQUEST": "_viewRoot",
                "fPP": "fPP",
                "fPP:numeroProcesso:numeroSequencial": partes["sequencial"],
                "fPP:numeroProcesso:numeroDigitoVerificador": partes["digito"],
                "fPP:numeroProcesso:Ano": partes["ano"],
                "fPP:numeroProcesso:ramoJustica": partes["segmento"],
                "fPP:numeroProcesso:respectivoTribunal": partes["tribunal"],
                "fPP:numeroProcesso:NumeroOrgaoJustica": partes["origem"],
                "fPP:j_id150:nomeParte": "",
                "fPP:decorationDados:ufOABCombo": "org.jboss.seam.ui.NoSelectionConverter.noSelectionValue",
                "fPP:jurisdicaoComboDecoration:jurisdicaoCombo": "org.jboss.seam.ui.NoSelectionConverter.noSelectionValue",
                "fPP:orgaoJulgadorComboDecoration:orgaoJulgadorCombo": "org.jboss.seam.ui.NoSelectionConverter.noSelectionValue",
                "fPP:processoReferenciaDecoration:habilitarMascaraProcessoReferencia": "true",
                "fPP:dataAutuacaoDecoration:dataAutuacaoInicioInputCurrentDate": "",
                "fPP:dataAutuacaoDecoration:dataAutuacaoFimInputCurrentDate": "",
                "tipoMascaraDocumento": "on",
                button_id: button_id,
                "javax.faces.ViewState": viewstate,
                "AJAX:EVENTS_COUNT": "1"
            }
            
            resp_busca = self.client.session.post(
                url_consulta,
                data=form_data,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam?iframe=true"
                }
            )
            
            self.logger.info(f"[BUSCA_DIRETA] Response: HTTP {resp_busca.status_code} ({len(resp_busca.text)} bytes)")
            
            # Salvar HTML da resposta da busca para debug
            self._salvar_html_debug(resp_busca.text, "busca_direta_resposta_busca", numero_processo)
            
            if resp_busca.status_code != 200:
                self.logger.error(f"[BUSCA_DIRETA] ❌ Erro HTTP {resp_busca.status_code}")
                return resultado
            
            html = resp_busca.text
            
            # 3. Analisar resposta - procurar linha na tabela
            self.logger.info(f"[BUSCA_DIRETA] [3/4] Analisando resposta...")
            
            # Verificar se há erro
            if "Nenhum processo encontrado" in html or "não foi localizado" in html.lower():
                self.logger.info("[BUSCA_DIRETA] ❌ Processo não encontrado na consulta")
                return resultado
            
            # Procurar por linha de resultado na tabela (tbody > tr)
            # O padrão é: fPP:processosTable:0:j_id467 (onde 0 é o índice da linha)
            row_pattern = r'fPP:processosTable:(\d+):j_id(\d+)'
            row_matches = re.findall(row_pattern, html)
            
            self.logger.debug(f"[BUSCA_DIRETA] Linhas encontradas na tabela: {len(row_matches)}")
            
            if not row_matches:
                self.logger.debug("[BUSCA_DIRETA] Análise do HTML:")
                self.logger.debug(f"[BUSCA_DIRETA]   Contém 'processosTable': {'processosTable' in html}")
                self.logger.debug(f"[BUSCA_DIRETA]   Contém 'rich-table-row': {'rich-table-row' in html}")
                self.logger.debug(f"[BUSCA_DIRETA]   Contém 'tbody': {'tbody' in html}")
                
                # Procurar por outras estruturas
                if 'rich-table-row' in html:
                    self.logger.debug("[BUSCA_DIRETA] Há linhas mas sem o padrão esperado")
                
                return resultado
            
            # Pegar a primeira linha (índice 0)
            row_index = row_matches[0][0]
            row_j_id = row_matches[0][1]
            
            self.logger.debug(f"[BUSCA_DIRETA] Primeira linha: índice={row_index}, j_id={row_j_id}")
            
            # Atualizar viewstate se houver um novo
            new_viewstate = extrair_viewstate(html)
            if new_viewstate:
                viewstate = new_viewstate
            
            delay(0.3, 0.6)
            
            # 4. Clicar no processo para obter idProcesso e ca
            self.logger.info(f"[BUSCA_DIRETA] [4/4] Clicando no resultado para obter idProcesso e ca...")
            
            # O elemento clicável geralmente é um link na primeira coluna
            click_element = f"fPP:processosTable:{row_index}:j_id{row_j_id}"
            
            click_data = {
                "AJAXREQUEST": "_viewRoot",
                "fPP": "fPP",
                click_element: click_element,
                "javax.faces.ViewState": viewstate,
                "AJAX:EVENTS_COUNT": "1"
            }
            
            resp_click = self.client.session.post(
                url_consulta,
                data=click_data,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam?iframe=true"
                }
            )
            
            self.logger.info(f"[BUSCA_DIRETA] Click Response: HTTP {resp_click.status_code} ({len(resp_click.text)} bytes)")
            
            # Salvar HTML da resposta do click para debug
            self._salvar_html_debug(resp_click.text, "busca_direta_resposta_click", numero_processo)
            
            if resp_click.status_code == 200:
                click_html = resp_click.text
                
                # Procurar link com idProcesso e ca
                link_pattern = r'listAutosDigitais\.seam\?idProcesso=(\d+)(?:&amp;|&)ca=([a-f0-9]+)'
                link_match = re.search(link_pattern, click_html)
                
                if link_match:
                    resultado.encontrado = True
                    resultado.id_processo = int(link_match.group(1))
                    resultado.chave_acesso = link_match.group(2)
                    resultado.metodo_busca = "busca_direta"
                    self.logger.info(f"[BUSCA_DIRETA] ✅ Encontrado!")
                    self.logger.info(f"[BUSCA_DIRETA]   ID: {resultado.id_processo}")
                    self.logger.info(f"[BUSCA_DIRETA]   CA: {resultado.chave_acesso[:30]}...")
                    return resultado
                
                # Procurar só idProcesso
                id_pattern = r'idProcesso["\']?\s*[:=]\s*["\']?(\d+)'
                id_match = re.search(id_pattern, click_html)
                
                if id_match:
                    resultado.id_processo = int(id_match.group(1))
                    self.logger.debug(f"[BUSCA_DIRETA] idProcesso encontrado: {resultado.id_processo}")
                    
                    # Gerar chave via API
                    resultado.chave_acesso = self.gerar_chave_acesso(resultado.id_processo) or ""
                    
                    if resultado.id_processo > 0:
                        resultado.encontrado = True
                        resultado.metodo_busca = "busca_direta"
                        self.logger.info(f"[BUSCA_DIRETA] ✅ Encontrado (sem ca direto)!")
                        return resultado
                
                # Log para debug
                self.logger.debug("[BUSCA_DIRETA] Padrões não encontrados no click response")
                self.logger.debug(f"[BUSCA_DIRETA] Contém 'listAutosDigitais': {'listAutosDigitais' in click_html}")
                self.logger.debug(f"[BUSCA_DIRETA] Contém 'idProcesso': {'idProcesso' in click_html}")
            
            self.logger.info("[BUSCA_DIRETA] ❌ Não foi possível obter idProcesso e ca")
            return resultado
            
        except Exception as e:
            self.logger.error(f"[BUSCA_DIRETA] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.error(f"[BUSCA_DIRETA] Traceback:\n{traceback.format_exc()}")
            return resultado
    
    def _encontrar_botao_pesquisa(self, html: str) -> str:
        """Encontra o ID do botão de pesquisa no formulário."""
        # Procurar por botões de submit no formulário
        # Padrão comum: fPP:j_id455 ou similar
        patterns = [
            r'(fPP:j_id\d+)"\s*(?:type="submit"|value="Pesquisar")',
            r'(fPP:j_id\d+).*?Pesquisar',
            r'name="(fPP:j_id\d+)".*?submit',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Default
        return "fPP:j_id455"

    def _buscar_via_consulta_publica(self, numero_processo: str) -> ResultadoBusca:
        """Busca processo via página de consulta pública (método alternativo)."""
        # Usar mesmo código do busca_direta
        return self._buscar_via_consulta_direta(numero_processo)

    def _buscar_via_painel_tarefas(self, numero_processo: str) -> ResultadoBusca:
        """Busca processo no painel de tarefas do usuário."""
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        self.logger.info(f"[PAINEL_TAREFAS] ----- Iniciando -----")
        
        try:
            self.logger.debug("[PAINEL_TAREFAS] Obtendo lista de tarefas...")
            
            resp_tarefas = self.client.api_post(
                "painelUsuario/tarefas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            
            self.logger.info(f"[PAINEL_TAREFAS] Response tarefas: HTTP {resp_tarefas.status_code}")
            
            if resp_tarefas.status_code != 200:
                self.logger.error(f"[PAINEL_TAREFAS] ❌ Erro HTTP {resp_tarefas.status_code}")
                return resultado
            
            tarefas = resp_tarefas.json()
            self.logger.info(f"[PAINEL_TAREFAS] Total de tarefas: {len(tarefas)}")
            
            # Buscar em cada tarefa
            for i, tarefa in enumerate(tarefas[:10], 1):
                nome_tarefa = tarefa.get("nome", "")
                qtd = tarefa.get("quantidadePendente", 0)
                
                if not nome_tarefa:
                    continue
                
                self.logger.debug(f"[PAINEL_TAREFAS] [{i}/10] Tarefa: '{nome_tarefa}' ({qtd} pendentes)")
                
                from urllib.parse import quote
                endpoint = f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{quote(nome_tarefa)}/false"
                
                resp_proc = self.client.api_post(
                    endpoint,
                    {
                        "numeroProcesso": numero_processo,
                        "classe": None,
                        "tags": [],
                        "page": 0,
                        "maxResults": 1,
                        "competencia": ""
                    }
                )
                
                if resp_proc.status_code == 200:
                    data = resp_proc.json()
                    entities = data.get("entities", [])
                    
                    self.logger.debug(f"[PAINEL_TAREFAS]   Resultados: {len(entities)}")
                    
                    if entities:
                        proc = entities[0]
                        if proc.get("numeroProcesso") == numero_processo:
                            resultado.encontrado = True
                            resultado.id_processo = proc.get("idProcesso", 0)
                            resultado.metodo_busca = "painel_tarefas"
                            resultado.detalhes["tarefa"] = nome_tarefa
                            
                            # Gerar chave de acesso
                            resultado.chave_acesso = self.gerar_chave_acesso(resultado.id_processo) or ""
                            
                            self.logger.info(f"[PAINEL_TAREFAS] ✅ Encontrado na tarefa '{nome_tarefa}'!")
                            return resultado
                else:
                    self.logger.debug(f"[PAINEL_TAREFAS]   Erro HTTP {resp_proc.status_code}")
            
            # Tentar nas favoritas
            self.logger.debug("[PAINEL_TAREFAS] Buscando nas favoritas...")
            
            resp_fav = self.client.api_post(
                "painelUsuario/tarefasFavoritas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            
            if resp_fav.status_code == 200:
                tarefas_fav = resp_fav.json()
                self.logger.info(f"[PAINEL_TAREFAS] Total de favoritas: {len(tarefas_fav)}")
                
                for i, tarefa in enumerate(tarefas_fav[:5], 1):
                    nome_tarefa = tarefa.get("nome", "")
                    if not nome_tarefa:
                        continue
                    
                    self.logger.debug(f"[PAINEL_TAREFAS] [{i}/5] Favorita: '{nome_tarefa}'")
                    
                    from urllib.parse import quote
                    endpoint = f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{quote(nome_tarefa)}/true"
                    
                    resp_proc = self.client.api_post(
                        endpoint,
                        {"numeroProcesso": numero_processo, "page": 0, "maxResults": 1}
                    )
                    
                    if resp_proc.status_code == 200:
                        data = resp_proc.json()
                        entities = data.get("entities", [])
                        
                        if entities:
                            proc = entities[0]
                            if proc.get("numeroProcesso") == numero_processo:
                                resultado.encontrado = True
                                resultado.id_processo = proc.get("idProcesso", 0)
                                resultado.metodo_busca = "painel_tarefas_favoritas"
                                resultado.detalhes["tarefa"] = nome_tarefa
                                resultado.chave_acesso = self.gerar_chave_acesso(resultado.id_processo) or ""
                                self.logger.info(f"[PAINEL_TAREFAS] ✅ Encontrado na favorita '{nome_tarefa}'!")
                                return resultado
            
            self.logger.info("[PAINEL_TAREFAS] ❌ Não encontrado em nenhuma tarefa")
            return resultado
            
        except Exception as e:
            self.logger.error(f"[PAINEL_TAREFAS] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.debug(f"[PAINEL_TAREFAS] Traceback:\n{traceback.format_exc()}")
            return resultado

    def _buscar_via_etiquetas(self, numero_processo: str) -> ResultadoBusca:
        """Busca processo nas etiquetas do usuário."""
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        self.logger.info(f"[ETIQUETAS] ----- Iniciando -----")
        
        try:
            self.logger.debug("[ETIQUETAS] Obtendo lista de etiquetas...")
            
            resp_etiquetas = self.client.api_post(
                "painelUsuario/etiquetas",
                {"page": 0, "maxResults": 50, "tagsString": ""}
            )
            
            self.logger.info(f"[ETIQUETAS] Response: HTTP {resp_etiquetas.status_code}")
            
            if resp_etiquetas.status_code != 200:
                self.logger.error(f"[ETIQUETAS] ❌ Erro HTTP {resp_etiquetas.status_code}")
                return resultado
            
            data = resp_etiquetas.json()
            etiquetas = data.get("entities", [])
            
            self.logger.info(f"[ETIQUETAS] Total de etiquetas: {len(etiquetas)}")
            
            for i, etiqueta in enumerate(etiquetas[:15], 1):
                id_etiqueta = etiqueta.get("id")
                nome_etiqueta = etiqueta.get("nomeTag", "")
                
                if not id_etiqueta:
                    continue
                
                self.logger.debug(f"[ETIQUETAS] [{i}/15] Etiqueta: '{nome_etiqueta}' (ID={id_etiqueta})")
                
                resp_proc = self.client.api_get(
                    f"painelUsuario/etiquetas/{id_etiqueta}/processos",
                    params={"limit": 500}
                )
                
                if resp_proc.status_code == 200:
                    processos = resp_proc.json()
                    self.logger.debug(f"[ETIQUETAS]   Processos: {len(processos)}")
                    
                    for proc in processos:
                        if proc.get("numeroProcesso") == numero_processo:
                            resultado.encontrado = True
                            resultado.id_processo = proc.get("idProcesso", 0)
                            resultado.metodo_busca = "etiquetas"
                            resultado.detalhes["etiqueta"] = nome_etiqueta
                            resultado.chave_acesso = self.gerar_chave_acesso(resultado.id_processo) or ""
                            self.logger.info(f"[ETIQUETAS] ✅ Encontrado na etiqueta '{nome_etiqueta}'!")
                            return resultado
                else:
                    self.logger.debug(f"[ETIQUETAS]   Erro HTTP {resp_proc.status_code}")
            
            self.logger.info("[ETIQUETAS] ❌ Não encontrado em nenhuma etiqueta")
            return resultado
            
        except Exception as e:
            self.logger.error(f"[ETIQUETAS] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.debug(f"[ETIQUETAS] Traceback:\n{traceback.format_exc()}")
            return resultado

    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """Gera chave de acesso para um processo já conhecido."""
        self.logger.debug(f"[GERAR_CA] Gerando chave para ID={id_processo}")
        
        try:
            resp = self.client.api_get(f"painelUsuario/gerarChaveAcessoProcesso/{id_processo}")
            
            self.logger.debug(f"[GERAR_CA] Response: HTTP {resp.status_code}")
            
            if resp.status_code == 200:
                chave = resp.text.strip().strip('"')
                self.logger.debug(f"[GERAR_CA] ✅ Chave: {chave[:30]}...")
                return chave
            else:
                self.logger.debug(f"[GERAR_CA] ❌ Erro HTTP {resp.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"[GERAR_CA] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            return None

    def acessar_processo_direto(self, id_processo: int, chave_acesso: str) -> Optional[str]:
        """Acessa diretamente a página de autos digitais do processo."""
        self.logger.info(f"[ACESSAR_DIRETO] Acessando processo ID={id_processo}")
        
        try:
            url = (
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/Detalhe/"
                f"listAutosDigitais.seam?idProcesso={id_processo}&ca={chave_acesso}&aba="
            )
            
            self.logger.debug(f"[ACESSAR_DIRETO] URL: {url}")
            
            resp = self.client.session.get(
                url, timeout=self.client.timeout,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam?iframe=true"
                }
            )
            
            self.logger.info(f"[ACESSAR_DIRETO] Response: HTTP {resp.status_code} ({len(resp.text)} bytes)")
            
            if resp.status_code == 200:
                self.logger.info(f"[ACESSAR_DIRETO] ✅ Sucesso!")
                return resp.text
            else:
                self.logger.error(f"[ACESSAR_DIRETO] ❌ Erro HTTP {resp.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"[ACESSAR_DIRETO] ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}")
            return None

    def buscar_e_acessar_processo(self, numero_processo: str) -> Tuple[ResultadoBusca, Optional[str]]:
        """Busca e acessa diretamente um processo."""
        self.logger.info(f"[BUSCAR_E_ACESSAR] ========== INICIANDO ==========")
        self.logger.info(f"[BUSCAR_E_ACESSAR] Processo: {numero_processo}")
        
        resultado = self.buscar_processo(numero_processo)
        
        if not resultado.encontrado:
            self.logger.warning(f"[BUSCAR_E_ACESSAR] ❌ Processo não encontrado")
            return resultado, None
        
        if not resultado.chave_acesso:
            self.logger.debug("[BUSCAR_E_ACESSAR] Sem chave, tentando gerar...")
            resultado.chave_acesso = self.gerar_chave_acesso(resultado.id_processo) or ""
        
        if resultado.id_processo and resultado.chave_acesso:
            html = self.acessar_processo_direto(resultado.id_processo, resultado.chave_acesso)
            self.logger.info(f"[BUSCAR_E_ACESSAR] ========== FIM ==========")
            return resultado, html
        
        self.logger.warning("[BUSCAR_E_ACESSAR] ⚠️ Sem chave de acesso, não foi possível acessar")
        return resultado, None