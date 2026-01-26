import shutil
from pathlib import Path
from typing import Optional, List, Any

from ..config import APP_CONFIG
from ..state.session_state import SessionStateManager


class PJESessionService:
    """
    Serviço responsável pelo gerenciamento da sessão PJE.
    
    Encapsula toda interação com o PJEClient,
    fornecendo uma interface simplificada para a UI.
    """
    
    def __init__(self, state_manager: SessionStateManager):
        """
        Inicializa o serviço.
        
        Args:
            state_manager: Gerenciador de estado da sessão
        """
        self._state = state_manager
        self._client = None
    
    def _get_or_create_client(self):
        """Obtém ou cria cliente PJE."""
        if self._state.pje_client is None:
            from pje_lib import PJEClient
            
            self._client = PJEClient(
                download_dir=self._state.get("download_dir", APP_CONFIG.DOWNLOAD_DIR),
                debug=True
            )
            self._state.pje_client = self._client
        else:
            self._client = self._state.pje_client
        
        return self._client
    
    @property
    def client(self):
        """Retorna cliente PJE."""
        return self._get_or_create_client()
    
    @property
    def is_logged_in(self) -> bool:
        """Verifica se está logado."""
        return self._state.is_logged_in and self.client.usuario is not None
    
    def login(self, username: str, password: str) -> bool:
        """
        Realiza login no PJE.
        
        Args:
            username: CPF do usuário
            password: Senha
        
        Returns:
            True se login bem-sucedido
        """
        try:
            client = self.client
            
            if client.login(username, password, validar_saude=True):
                self._state.is_logged_in = True
                self._state.user_name = client.usuario.nome if client.usuario else username
                return True
            
            return False
        
        except Exception as e:
            raise Exception(f"Erro ao conectar: {str(e)}")
    
    def logout(self) -> None:
        """Realiza logout e limpa sessão."""
        self.clear_session_complete()
    
    def validate_session(self) -> bool:
        """
        Valida se a sessão está saudável.
        
        Returns:
            True se sessão válida
        """
        if not self._state.pje_client:
            return False
        
        client = self.client
        
        if not client.usuario:
            return False
        
        if hasattr(client._auth, 'validar_saude_sessao_rapida'):
            return client._auth.validar_saude_sessao_rapida()
        
        return True
    
    def validate_session_full(self) -> bool:
        """
        Valida sessão de forma completa (mais lenta).
        
        Returns:
            True se sessão válida
        """
        if not self._state.pje_client:
            return False
        
        client = self.client
        
        if hasattr(client._auth, 'validar_saude_sessao'):
            return client._auth.validar_saude_sessao()
        
        return self.validate_session()
    
    def ensure_valid_session(self) -> bool:
        """
        Garante que a sessão está válida.
        Redireciona para login se inválida.
        
        Returns:
            True se sessão válida
        """
        if not self.validate_session():
            return False
        return True
    
    def clear_session_complete(self) -> None:
        """Limpa completamente a sessão."""
        # Fechar cliente
        if self._state.pje_client:
            try:
                self._state.pje_client.close()
            except:
                pass
        
        # Limpar diretórios
        dirs_to_clear = [APP_CONFIG.CONFIG_DIR, APP_CONFIG.SESSION_DIR]
        
        for dir_path in dirs_to_clear:
            path = Path(dir_path)
            if path.exists():
                try:
                    shutil.rmtree(path)
                except:
                    pass
        
        # Recriar diretórios
        for dir_path in dirs_to_clear:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # Resetar estado
        self._state.reset_to_defaults()
        self._client = None
    
    def list_profiles(self) -> List[Any]:
        """
        Lista perfis disponíveis.
        
        Returns:
            Lista de perfis
        """
        profiles = self._state.get("perfis", [])
        
        if not profiles:
            profiles = self.client.listar_perfis()
            self._state.set("perfis", profiles)
        
        return profiles
    
    def refresh_profiles(self) -> List[Any]:
        """
        Atualiza lista de perfis.
        
        Returns:
            Lista de perfis atualizada
        """
        self._state.set("perfis", [])
        return self.list_profiles()
    
    def select_profile_by_index(self, index: int) -> bool:
        """
        Seleciona perfil por índice.
        
        Args:
            index: Índice do perfil
        
        Returns:
            True se selecionado com sucesso
        """
        if self.client.select_profile_by_index(index):
            # Limpar cache de tarefas
            self._state.set("tarefas", [])
            self._state.set("tarefas_favoritas", [])
            return True
        
        return False
    
    def select_profile(self, name: str) -> bool:
        """
        Seleciona perfil por nome.
        
        Args:
            name: Nome do perfil
        
        Returns:
            True se selecionado com sucesso
        """
        if self.client.select_profile(name):
            self._state.set("tarefas", [])
            self._state.set("tarefas_favoritas", [])
            return True
        
        return False
    
    def list_tasks(self, force_refresh: bool = False) -> List[Any]:
        """
        Lista tarefas.
        
        Args:
            force_refresh: Forçar atualização
        
        Returns:
            Lista de tarefas
        """
        if not force_refresh:
            tasks = self._state.get("tarefas", [])
            if tasks:
                return tasks
        
        tasks = self.client.listar_tarefas(force=force_refresh)
        self._state.set("tarefas", tasks)
        return tasks
    
    def list_favorite_tasks(self, force_refresh: bool = False) -> List[Any]:
        """
        Lista tarefas favoritas.
        
        Args:
            force_refresh: Forçar atualização
        
        Returns:
            Lista de tarefas favoritas
        """
        if not force_refresh:
            tasks = self._state.get("tarefas_favoritas", [])
            if tasks:
                return tasks
        
        tasks = self.client.listar_tarefas_favoritas(force=force_refresh)
        self._state.set("tarefas_favoritas", tasks)
        return tasks
    
    def search_tags(self, query: str) -> List[Any]:
        """
        Busca etiquetas.
        
        Args:
            query: Termo de busca
        
        Returns:
            Lista de etiquetas
        """
        return self.client.buscar_etiquetas(query)
    
    def cancel_processing(self) -> None:
        """Cancela processamento atual."""
        self._state.is_cancellation_requested = True
        self.client.cancelar_processamento()