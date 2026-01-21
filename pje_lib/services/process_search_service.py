"""
Serviço especializado para busca de processos por número.

Este serviço implementa múltiplas estratégias para localizar processos:
1. Consulta pública via página de pesquisa
2. Busca via painel de tarefas do usuário
3. Busca via etiquetas do usuário
"""

import re
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from ..config import BASE_URL
from ..core import PJEHttpClient
from ..utils import delay, extrair_viewstate, get_logger


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
    
    Implementa múltiplas estratégias de busca para maximizar
    a chance de encontrar o processo.
    """
    
    def __init__(self, http_client: PJEHttpClient):
        self.client = http_client
        self.logger = get_logger()
        self._cache_resultados: Dict[str, ResultadoBusca] = {}
    
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
        
        Args:
            numero_processo: Número do processo no formato CNJ
            usar_cache: Se deve usar cache de buscas anteriores
            metodos: Lista de métodos a usar. Default: todos.
                    Opções: ['consulta_publica', 'painel_tarefas', 'etiquetas']
        
        Returns:
            ResultadoBusca com informações do processo
        """
        numero_normalizado = self._normalizar_numero(numero_processo)
        if not numero_normalizado:
            self.logger.error(f"Número de processo inválido: {numero_processo}")
            return ResultadoBusca(numero_processo=numero_processo)
        
        # Verificar cache
        if usar_cache and numero_normalizado in self._cache_resultados:
            cached = self._cache_resultados[numero_normalizado]
            self.logger.debug(f"Cache hit para {numero_normalizado}")
            return cached
        
        # Definir métodos de busca
        if metodos is None:
            metodos = ['consulta_publica', 'painel_tarefas', 'etiquetas']
        
        resultado = ResultadoBusca(numero_processo=numero_normalizado)
        
        for metodo in metodos:
            if metodo == 'consulta_publica':
                resultado = self._buscar_via_consulta_publica(numero_normalizado)
            elif metodo == 'painel_tarefas':
                resultado = self._buscar_via_painel_tarefas(numero_normalizado)
            elif metodo == 'etiquetas':
                resultado = self._buscar_via_etiquetas(numero_normalizado)
            
            if resultado.encontrado:
                self.logger.info(
                    f"Processo {numero_normalizado} encontrado via {metodo}: "
                    f"ID={resultado.id_processo}"
                )
                break
        
        # Salvar no cache
        if usar_cache:
            self._cache_resultados[numero_normalizado] = resultado
        
        return resultado
    
    def _normalizar_numero(self, numero: str) -> Optional[str]:
        """
        Normaliza número do processo para formato CNJ.
        
        Aceita:
        - NNNNNNN-DD.AAAA.J.TR.OOOO (formatado)
        - NNNNNNNDDAAAAJTROOOO (apenas números)
        
        Retorna formato: NNNNNNN-DD.AAAA.J.TR.OOOO
        """
        # Remover espaços
        numero = numero.strip()
        
        # Se já está formatado
        if re.match(r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$', numero):
            return numero
        
        # Extrair apenas números
        apenas_numeros = re.sub(r'[^\d]', '', numero)
        
        if len(apenas_numeros) != 20:
            return None
        
        # Formatar
        return (
            f"{apenas_numeros[:7]}-{apenas_numeros[7:9]}."
            f"{apenas_numeros[9:13]}.{apenas_numeros[13]}."
            f"{apenas_numeros[14:16]}.{apenas_numeros[16:20]}"
        )
    
    def _extrair_partes_numero(self, numero: str) -> Optional[Dict[str, str]]:
        """
        Extrai partes do número CNJ para campos do formulário.
        
        Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
        - NNNNNNN: Número sequencial (7 dígitos)
        - DD: Dígito verificador (2 dígitos)
        - AAAA: Ano do ajuizamento (4 dígitos)
        - J: Segmento do Judiciário (1 dígito)
        - TR: Tribunal (2 dígitos)
        - OOOO: Origem (4 dígitos)
        """
        match = re.match(
            r'^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$', 
            numero
        )
        
        if not match:
            return None
        
        return {
            "sequencial": match.group(1),
            "digito": match.group(2),
            "ano": match.group(3),
            "segmento": match.group(4),
            "tribunal": match.group(5),
            "origem": match.group(6)
        }
    
    def _buscar_via_consulta_publica(self, numero_processo: str) -> ResultadoBusca:
        """
        Busca processo via página de consulta pública.
        
        Este é o método mais confiável pois não depende do processo
        estar no painel do usuário.
        """
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        try:
            self.logger.debug(f"Buscando via consulta pública: {numero_processo}")
            
            # Extrair partes do número
            partes = self._extrair_partes_numero(numero_processo)
            if not partes:
                self.logger.error(f"Não foi possível extrair partes do número: {numero_processo}")
                return resultado
            
            # Acessar página de consulta
            resp = self.client.session.get(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam",
                params={"iframe": "true"},
                timeout=self.client.timeout
            )
            
            if resp.status_code != 200:
                self.logger.error(f"Erro ao acessar página de consulta: {resp.status_code}")
                return resultado
            
            viewstate = extrair_viewstate(resp.text)
            if not viewstate:
                self.logger.error("ViewState não encontrado na página de consulta")
                return resultado
            
            delay(0.5, 1.0)
            
            # Preparar dados do formulário
            form_data = self._montar_form_pesquisa(partes, viewstate)
            
            # Fazer busca
            resp_busca = self.client.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam",
                data=form_data,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam"
                }
            )
            
            if resp_busca.status_code != 200:
                self.logger.error(f"Erro na busca: {resp_busca.status_code}")
                return resultado
            
            # Extrair ID do processo da resposta
            id_processo = self._extrair_id_da_tabela(resp_busca.text)
            
            if id_processo:
                resultado.encontrado = True
                resultado.id_processo = id_processo
                resultado.metodo_busca = "consulta_publica"
                
                # Tentar obter chave de acesso clicando no resultado
                chave = self._obter_chave_acesso_click(
                    resp_busca.text, id_processo, viewstate
                )
                if chave:
                    resultado.chave_acesso = chave
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na busca via consulta pública: {e}")
            return resultado
    
    def _montar_form_pesquisa(
        self, 
        partes: Dict[str, str], 
        viewstate: str
    ) -> Dict[str, str]:
        """Monta dados do formulário de pesquisa."""
        return {
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
            "fPP:j_id455": "fPP:j_id455",  # Botão de pesquisa
            "javax.faces.ViewState": viewstate,
            "AJAX:EVENTS_COUNT": "1"
        }
    
    def _extrair_id_da_tabela(self, html: str) -> Optional[int]:
        """
        Extrai ID do processo da tabela de resultados.
        
        Procura por padrões como:
        - processosTable:{id}:j_id467
        - idProcessoSelecionado:{id}
        """
        # Padrão da tabela de resultados
        pattern = r'processosTable:(\d+):j_id\d+'
        match = re.search(pattern, html)
        
        if match:
            return int(match.group(1))
        
        # Padrão alternativo no onclick
        pattern2 = r"idProcessoSelecionado['\"]?\s*[:=]\s*(\d+)"
        match2 = re.search(pattern2, html)
        
        if match2:
            return int(match2.group(1))
        
        return None
    
    def _obter_chave_acesso_click(
        self, 
        html_tabela: str, 
        id_processo: int,
        viewstate: str
    ) -> Optional[str]:
        """
        Simula clique no resultado para obter chave de acesso.
        
        Após a busca inicial, um segundo POST retorna o link
        com a chave de acesso (ca).
        """
        try:
            # Encontrar o ID do elemento de click
            pattern = rf'fPP:processosTable:{id_processo}:(j_id\d+)'
            match = re.search(pattern, html_tabela)
            
            if not match:
                self.logger.debug("Elemento de click não encontrado")
                return None
            
            element_id = f"fPP:processosTable:{id_processo}:{match.group(1)}"
            
            delay(0.3, 0.6)
            
            # Fazer POST para obter link com chave de acesso
            form_data = {
                "AJAXREQUEST": "_viewRoot",
                "fPP": "fPP",
                element_id: element_id,
                "idProcessoSelecionado": str(id_processo),
                "ajaxSingle": element_id,
                "javax.faces.ViewState": viewstate,
            }
            
            resp = self.client.session.post(
                f"{BASE_URL}/pje/Processo/ConsultaProcesso/listView.seam",
                data=form_data,
                timeout=self.client.timeout,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": BASE_URL,
                }
            )
            
            if resp.status_code == 200:
                # Extrair chave de acesso
                # Padrão: &ca=xxx ou ca=xxx
                ca_pattern = r'[&?]ca=([a-f0-9]+)'
                ca_match = re.search(ca_pattern, resp.text)
                
                if ca_match:
                    return ca_match.group(1)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Erro ao obter chave de acesso: {e}")
            return None
    
    def _buscar_via_painel_tarefas(self, numero_processo: str) -> ResultadoBusca:
        """
        Busca processo no painel de tarefas do usuário.
        
        Procura o processo em todas as tarefas acessíveis.
        """
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        try:
            self.logger.debug(f"Buscando via painel de tarefas: {numero_processo}")
            
            # Primeiro, obter lista de tarefas
            resp_tarefas = self.client.api_post(
                "painelUsuario/tarefas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            
            if resp_tarefas.status_code != 200:
                return resultado
            
            tarefas = resp_tarefas.json()
            
            # Buscar em cada tarefa
            for tarefa in tarefas[:10]:  # Limitar a 10 tarefas
                nome_tarefa = tarefa.get("nome", "")
                if not nome_tarefa:
                    continue
                
                from urllib.parse import quote
                endpoint = (
                    f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/"
                    f"{quote(nome_tarefa)}/false"
                )
                
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
                    
                    if entities:
                        proc = entities[0]
                        if proc.get("numeroProcesso") == numero_processo:
                            resultado.encontrado = True
                            resultado.id_processo = proc.get("idProcesso", 0)
                            resultado.metodo_busca = "painel_tarefas"
                            resultado.detalhes["tarefa"] = nome_tarefa
                            return resultado
            
            # Tentar também nas favoritas
            resp_fav = self.client.api_post(
                "painelUsuario/tarefasFavoritas",
                {"numeroProcesso": "", "competencia": "", "etiquetas": []}
            )
            
            if resp_fav.status_code == 200:
                tarefas_fav = resp_fav.json()
                
                for tarefa in tarefas_fav[:5]:
                    nome_tarefa = tarefa.get("nome", "")
                    if not nome_tarefa:
                        continue
                    
                    from urllib.parse import quote
                    endpoint = (
                        f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/"
                        f"{quote(nome_tarefa)}/true"
                    )
                    
                    resp_proc = self.client.api_post(
                        endpoint,
                        {
                            "numeroProcesso": numero_processo,
                            "page": 0,
                            "maxResults": 1
                        }
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
                                return resultado
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na busca via painel: {e}")
            return resultado
    
    def _buscar_via_etiquetas(self, numero_processo: str) -> ResultadoBusca:
        """
        Busca processo nas etiquetas do usuário.
        """
        resultado = ResultadoBusca(numero_processo=numero_processo)
        
        try:
            self.logger.debug(f"Buscando via etiquetas: {numero_processo}")
            
            # Buscar etiquetas
            resp_etiquetas = self.client.api_post(
                "painelUsuario/etiquetas",
                {"page": 0, "maxResults": 50, "tagsString": ""}
            )
            
            if resp_etiquetas.status_code != 200:
                return resultado
            
            data = resp_etiquetas.json()
            etiquetas = data.get("entities", [])
            
            for etiqueta in etiquetas[:15]:
                id_etiqueta = etiqueta.get("id")
                if not id_etiqueta:
                    continue
                
                # Listar processos da etiqueta
                resp_proc = self.client.api_get(
                    f"painelUsuario/etiquetas/{id_etiqueta}/processos",
                    params={"limit": 500}
                )
                
                if resp_proc.status_code == 200:
                    processos = resp_proc.json()
                    
                    for proc in processos:
                        if proc.get("numeroProcesso") == numero_processo:
                            resultado.encontrado = True
                            resultado.id_processo = proc.get("idProcesso", 0)
                            resultado.metodo_busca = "etiquetas"
                            resultado.detalhes["etiqueta"] = etiqueta.get("nomeTag", "")
                            return resultado
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na busca via etiquetas: {e}")
            return resultado
    
    def gerar_chave_acesso(self, id_processo: int) -> Optional[str]:
        """
        Gera chave de acesso para um processo já conhecido.
        
        Útil quando temos o ID mas não temos a chave de acesso.
        """
        try:
            resp = self.client.api_get(
                f"painelUsuario/gerarChaveAcessoProcesso/{id_processo}"
            )
            
            if resp.status_code == 200:
                return resp.text.strip().strip('"')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar chave de acesso: {e}")
            return None
