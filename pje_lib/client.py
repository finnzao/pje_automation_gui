from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Generator

from .config import DEFAULT_TIMEOUT
from .core import SessionManager, PJEHttpClient
from .services import AuthService, TaskService, TagService, DownloadService
from .processors import NumberProcessor, TaskProcessor, TagProcessor
from .models import Usuario, Perfil, Tarefa, ProcessoTarefa, Etiqueta, Processo, DownloadDisponivel
from .utils import get_logger


class PJEClient:
    """
    Cliente principal para automação do PJE.
    """
    
    def __init__(
        self,
        download_dir: str = "./downloads",
        log_dir: str = "./.logs",
        session_dir: str = "./.session",
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = True
    ):
        """
        Inicializa o cliente PJE.
        
        Args:
            download_dir: Diretório para downloads
            log_dir: Diretório para logs
            session_dir: Diretório para sessão
            timeout: Timeout padrão para requisições
            debug: Se deve habilitar logs de debug
        """
        self.timeout = timeout
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger("pje", self.log_dir, debug)
        
        # Componentes core
        self._http = PJEHttpClient(timeout)
        self._session = SessionManager(session_dir)
        
        # Serviços
        self._auth = AuthService(self._http, self._session)
        self._tasks = TaskService(self._http)
        self._tags = TagService(self._http)
        self._downloads = DownloadService(self._http, self.download_dir)
        
        # Processadores (lazy initialization)
        self._number_processor: Optional[NumberProcessor] = None
        self._task_processor: Optional[TaskProcessor] = None
        self._tag_processor: Optional[TagProcessor] = None
        
        # Callbacks
        self._progress_callback: Optional[Callable[[int, int, str, str], None]] = None
        
        self.logger.info(f"PJEClient inicializado. Downloads: {self.download_dir}")
    
    # PROPRIEDADES
    
    @property
    def usuario(self) -> Optional[Usuario]:
        """Usuário atualmente logado."""
        return self._auth.usuario
    
    @property
    def perfis(self) -> List[Perfil]:
        """Lista de perfis disponíveis."""
        return self._auth.perfis_disponiveis
    
    @property
    def tarefas(self) -> List[Tarefa]:
        """Cache de tarefas."""
        return self._tasks.tarefas_cache
    
    @property
    def tarefas_favoritas(self) -> List[Tarefa]:
        """Cache de tarefas favoritas."""
        return self._tasks.tarefas_favoritas_cache
    
    # PROCESSADORES (LAZY)
    
    def _get_number_processor(self) -> NumberProcessor:
        """Obtém processador de números (lazy initialization)."""
        if self._number_processor is None:
            # Importar aqui para evitar import circular
            from .services.process_search_service import ProcessSearchService
            
            search_service = ProcessSearchService(self._http)
            self._number_processor = NumberProcessor(
                self._downloads,
                search_service,
                self.download_dir
            )
        return self._number_processor
    
    def _get_task_processor(self) -> TaskProcessor:
        """Obtém processador de tarefas (lazy initialization)."""
        if self._task_processor is None:
            self._task_processor = TaskProcessor(
                self._downloads,
                self._tasks,
                self.download_dir
            )
        return self._task_processor
    
    def _get_tag_processor(self) -> TagProcessor:
        """Obtém processador de etiquetas (lazy initialization)."""
        if self._tag_processor is None:
            self._tag_processor = TagProcessor(
                self._downloads,
                self._tags,
                self.download_dir
            )
        return self._tag_processor
    
    # AUTENTICAÇÃO
    
    def login(
        self,
        username: str = None,
        password: str = None,
        force: bool = False,
        validar_saude: bool = True
    ) -> bool:
        """
        Realiza login no PJE.
        
        Args:
            username: CPF do usuário
            password: Senha
            force: Forçar novo login
            validar_saude: Validar saúde da sessão após login
        
        Returns:
            True se login bem-sucedido
        """
        if validar_saude:
            # Usar login com validação automática
            return self._auth.login_com_validacao(username, password, force)
        else:
            # Login tradicional
            return self._auth.login(username, password, force)
    
    def limpar_sessao(self):
        """Limpa sessão salva."""
        self._auth.limpar_sessao()
    
    def forcar_reset_sessao(self) -> bool:
        """
        Força reset completo da sessão.
        Remove .config e .session.
        """
        return self._auth.forcar_reset_sessao()
    
    def ensure_logged_in(self) -> bool:
        """
        Garante que está logado com sessão válida.
        Valida saúde automaticamente.
        """
        return self._auth.ensure_logged_in()
    
    def validar_saude_sessao(self) -> bool:
        """Valida se sessão está funcional."""
        return self._auth.validar_saude_sessao()
    
    # PERFIS
    
    def listar_perfis(self) -> List[Perfil]:
        """Lista perfis disponíveis."""
        return self._auth.listar_perfis()
    
    def select_profile(self, nome: str) -> bool:
        """Seleciona perfil por nome."""
        result = self._auth.select_profile(nome)
        if result:
            self._tasks.limpar_cache()
        return result
    
    def select_profile_by_index(self, index: int) -> bool:
        """Seleciona perfil por índice."""
        result = self._auth.select_profile_by_index(index)
        if result:
            self._tasks.limpar_cache()
            self.logger.info(f"Cache de tarefas limpo após seleção de perfil")
        return result
    
    # TAREFAS
    
    def listar_tarefas(self, force: bool = False) -> List[Tarefa]:
        """Lista tarefas gerais."""
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas(force)
    
    def listar_tarefas_favoritas(self, force: bool = False) -> List[Tarefa]:
        """Lista tarefas favoritas."""
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_tarefas_favoritas(force)
    
    def buscar_tarefa(self, nome: str, favoritas: bool = False) -> Optional[Tarefa]:
        """Busca tarefa por nome."""
        return self._tasks.buscar_tarefa_por_nome(nome, favoritas)
    
    def listar_processos_tarefa(
        self,
        nome: str,
        favoritas: bool = False
    ) -> List[ProcessoTarefa]:
        """Lista todos os processos de uma tarefa."""
        if not self.ensure_logged_in():
            return []
        return self._tasks.listar_todos_processos_tarefa(nome, favoritas)
    
    # ETIQUETAS
    
    def buscar_etiquetas(self, busca: str = "") -> List[Etiqueta]:
        """Busca etiquetas."""
        if not self.ensure_logged_in():
            return []
        return self._tags.buscar_etiquetas(busca)
    
    def buscar_etiqueta(self, nome: str) -> Optional[Etiqueta]:
        """Busca etiqueta por nome."""
        if not self.ensure_logged_in():
            return None
        return self._tags.buscar_etiqueta_por_nome(nome)
    
    def listar_processos_etiqueta(
        self,
        id_etiqueta: int,
        limit: int = 100
    ) -> List[Processo]:
        """Lista processos de uma etiqueta."""
        if not self.ensure_logged_in():
            return []
        return self._tags.listar_processos_etiqueta(id_etiqueta, limit)
    
    # DOWNLOADS
    
    def solicitar_download(
        self,
        id_processo: int,
        numero_processo: str,
        tipo: str = "Selecione",
        diretorio: Path = None
    ) -> bool:
        """Solicita download de processo."""
        sucesso, _ = self._downloads.solicitar_download(
            id_processo, numero_processo, tipo, diretorio_download=diretorio
        )
        return sucesso
    
    def listar_downloads(self) -> List[DownloadDisponivel]:
        """Lista downloads disponíveis."""
        return self._downloads.listar_downloads_disponiveis()
    
    def baixar_arquivo(
        self,
        download: DownloadDisponivel,
        diretorio: Path = None
    ) -> Optional[Path]:
        """Baixa arquivo da área de downloads."""
        return self._downloads.baixar_arquivo(download, diretorio)
    
    # PROCESSAMENTO - NÚMEROS
    
    def processar_numeros_generator(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Processa lista de números de processos (generator).
        
        Args:
            numeros_processos: Lista de números CNJ
            tipo_documento: Tipo de documento
            aguardar_download: Se deve aguardar downloads
            tempo_espera: Tempo máximo de espera
        
        Yields:
            Estado atual do processamento
        
        Returns:
            Relatório final
        """
        processor = self._get_number_processor()
        
        for estado in processor.processar_generator(
            numeros_processos=numeros_processos,
            tipo_documento=tipo_documento,
            aguardar_download=aguardar_download,
            tempo_espera=tempo_espera
        ):
            # Notificar callbacks
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
            yield estado
    
    def processar_numeros(
        self,
        numeros_processos: List[str],
        tipo_documento: str = "Selecione",
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """Processa lista de números (versão síncrona)."""
        processor = self._get_number_processor()
        return processor.processar(
            numeros_processos=numeros_processos,
            tipo_documento=tipo_documento,
            aguardar_download=aguardar_download,
            tempo_espera=tempo_espera
        )
    
    # PROCESSAMENTO - TAREFAS
    
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
        """
        Processa tarefa (generator).
        
        Args:
            nome_tarefa: Nome da tarefa
            perfil: Nome do perfil (opcional)
            tipo_documento: Tipo de documento
            limite: Limite de processos
            aguardar_download: Se deve aguardar downloads
            tempo_espera: Tempo máximo de espera
            usar_favoritas: Se deve buscar em favoritas
            tamanho_lote: Tamanho do lote para downloads
        
        Yields:
            Estado atual
        
        Returns:
            Relatório final
        """
        if perfil and not self.select_profile(perfil):
            yield {
                "status": "erro",
                "erros": ["Falha ao selecionar perfil"],
                "processos": 0,
                "sucesso": 0,
                "falha": 0
            }
            return
        
        processor = self._get_task_processor()
        processor.tamanho_lote = tamanho_lote
        
        for estado in processor.processar_generator(
            nome_tarefa=nome_tarefa,
            usar_favoritas=usar_favoritas,
            limite=limite,
            tipo_documento=tipo_documento,
            aguardar_download=aguardar_download,
            tempo_espera=tempo_espera
        ):
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
            yield estado
    
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
        """Processa tarefa (versão síncrona)."""
        relatorio = None
        for estado in self.processar_tarefa_generator(
            nome_tarefa, perfil, tipo_documento, limite,
            aguardar_download, tempo_espera, usar_favoritas
        ):
            relatorio = estado
        return relatorio
    
    # PROCESSAMENTO - ETIQUETAS
    
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
        """
        Processa etiqueta (generator).
        
        Args:
            nome_etiqueta: Nome da etiqueta
            perfil: Nome do perfil (opcional)
            tipo_documento: Tipo de documento
            limite: Limite de processos
            aguardar_download: Se deve aguardar downloads
            tempo_espera: Tempo máximo de espera
            tamanho_lote: Tamanho do lote
        
        Yields:
            Estado atual
        
        Returns:
            Relatório final
        """
        if perfil and not self.select_profile(perfil):
            yield {
                "status": "erro",
                "erros": ["Falha ao selecionar perfil"],
                "processos": 0,
                "sucesso": 0,
                "falha": 0
            }
            return
        
        processor = self._get_tag_processor()
        processor.tamanho_lote = tamanho_lote
        
        for estado in processor.processar_generator(
            nome_etiqueta=nome_etiqueta,
            limite=limite,
            tipo_documento=tipo_documento,
            aguardar_download=aguardar_download,
            tempo_espera=tempo_espera
        ):
            self._notify_progress(
                estado.get("progresso", 0),
                estado.get("processos", 0),
                estado.get("processo_atual", ""),
                estado.get("status", "")
            )
            yield estado
    
    def processar_etiqueta(
        self,
        nome_etiqueta: str,
        perfil: str = None,
        tipo_documento: str = "Selecione",
        limite: int = None,
        aguardar_download: bool = True,
        tempo_espera: int = 300
    ) -> Dict[str, Any]:
        """Processa etiqueta (versão síncrona)."""
        relatorio = None
        for estado in self.processar_etiqueta_generator(
            nome_etiqueta, perfil, tipo_documento, limite,
            aguardar_download, tempo_espera
        ):
            relatorio = estado
        return relatorio
    
    # CANCELAMENTO
    
    def cancelar_processamento(self):
        """
        Cancela processamento atual.
        Thread-safe e efetivo.
        """
        self.logger.warning("🛑 Solicitando cancelamento...")
        
        # Cancelar em todos os processadores
        if self._number_processor:
            self._number_processor.cancelar()
        if self._task_processor:
            self._task_processor.cancelar()
        if self._tag_processor:
            self._tag_processor.cancelar()
        
        # Tentar interromper sessão HTTP
        try:
            self._http.session.close()
            
            # Recriar sessão
            import requests
            from .config import DEFAULT_HEADERS
            self._http.session = requests.Session()
            self._http.session.headers.update(DEFAULT_HEADERS)
            
            self.logger.info("✓ Sessão HTTP reiniciada")
        except Exception as e:
            self.logger.debug(f"Erro ao reiniciar sessão: {e}")
    
    # CALLBACKS
    
    def set_progress_callback(
        self,
        callback: Callable[[int, int, str, str], None]
    ):
        """Define callback para progresso."""
        self._progress_callback = callback
    
    def _notify_progress(
        self,
        atual: int,
        total: int,
        numero_processo: str,
        status: str
    ):
        """Notifica callback de progresso."""
        if self._progress_callback:
            try:
                self._progress_callback(atual, total, numero_processo, status)
            except Exception:
                pass
    
    # FECHAMENTO
    
    def close(self):
        """Fecha conexões."""
        self._http.close()
        self.logger.info("Conexão encerrada")
