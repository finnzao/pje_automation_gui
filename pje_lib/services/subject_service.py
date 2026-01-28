from typing import List, Dict, Optional, Set
from collections import defaultdict

from ..core import PJEHttpClient
from ..models import Tarefa, ProcessoTarefa, AssuntoPrincipal
from ..utils import delay, get_logger
from .task_service import TaskService


class SubjectService:
    """Serviço para análise e agrupamento de processos por assunto principal."""
    
    def __init__(self, http_client: PJEHttpClient, task_service: TaskService):
        self.client = http_client
        self.task_service = task_service
        self.logger = get_logger()
        
        # Cache
        self._assuntos_cache: Dict[str, AssuntoPrincipal] = {}
        self._tarefas_ignoradas: Set[str] = set()
    
    def limpar_cache(self):
        """Limpa cache de assuntos."""
        self._assuntos_cache.clear()
        self._tarefas_ignoradas.clear()
    
    def definir_tarefas_ignoradas(self, nomes_tarefas: List[str]) -> None:
        """
        Define quais tarefas serão ignoradas na análise.
        
        Args:
            nomes_tarefas: Lista de nomes de tarefas a ignorar
        """
        self._tarefas_ignoradas = set(nomes_tarefas)
        self.logger.info(f"Tarefas ignoradas definidas: {len(self._tarefas_ignoradas)}")
    
    def listar_tarefas_disponiveis(self, force_refresh: bool = False) -> List[Tarefa]:
        """
        Lista todas as tarefas disponíveis (não favoritas).
        
        Args:
            force_refresh: Forçar atualização
        
        Returns:
            Lista de tarefas
        """
        return self.task_service.listar_tarefas(force_refresh)
    
    def analisar_assuntos_por_tarefas(
        self,
        tarefas: List[Tarefa] = None,
        callback_progresso: callable = None
    ) -> Dict[str, AssuntoPrincipal]:
        """
        Analisa e agrupa processos por assunto principal de todas as tarefas.
        
        Args:
            tarefas: Lista de tarefas a analisar (None = todas não ignoradas)
            callback_progresso: Callback para reportar progresso (tarefa_atual, total)
        
        Returns:
            Dict com assuntos e seus processos
        """
        if tarefas is None:
            tarefas = self.listar_tarefas_disponiveis()
        
        # Filtrar tarefas ignoradas
        tarefas_para_analisar = [
            t for t in tarefas 
            if t.nome not in self._tarefas_ignoradas and not t.favorita
        ]
        
        self.logger.info(f"Analisando {len(tarefas_para_analisar)} tarefas")
        
        assuntos: Dict[str, AssuntoPrincipal] = {}
        total_tarefas = len(tarefas_para_analisar)
        
        for idx, tarefa in enumerate(tarefas_para_analisar, 1):
            self.logger.info(f"[{idx}/{total_tarefas}] Analisando: {tarefa.nome}")
            
            if callback_progresso:
                callback_progresso(tarefa.nome, idx, total_tarefas)
            
            # Listar processos da tarefa
            processos = self.task_service.listar_todos_processos_tarefa(
                tarefa.nome,
                apenas_favoritas=False
            )
            
            self.logger.debug(f"  Processos encontrados: {len(processos)}")
            
            for proc in processos:
                assunto = proc.assunto_principal or "Sem assunto definido"
                
                if assunto not in assuntos:
                    assuntos[assunto] = AssuntoPrincipal(nome=assunto)
                
                assuntos[assunto].adicionar_processo(proc)
            
            delay(0.5, 1.0)
        
        # Ordenar por quantidade de processos (decrescente)
        assuntos_ordenados = dict(
            sorted(
                assuntos.items(),
                key=lambda x: x[1].quantidade,
                reverse=True
            )
        )
        
        self._assuntos_cache = assuntos_ordenados
        
        self.logger.info(f"Total de assuntos encontrados: {len(assuntos_ordenados)}")
        
        return assuntos_ordenados
    
    def buscar_assunto(self, termo_busca: str) -> List[AssuntoPrincipal]:
        """
        Busca assuntos pelo nome.
        
        Args:
            termo_busca: Termo de busca (case-insensitive)
        
        Returns:
            Lista de assuntos que correspondem à busca
        """
        termo_lower = termo_busca.lower().strip()
        
        resultados = []
        for assunto in self._assuntos_cache.values():
            if termo_lower in assunto.nome.lower():
                resultados.append(assunto)
        
        return resultados
    
    def obter_assunto(self, nome: str) -> Optional[AssuntoPrincipal]:
        """
        Obtém assunto específico pelo nome exato.
        
        Args:
            nome: Nome do assunto
        
        Returns:
            AssuntoPrincipal ou None
        """
        return self._assuntos_cache.get(nome)
    
    def obter_processos_por_assunto(self, nome_assunto: str) -> List[ProcessoTarefa]:
        """
        Obtém todos os processos de um assunto específico.
        
        Args:
            nome_assunto: Nome do assunto
        
        Returns:
            Lista de processos
        """
        assunto = self.obter_assunto(nome_assunto)
        if assunto:
            return assunto.processos
        return []
    
    def listar_todos_assuntos(self) -> List[AssuntoPrincipal]:
        """
        Lista todos os assuntos em cache.
        
        Returns:
            Lista de assuntos ordenados por quantidade
        """
        return list(self._assuntos_cache.values())
    
    def get_estatisticas(self) -> Dict[str, int]:
        """
        Retorna estatísticas dos assuntos.
        
        Returns:
            Dict com estatísticas
        """
        total_assuntos = len(self._assuntos_cache)
        total_processos = sum(a.quantidade for a in self._assuntos_cache.values())
        
        return {
            "total_assuntos": total_assuntos,
            "total_processos": total_processos,
            "tarefas_ignoradas": len(self._tarefas_ignoradas)
        }