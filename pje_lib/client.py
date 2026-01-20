"""
Cliente principal do PJE - Interface unificada.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Generator, Set
import time
import os
import re

from .config import DEFAULT_TIMEOUT, API_BASE, BASE_URL
from .core import SessionManager, PJEHttpClient
from .services import AuthService, TaskService, TagService, DownloadService
from .models import (
    Usuario, Perfil, Tarefa, ProcessoTarefa, 
    Etiqueta, Processo, DownloadDisponivel
)
from .utils import delay, normalizar_nome_pasta, save_json, timestamp_str, get_logger, extrair_viewstate


class PJEClient:
    """Cliente principal para automacao do PJE."""
    
    def __init__(
        self,
        download_dir: str = "./downloads",
        log_dir: str = "./.logs",
        session_dir: str = "./.session",
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = True
    ):
        self.timeout = timeout
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger("pje", self.log_dir, debug)
        
        self._http = PJEHttpClient(timeout)
        self._session = SessionManager(session_dir)
        
        self._auth = AuthService(self._http, self._session)
        self._tasks = TaskService(self._http)
        self._tags = TagService(self._http)
        self._downloads = DownloadService(self._http, self.download_dir)
        
        self._progress_callback: Optional[Callable[[int, int, str, str], None]] = None
        self._cancelar = False
        
        self.max_retries = 2
        self.retry_delay = 5
        
        self.logger.info(f"PJEClient inicializado. Downloads: {self.download_dir}")
    
    @property
    def usuario(self) -> Optional[Usuario]:
        return self._auth.usuario
    
    @property
    def perfis(self) -> List[Perfil]:
        return self._auth.perfis_disponiveis
    
    @property
    def tarefas(self) -> List[Tarefa]:
        return self._tasks.tarefas_cache
    
    @property
    def tarefas_favoritas(self) -> List[Tarefa]:
        return self._tasks.tarefas_favoritas_cache
    
    def set_progress_callback(self, callback: Callable[[int, int, str, str], None]):
        self._progress_callback = callback
    
    def _notify_progress(self, atual: int, total: int, numero_processo: str, status: str):
        if self._progress_callback:
            try:
                self._progress_callback(atual, total, numero_processo, status)
            except Exception:
                pass
    
    def cancelar_processamento(self):
        """Marca flag de cancelamento."""
        self._cancelar = True
        self.logger.info("Cancelamento solicitado pelo usuario")
    
    def _reset_cancelamento(self):
        """Reseta flag de cancelamento."""
        self._cancelar = False
    
    def _check_cancelado(self) -> bool:
        """Verifica se foi solicitado cancelamento."""
        return self._cancelar
    
    def login(self, username: str = None, password: str = None, force: bool = False) -> bool:
        return self._auth.login(username, password, force)
    
    def limpar_sessao(self):
        self._auth.limpar_sessao()
    
    def ensure_logged_in(self) -> bool:
        return self._auth.ensure_logged_in()
    
    def listar_perfis(self) -> List[Perfil]:
        return self._auth.listar_perfis()
    
    def select_profile(self, nome: str) -> bool:
        result = self._auth.select_profile(nome)
        if result:
            self._tasks.limpar_cache()
        return result
    
    def select_profile_by_index(self, index: int) -> bool:
        result = self._auth.select_profile_by_index(index)
        if result:
            self._tasks.limpar_cache()
            self.logger.info(f"Cache de tarefas limpo apos selecao de perfil")
        return result
    
    def listar_tarefas(self, force: bool = False) -> List[Tarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas(force)
    
    def listar_tarefas_favoritas(self, force: bool = False) -> List[Tarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas_favoritas(force)
    
    def buscar_tarefa(self, nome: str, favoritas: bool = False) -> Optional[Tarefa]:
        return self._tasks.buscar_tarefa_por_nome(nome, favoritas)
    
    def listar_processos_tarefa(self, nome: str, favoritas: bool = False) -> List[ProcessoTarefa]:
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_todos_processos_tarefa(nome, favoritas)
    
    def buscar_etiquetas(self, busca: str = "") -> List[Etiqueta]:
        if not self.ensure_logged_in():
            return []
        return self._tags.buscar_etiquetas(busca)
    
    def buscar_etiqueta(self, nome: str) -> Optional[Etiqueta]:
        if not self.ensure_logged_in():
            return None
        return self._tags.buscar_etiqueta_por_nome(nome)
    
    def listar_processos_etiqueta(self, id_etiqueta: int, limit: int = 100) -> List[Processo]:
        if not self.ensure_logged_in():
            return []
        return self._tags.listar_processos_etiqueta(id_etiqueta, limit)
    
    def solicitar_download(self, id_processo: int, numero_processo: str, 
                          tipo: str = "Selecione", diretorio: Path = None) -> bool:
        sucesso, _ = self._downloads.solicitar_download(
            id_processo, numero_processo, tipo, diretorio_download=diretorio
        )
        return sucesso
    
    def listar_downloads(self) -> List[DownloadDisponivel]:
        return self._downloads.listar_downloads_disponiveis()
    
    def baixar_arquivo(self, download: DownloadDisponivel, diretorio: Path = None) -> Optional[Path]:
        return self._downloads.baixar_arquivo(download, diretorio)
    
    def _verificar_arquivo_valido(self, filepath: Path) -> bool:
        try:
            if not filepath.exists():
                return False
            if filepath.stat().st_size == 0:
                return False
            with open(filepath, 'rb') as f:
                f.read(1)
            return True
        except Exception:
            return False
    
    def _listar_arquivos_diretorio(self, diretorio: Path) -> Set[str]:
        arquivos = set()
        if not diretorio.exists():
            return arquivos
        
        for arquivo in diretorio.iterdir():
            if arquivo.is_file() and arquivo.suffix.lower() in ['.pdf', '.zip']:
                if self._verificar_arquivo_valido(arquivo):
                    arquivos.add(arquivo.name)
        return arquivos
    
    def _extrair_numero_processo_arquivo(self, nome_arquivo: str) -> Optional[str]:
        match = re.match(r'^(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', nome_arquivo)
        if match:
            return match.group(1)
        return None
    
    def _verificar_integridade(self, processos_esperados: List[str], diretorio: Path) -> Dict[str, Any]:
        arquivos_disco = self._listar_arquivos_diretorio(diretorio)
        
        processos_baixados = set()
        for arquivo in arquivos_disco:
            num_proc = self._extrair_numero_processo_arquivo(arquivo)
            if num_proc:
                processos_baixados.add(num_proc)
        
        processos_esperados_set = set(processos_esperados)
        processos_faltantes = processos_esperados_set - processos_baixados
        
        return {
            "total_esperado": len(processos_esperados),
            "total_arquivos": len(arquivos_disco),
            "processos_confirmados": len(processos_baixados),
            "processos_faltantes": list(processos_faltantes),
            "integridade": "ok" if not processos_faltantes else "inconsistente"
        }
    
    def _baixar_pendentes_verificado(self, processos: List[str], diretorio: Path, tempo_espera: int = 60) -> List[str]:
        if not processos:
            return []
        
        arquivos_baixados = []
        self.logger.info(f"Verificando {len(processos)} downloads pendentes")
        
        time.sleep(5)
        
        inicio = time.time()
        processos_restantes = set(processos)
        
        while processos_restantes and (time.time() - inicio) < tempo_espera:
            # Verificar cancelamento
            if self._check_cancelado():
                self.logger.info("Download pendente cancelado")
                break
            
            downloads = self._downloads.listar_downloads_disponiveis()
            
            for download in downloads:
                if self._check_cancelado():
                    break
                    
                numeros = download.get_numeros_processos()
                for num in numeros:
                    if num in processos_restantes:
                        arquivo = self._downloads.baixar_arquivo(download, diretorio)
                        if arquivo and self._verificar_arquivo_valido(arquivo):
                            arquivos_baixados.append(str(arquivo))
                            processos_restantes.discard(num)
            
            if processos_restantes and not self._check_cancelado():
                self.logger.info(f"Restantes: {len(processos_restantes)}")
                time.sleep(10)
        
        return arquivos_baixados
    
    def buscar_processo_por_numero(self, numero_processo: str) -> Optional[Dict[str, Any]]:
        """
        Busca informações de um processo pelo número usando a página de consulta.
        """
        if not self.ensure_logged_in():
            return None
        
        try:
            # Método 1: Tentar via página de consulta pública
            self.logger.debug(f"Buscando processo via consulta: {numero_processo}")
            
            # Acessar página de consulta de processos
            resp = self._http.session.get(
                f"{BASE_URL}/pje/ConsultaPublica/listView.seam",
                timeout=self.timeout
            )
            
            if resp.status_code == 200:
                viewstate = extrair_viewstate(resp.text)
                
                if viewstate:
                    # Extrair partes do número do processo
                    partes = self._extrair_partes_numero_processo(numero_processo)
                    if partes:
                        # Fazer busca
                        form_data = {
                            "fPP": "fPP",
                            "fPP:numeroProcesso:numeroSequencial": partes["sequencial"],
                            "fPP:numeroProcesso:digitoVerificador": partes["digito"],
                            "fPP:numeroProcesso:anoProcesso": partes["ano"],
                            "fPP:numeroProcesso:segmentoJustica": partes["segmento"],
                            "fPP:numeroProcesso:tRF": partes["tribunal"],
                            "fPP:numeroProcesso:origemProcesso": partes["origem"],
                            "fPP:j_id148": "fPP:j_id148",
                            "javax.faces.ViewState": viewstate,
                        }
                        
                        resp_busca = self._http.session.post(
                            f"{BASE_URL}/pje/ConsultaPublica/listView.seam",
                            data=form_data,
                            timeout=self.timeout,
                            headers={
                                "Content-Type": "application/x-www-form-urlencoded",
                                "Origin": BASE_URL,
                            }
                        )
                        
                        if resp_busca.status_code == 200:
                            # Procurar ID do processo na resposta
                            id_match = re.search(r'idProcesso[=:](\d+)', resp_busca.text)
                            if id_match:
                                return {
                                    "id_processo": int(id_match.group(1)),
                                    "numero_processo": numero_processo
                                }
            
            # Método 2: Tentar busca via painel do usuário
            self.logger.debug(f"Tentando busca via painel do usuario")
            resp = self._http.api_post(
                "painelUsuario/processos",
                {"numeroProcesso": numero_processo, "page": 0, "maxResults": 1}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("entities"):
                    proc = data["entities"][0]
                    return {
                        "id_processo": proc.get("idProcesso", 0),
                        "numero_processo": numero_processo
                    }
                elif isinstance(data, list) and len(data) > 0:
                    proc = data[0]
                    return {
                        "id_processo": proc.get("idProcesso", 0),
                        "numero_processo": numero_processo
                    }
            
            # Método 3: Tentar via tarefas
            self.logger.debug(f"Tentando busca via tarefas")
            resp = self._http.api_post(
                "painelUsuario/tarefas",
                {"numeroProcesso": numero_processo, "competencia": "", "etiquetas": []}
            )
            
            if resp.status_code == 200:
                tarefas = resp.json()
                if tarefas:
                    # Buscar processos em cada tarefa encontrada
                    for tarefa in tarefas[:3]:  # Limitar a 3 tarefas
                        nome_tarefa = tarefa.get("nome", "")
                        if nome_tarefa:
                            from urllib.parse import quote
                            resp_proc = self._http.api_post(
                                f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{quote(nome_tarefa)}/false",
                                {"numeroProcesso": numero_processo, "page": 0, "maxResults": 1}
                            )
                            if resp_proc.status_code == 200:
                                data = resp_proc.json()
                                if data.get("entities"):
                                    proc = data["entities"][0]
                                    return {
                                        "id_processo": proc.get("idProcesso", 0),
                                        "numero_processo": numero_processo
                                    }
            
            self.logger.warning(f"Processo nao encontrado via API: {numero_processo}")
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar processo {numero_processo}: {e}")
            return None
    
    def _extrair_partes_numero_processo(self, numero: str) -> Optional[Dict[str, str]]:
        """Extrai as partes do número do processo no formato CNJ."""
        # Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
        match = re.match(r'^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$', numero)
        if match:
            return {
                "sequencial": match.group(1),
                "digito": match.group(2),
                "ano": match.group(3),
                "segmento": match.group(4),
                "tribunal": match.group(5),
                "origem": match.group(6)
            }
        return None
    
    def obter_id_processo_via_painel(self, numero_processo: str) -> Optional[int]:
        """
        Tenta obter o ID do processo através do painel usando busca filtrada.
        """
        try:
            # Buscar em todas as tarefas usando o número como filtro
            self.logger.debug(f"Buscando ID via filtro de tarefa: {numero_processo}")
            
            # Primeiro, obter lista de tarefas
            tarefas = self._tasks.listar_tarefas()
            
            for tarefa in tarefas[:5]:  # Verificar nas primeiras 5 tarefas
                if self._check_cancelado():
                    return None
                    
                from urllib.parse import quote
                resp = self._http.api_post(
                    f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{quote(tarefa.nome)}/false",
                    {
                        "numeroProcesso": numero_processo,
                        "classe": None,
                        "tags": [],
                        "page": 0,
                        "maxResults": 1,
                        "competencia": ""
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    entities = data.get("entities", [])
                    if entities:
                        proc = entities[0]
                        if proc.get("numeroProcesso") == numero_processo:
                            self.logger.info(f"Processo encontrado na tarefa '{tarefa.nome}'")
                            return proc.get("idProcesso", 0)
            
            # Tentar também nas favoritas
            tarefas_fav = self._tasks.listar_tarefas_favoritas()
            
            for tarefa in tarefas_fav[:5]:
                if self._check_cancelado():
                    return None
                    
                from urllib.parse import quote
                resp = self._http.api_post(
                    f"painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{quote(tarefa.nome)}/true",
                    {
                        "numeroProcesso": numero_processo,
                        "classe": None,
                        "tags": [],
                        "page": 0,
                        "maxResults": 1,
                        "competencia": ""
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    entities = data.get("entities", [])
                    if entities:
                        proc = entities[0]
                        if proc.get("numeroProcesso") == numero_processo:
                            self.logger.info(f"Processo encontrado na tarefa favorita '{tarefa.nome}'")
                            return proc.get("idProcesso", 0)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao obter ID do processo: {e}")
            return None
    
    def obter_id_processo_via_etiquetas(self, numero_processo: str) -> Optional[int]:
        """
        Tenta obter o ID do processo através das etiquetas.
        """
        try:
            self.logger.debug(f"Buscando ID via etiquetas: {numero_processo}")
            
            # Buscar etiquetas do usuário
            etiquetas = self._tags.buscar_etiquetas("")
            
            for etiqueta in etiquetas[:10]:  # Verificar nas primeiras 10 etiquetas
                if self._check_cancelado():
                    return None
                    
                processos = self._tags.listar_processos_etiqueta(etiqueta.id, limit=500)
                
                for proc in processos:
                    if proc.numero_processo == numero_processo:
                        self.logger.info(f"Processo encontrado na etiqueta '{etiqueta.nome}'")
                        return proc.id_processo
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar via etiquetas: {e}")
            return None
    
    def processar_numeros_generator(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa uma lista de números de processos para download.
        """
        self._reset_cancelamento()
        self._downloads.limpar_diagnosticos()
        
        # Criar diretório específico para downloads por número
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        diretorio = self.download_dir / f"processos_{timestamp}"
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "tipo": "download_por_numero",
            "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": len(numeros_processos),
            "sucesso": 0,
            "falha": 0,
            "arquivos": [],
            "erros": [],
            "status": "iniciando",
            "processo_atual": "",
            "progresso": 0,
            "integridade": "pendente",
            "retries": {"tentativas": 0, "processos_reprocessados": [], "processos_falha_definitiva": []}
        }
        
        yield relatorio
        
        self.logger.section(f"PROCESSANDO {len(numeros_processos)} PROCESSOS POR NÚMERO")
        
        if not numeros_processos:
            relatorio["status"] = "concluido"
            relatorio["erros"].append("Nenhum processo informado")
            yield relatorio
            return relatorio
        
        processos_info = {}  # numero_processo -> {id_processo, ...}
        processos_pendentes = []
        total = len(numeros_processos)
        
        relatorio["status"] = "processando"
        
        for i, numero in enumerate(numeros_processos, 1):
            # Verificar cancelamento no início de cada iteração
            if self._check_cancelado():
                self.logger.info("Processamento cancelado pelo usuario")
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuario")
                yield relatorio
                return relatorio
            
            relatorio["processo_atual"] = numero
            relatorio["progresso"] = i
            self.logger.info(f"[{i}/{total}] Processando {numero}")
            yield relatorio
            
            # Verificar cancelamento antes de buscar
            if self._check_cancelado():
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuario")
                yield relatorio
                return relatorio
            
            # Tentar buscar informações do processo
            relatorio["status"] = "buscando_processo"
            yield relatorio
            
            id_processo = None
            
            # Método 1: Busca via API
            proc_info = self.buscar_processo_por_numero(numero)
            if proc_info and proc_info.get("id_processo"):
                id_processo = proc_info["id_processo"]
                self.logger.info(f"ID encontrado via API: {id_processo}")
            
            # Método 2: Busca via painel de tarefas
            if not id_processo and not self._check_cancelado():
                id_processo = self.obter_id_processo_via_painel(numero)
                if id_processo:
                    self.logger.info(f"ID encontrado via painel: {id_processo}")
            
            # Método 3: Busca via etiquetas
            if not id_processo and not self._check_cancelado():
                id_processo = self.obter_id_processo_via_etiquetas(numero)
                if id_processo:
                    self.logger.info(f"ID encontrado via etiquetas: {id_processo}")
            
            # Verificar cancelamento após busca
            if self._check_cancelado():
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuario")
                yield relatorio
                return relatorio
            
            if not id_processo:
                self.logger.error(f"Nao foi possivel encontrar o processo: {numero}")
                relatorio["falha"] += 1
                relatorio["erros"].append(f"Processo nao encontrado: {numero}")
                relatorio["status"] = "processando"
                yield relatorio
                continue
            
            processos_info[numero] = {
                "id_processo": id_processo,
                "numero_processo": numero
            }
            
            relatorio["status"] = "processando"
            yield relatorio
            
            # Solicitar download
            sucesso, detalhes = self._downloads.solicitar_download(
                id_processo, numero, tipo_documento, diretorio_download=diretorio
            )
            
            if sucesso:
                if detalhes.get("arquivo_baixado"):
                    arquivo_path = Path(detalhes["arquivo_baixado"])
                    if self._verificar_arquivo_valido(arquivo_path):
                        relatorio["arquivos"].append(str(arquivo_path))
                        relatorio["sucesso"] += 1
                        self.logger.success(f"Download concluido: {numero}")
                    else:
                        processos_pendentes.append(numero)
                else:
                    processos_pendentes.append(numero)
            else:
                relatorio["falha"] += 1
                relatorio["erros"].append(f"Falha ao solicitar download: {numero}")
            
            yield relatorio
            time.sleep(2)
        
        # Verificar cancelamento antes de aguardar downloads
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            relatorio["erros"].append("Processamento cancelado pelo usuario")
            yield relatorio
            return relatorio
        
        # Aguardar downloads pendentes
        if aguardar_download and processos_pendentes:
            relatorio["status"] = "aguardando_downloads"
            relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
            yield relatorio
            
            arquivos = self._baixar_pendentes_verificado(processos_pendentes, diretorio, tempo_espera=tempo_espera)
            for arq in arquivos:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
                    relatorio["sucesso"] += 1
        
        # Verificar cancelamento antes de verificar integridade
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            relatorio["erros"].append("Processamento cancelado pelo usuario")
            yield relatorio
            return relatorio
        
        # Verificar integridade
        relatorio["status"] = "verificando_integridade"
        relatorio["processo_atual"] = "Verificando arquivos"
        yield relatorio
        
        processos_esperados = list(numeros_processos)
        integridade = self._verificar_integridade(processos_esperados, diretorio)
        relatorio["integridade"] = integridade["integridade"]
        processos_faltantes = integridade["processos_faltantes"]
        
        # Retries
        tentativa = 0
        while processos_faltantes and tentativa < self.max_retries and not self._check_cancelado():
            tentativa += 1
            relatorio["retries"]["tentativas"] = tentativa
            relatorio["status"] = f"retry_{tentativa}"
            relatorio["processo_atual"] = f"Retry {tentativa}/{self.max_retries} - {len(processos_faltantes)} processos"
            self.logger.info(f"Retry {tentativa}: {len(processos_faltantes)} processos faltantes")
            yield relatorio
            
            time.sleep(self.retry_delay)
            
            for num_proc in processos_faltantes[:]:
                if self._check_cancelado():
                    break
                
                if num_proc not in processos_info:
                    continue
                
                proc = processos_info[num_proc]
                if proc.get("id_processo", 0) <= 0:
                    continue
                
                relatorio["processo_atual"] = f"Retry: {num_proc}"
                yield relatorio
                
                sucesso, _ = self._downloads.solicitar_download(
                    proc["id_processo"], num_proc, tipo_documento, diretorio_download=diretorio
                )
                if sucesso:
                    relatorio["retries"]["processos_reprocessados"].append(num_proc)
                time.sleep(3)
            
            if self._check_cancelado():
                break
            
            time.sleep(15)
            arquivos_retry = self._baixar_pendentes_verificado(processos_faltantes, diretorio, tempo_espera=60)
            for arq in arquivos_retry:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            processos_faltantes = integridade["processos_faltantes"]
            relatorio["integridade"] = integridade["integridade"]
        
        if processos_faltantes:
            relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
        
        # Finalizar
        arquivos_validos = [a for a in relatorio["arquivos"] if self._verificar_arquivo_valido(Path(a))]
        relatorio["arquivos"] = arquivos_validos
        relatorio["sucesso"] = len(arquivos_validos)
        relatorio["falha"] = relatorio["processos"] - relatorio["sucesso"]
        relatorio["data_fim"] = datetime.now().isoformat()
        
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
        elif relatorio["integridade"] == "ok":
            relatorio["status"] = "concluido"
        elif processos_faltantes:
            relatorio["status"] = "concluido_com_falhas"
        else:
            relatorio["status"] = "concluido"
        
        relatorio["processo_atual"] = ""
        save_json(relatorio, diretorio / f"relatorio_{timestamp_str()}.json")
        
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        self.logger.info(f"Integridade: {relatorio['integridade']}")
        
        yield relatorio
        return relatorio
    
    def processar_tarefa_generator(
        self,
        nome_tarefa: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300,
        usar_favoritas: bool = False,
        tamanho_lote: int = 10
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        self._reset_cancelamento()
        self._downloads.limpar_diagnosticos()
        
        nome_pasta = normalizar_nome_pasta(nome_tarefa)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "tarefa": nome_tarefa, 
            "perfil": perfil, 
            "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": 0, 
            "sucesso": 0, 
            "falha": 0, 
            "arquivos": [], 
            "erros": [],
            "status": "iniciando",
            "processo_atual": "",
            "progresso": 0,
            "integridade": "pendente",
            "retries": {"tentativas": 0, "processos_reprocessados": [], "processos_falha_definitiva": []}
        }
        
        yield relatorio
        
        self.logger.section(f"PROCESSANDO TAREFA: {nome_tarefa}")
        
        if perfil and not self.select_profile(perfil):
            relatorio["erros"].append("Falha ao selecionar perfil")
            relatorio["status"] = "erro"
            yield relatorio
            return relatorio
        
        # Verificar cancelamento
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "buscando_tarefa"
        yield relatorio
        
        tarefa = self.buscar_tarefa(nome_tarefa, usar_favoritas)
        if not tarefa:
            relatorio["erros"].append("Tarefa nao encontrada")
            relatorio["status"] = "erro"
            yield relatorio
            return relatorio
        
        # Verificar cancelamento
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "listando_processos"
        yield relatorio
        
        processos = self.listar_processos_tarefa(tarefa.nome, usar_favoritas)
        if limite:
            processos = processos[:limite]
        relatorio["processos"] = len(processos)
        
        if not processos:
            relatorio["status"] = "concluido"
            relatorio["erros"].append("Nenhum processo encontrado")
            yield relatorio
            return relatorio
        
        mapa_processos = {p.numero_processo: p for p in processos}
        processos_esperados = list(mapa_processos.keys())
        processos_pendentes = []
        total = len(processos)
        
        relatorio["status"] = "processando"
        
        for i, proc in enumerate(processos, 1):
            # Verificar cancelamento no início de cada iteração
            if self._check_cancelado():
                self.logger.info("Processamento cancelado pelo usuario")
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuario")
                yield relatorio
                return relatorio
            
            relatorio["processo_atual"] = proc.numero_processo
            relatorio["progresso"] = i
            self.logger.info(f"[{i}/{total}] {proc.numero_processo}")
            yield relatorio
            
            sucesso, detalhes = self._downloads.solicitar_download(
                proc.id_processo, proc.numero_processo, tipo_documento, diretorio_download=diretorio
            )
            
            if sucesso:
                if detalhes.get("arquivo_baixado"):
                    arquivo_path = Path(detalhes["arquivo_baixado"])
                    if self._verificar_arquivo_valido(arquivo_path):
                        relatorio["arquivos"].append(str(arquivo_path))
                        relatorio["sucesso"] += 1
                    else:
                        processos_pendentes.append(proc.numero_processo)
                else:
                    processos_pendentes.append(proc.numero_processo)
            else:
                relatorio["falha"] += 1
            
            yield relatorio
            time.sleep(2)
            
            if len(processos_pendentes) >= tamanho_lote:
                # Verificar cancelamento antes do lote
                if self._check_cancelado():
                    relatorio["status"] = "cancelado"
                    yield relatorio
                    return relatorio
                
                relatorio["status"] = "baixando_lote"
                yield relatorio
                
                arquivos = self._baixar_pendentes_verificado(processos_pendentes, diretorio, tempo_espera=60)
                for arq in arquivos:
                    if arq not in relatorio["arquivos"]:
                        relatorio["arquivos"].append(arq)
                        relatorio["sucesso"] += 1
                processos_pendentes.clear()
                relatorio["status"] = "processando"
                yield relatorio
        
        # Verificar cancelamento antes de aguardar downloads
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        if aguardar_download and processos_pendentes:
            relatorio["status"] = "aguardando_downloads"
            relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
            yield relatorio
            
            arquivos = self._baixar_pendentes_verificado(processos_pendentes, diretorio, tempo_espera=tempo_espera)
            for arq in arquivos:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
                    relatorio["sucesso"] += 1
        
        # Verificar cancelamento antes de verificar integridade
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "verificando_integridade"
        relatorio["processo_atual"] = "Verificando arquivos"
        yield relatorio
        
        integridade = self._verificar_integridade(processos_esperados, diretorio)
        relatorio["integridade"] = integridade["integridade"]
        processos_faltantes = integridade["processos_faltantes"]
        tentativa = 0
        
        while processos_faltantes and tentativa < self.max_retries and not self._check_cancelado():
            tentativa += 1
            relatorio["retries"]["tentativas"] = tentativa
            relatorio["status"] = f"retry_{tentativa}"
            relatorio["processo_atual"] = f"Retry {tentativa}/{self.max_retries} - {len(processos_faltantes)} processos"
            self.logger.info(f"Retry {tentativa}: {len(processos_faltantes)} processos faltantes")
            yield relatorio
            
            time.sleep(self.retry_delay)
            
            for num_proc in processos_faltantes[:]:
                if self._check_cancelado():
                    break
                if num_proc not in mapa_processos:
                    continue
                proc = mapa_processos[num_proc]
                relatorio["processo_atual"] = f"Retry: {num_proc}"
                yield relatorio
                
                sucesso, _ = self._downloads.solicitar_download(
                    proc.id_processo, proc.numero_processo, tipo_documento, diretorio_download=diretorio
                )
                if sucesso:
                    relatorio["retries"]["processos_reprocessados"].append(num_proc)
                time.sleep(3)
            
            if self._check_cancelado():
                break
            
            time.sleep(15)
            arquivos_retry = self._baixar_pendentes_verificado(processos_faltantes, diretorio, tempo_espera=60)
            for arq in arquivos_retry:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            processos_faltantes = integridade["processos_faltantes"]
            relatorio["integridade"] = integridade["integridade"]
        
        if processos_faltantes:
            relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
        
        arquivos_validos = [a for a in relatorio["arquivos"] if self._verificar_arquivo_valido(Path(a))]
        relatorio["arquivos"] = arquivos_validos
        relatorio["sucesso"] = len(arquivos_validos)
        relatorio["falha"] = relatorio["processos"] - relatorio["sucesso"]
        relatorio["data_fim"] = datetime.now().isoformat()
        
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
        elif relatorio["integridade"] == "ok":
            relatorio["status"] = "concluido"
        elif processos_faltantes:
            relatorio["status"] = "concluido_com_falhas"
        else:
            relatorio["status"] = "concluido"
        
        relatorio["processo_atual"] = ""
        save_json(relatorio, diretorio / f"relatorio_{timestamp_str()}.json")
        
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        self.logger.info(f"Integridade: {relatorio['integridade']}")
        
        yield relatorio
        return relatorio
    
    def processar_etiqueta_generator(
        self,
        nome_etiqueta: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300,
        tamanho_lote: int = 10
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        self._reset_cancelamento()
        self._downloads.limpar_diagnosticos()
        
        nome_pasta = normalizar_nome_pasta(nome_etiqueta)
        diretorio = self.download_dir / nome_pasta
        diretorio.mkdir(parents=True, exist_ok=True)
        
        relatorio = {
            "etiqueta": nome_etiqueta, 
            "perfil": perfil, 
            "diretorio": str(diretorio),
            "data_inicio": datetime.now().isoformat(),
            "processos": 0, 
            "sucesso": 0, 
            "falha": 0, 
            "arquivos": [], 
            "erros": [],
            "status": "iniciando",
            "processo_atual": "",
            "progresso": 0,
            "integridade": "pendente",
            "retries": {"tentativas": 0, "processos_reprocessados": [], "processos_falha_definitiva": []}
        }
        
        yield relatorio
        
        self.logger.section(f"PROCESSANDO ETIQUETA: {nome_etiqueta}")
        
        if perfil and not self.select_profile(perfil):
            relatorio["erros"].append("Falha ao selecionar perfil")
            relatorio["status"] = "erro"
            yield relatorio
            return relatorio
        
        # Verificar cancelamento
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "buscando_etiqueta"
        yield relatorio
        
        etiqueta = self.buscar_etiqueta(nome_etiqueta)
        if not etiqueta:
            relatorio["erros"].append("Etiqueta nao encontrada")
            relatorio["status"] = "erro"
            yield relatorio
            return relatorio
        
        # Verificar cancelamento
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "listando_processos"
        yield relatorio
        
        processos = self.listar_processos_etiqueta(etiqueta.id)
        if limite:
            processos = processos[:limite]
        relatorio["processos"] = len(processos)
        
        if not processos:
            relatorio["status"] = "concluido"
            relatorio["erros"].append("Nenhum processo encontrado")
            yield relatorio
            return relatorio
        
        mapa_processos = {p.numero_processo: p for p in processos}
        processos_esperados = list(mapa_processos.keys())
        processos_pendentes = []
        total = len(processos)
        
        relatorio["status"] = "processando"
        
        for i, proc in enumerate(processos, 1):
            # Verificar cancelamento no início de cada iteração
            if self._check_cancelado():
                self.logger.info("Processamento cancelado pelo usuario")
                relatorio["status"] = "cancelado"
                relatorio["erros"].append("Processamento cancelado pelo usuario")
                yield relatorio
                return relatorio
            
            relatorio["processo_atual"] = proc.numero_processo
            relatorio["progresso"] = i
            self.logger.info(f"[{i}/{total}] {proc.numero_processo}")
            yield relatorio
            
            sucesso, detalhes = self._downloads.solicitar_download(
                proc.id_processo, proc.numero_processo, tipo_documento, diretorio_download=diretorio
            )
            
            if sucesso:
                if detalhes.get("arquivo_baixado"):
                    arquivo_path = Path(detalhes["arquivo_baixado"])
                    if self._verificar_arquivo_valido(arquivo_path):
                        relatorio["arquivos"].append(str(arquivo_path))
                        relatorio["sucesso"] += 1
                    else:
                        processos_pendentes.append(proc.numero_processo)
                else:
                    processos_pendentes.append(proc.numero_processo)
            else:
                relatorio["falha"] += 1
            
            yield relatorio
            time.sleep(2)
            
            if len(processos_pendentes) >= tamanho_lote:
                # Verificar cancelamento antes do lote
                if self._check_cancelado():
                    relatorio["status"] = "cancelado"
                    yield relatorio
                    return relatorio
                
                relatorio["status"] = "baixando_lote"
                yield relatorio
                arquivos = self._baixar_pendentes_verificado(processos_pendentes, diretorio, tempo_espera=60)
                for arq in arquivos:
                    if arq not in relatorio["arquivos"]:
                        relatorio["arquivos"].append(arq)
                        relatorio["sucesso"] += 1
                processos_pendentes.clear()
                relatorio["status"] = "processando"
                yield relatorio
        
        # Verificar cancelamento antes de aguardar downloads
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        if aguardar_download and processos_pendentes:
            relatorio["status"] = "aguardando_downloads"
            relatorio["processo_atual"] = f"Aguardando {len(processos_pendentes)} downloads"
            yield relatorio
            arquivos = self._baixar_pendentes_verificado(processos_pendentes, diretorio, tempo_espera=tempo_espera)
            for arq in arquivos:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
                    relatorio["sucesso"] += 1
        
        # Verificar cancelamento antes de verificar integridade
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
            yield relatorio
            return relatorio
        
        relatorio["status"] = "verificando_integridade"
        relatorio["processo_atual"] = "Verificando arquivos"
        yield relatorio
        
        integridade = self._verificar_integridade(processos_esperados, diretorio)
        relatorio["integridade"] = integridade["integridade"]
        processos_faltantes = integridade["processos_faltantes"]
        tentativa = 0
        
        while processos_faltantes and tentativa < self.max_retries and not self._check_cancelado():
            tentativa += 1
            relatorio["retries"]["tentativas"] = tentativa
            relatorio["status"] = f"retry_{tentativa}"
            relatorio["processo_atual"] = f"Retry {tentativa}/{self.max_retries}"
            self.logger.info(f"Retry {tentativa}: {len(processos_faltantes)} faltantes")
            yield relatorio
            
            time.sleep(self.retry_delay)
            
            for num_proc in processos_faltantes[:]:
                if self._check_cancelado():
                    break
                if num_proc not in mapa_processos:
                    continue
                proc = mapa_processos[num_proc]
                relatorio["processo_atual"] = f"Retry: {num_proc}"
                yield relatorio
                
                sucesso, _ = self._downloads.solicitar_download(
                    proc.id_processo, proc.numero_processo, tipo_documento, diretorio_download=diretorio
                )
                if sucesso:
                    relatorio["retries"]["processos_reprocessados"].append(num_proc)
                time.sleep(3)
            
            if self._check_cancelado():
                break
            
            time.sleep(15)
            arquivos_retry = self._baixar_pendentes_verificado(processos_faltantes, diretorio, tempo_espera=60)
            for arq in arquivos_retry:
                if arq not in relatorio["arquivos"]:
                    relatorio["arquivos"].append(arq)
            
            integridade = self._verificar_integridade(processos_esperados, diretorio)
            processos_faltantes = integridade["processos_faltantes"]
            relatorio["integridade"] = integridade["integridade"]
        
        if processos_faltantes:
            relatorio["retries"]["processos_falha_definitiva"] = processos_faltantes
        
        arquivos_validos = [a for a in relatorio["arquivos"] if self._verificar_arquivo_valido(Path(a))]
        relatorio["arquivos"] = arquivos_validos
        relatorio["sucesso"] = len(arquivos_validos)
        relatorio["falha"] = relatorio["processos"] - relatorio["sucesso"]
        relatorio["data_fim"] = datetime.now().isoformat()
        
        if self._check_cancelado():
            relatorio["status"] = "cancelado"
        elif relatorio["integridade"] == "ok":
            relatorio["status"] = "concluido"
        elif processos_faltantes:
            relatorio["status"] = "concluido_com_falhas"
        else:
            relatorio["status"] = "concluido"
        
        relatorio["processo_atual"] = ""
        save_json(relatorio, diretorio / f"relatorio_{timestamp_str()}.json")
        
        self.logger.section("RESUMO")
        self.logger.info(f"Processos: {relatorio['processos']}")
        self.logger.info(f"Sucesso: {relatorio['sucesso']}")
        self.logger.info(f"Arquivos: {len(relatorio['arquivos'])}")
        self.logger.info(f"Integridade: {relatorio['integridade']}")
        
        yield relatorio
        return relatorio
    
    def processar_tarefa(
        self,
        nome_tarefa: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300,
        usar_favoritas: bool = False
    ) -> Dict[str, Any]:
        relatorio = None
        for estado in self.processar_tarefa_generator(
            nome_tarefa, perfil, tipo_documento, limite,
            aguardar_download, tempo_espera, usar_favoritas
        ):
            relatorio = estado
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
        return relatorio
    
    def processar_etiqueta(
        self,
        nome_etiqueta: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        relatorio = None
        for estado in self.processar_etiqueta_generator(
            nome_etiqueta, perfil, tipo_documento, limite,
            aguardar_download, tempo_espera
        ):
            relatorio = estado
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
        return relatorio
    
    def processar_numeros(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """Processa lista de números de processos (versão síncrona)."""
        relatorio = None
        for estado in self.processar_numeros_generator(
            numeros_processos, tipo_documento,
            aguardar_download, tempo_espera
        ):
            relatorio = estado
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
        return relatorio
    
    def close(self):
        self._http.close()
        self.logger.info("Conexao encerrada")
