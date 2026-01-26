from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, Dict
from dataclasses import dataclass, field


@dataclass
class ComponentConfig:
    """Configuração base para componentes."""
    
    key: Optional[str] = None
    disabled: bool = False
    visible: bool = True
    css_class: str = ""
    extra_props: Dict[str, Any] = field(default_factory=dict)


class BaseComponent(ABC):
    """
    Classe base abstrata para todos os componentes.
    
    Define a interface comum que todos os componentes
    devem implementar.
    """
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        """
        Inicializa o componente.
        
        Args:
            config: Configuração do componente
        """
        self._config = config or ComponentConfig()
        self._rendered = False
    
    @property
    def key(self) -> Optional[str]:
        """Retorna a chave única do componente."""
        return self._config.key
    
    @property
    def is_disabled(self) -> bool:
        """Verifica se o componente está desabilitado."""
        return self._config.disabled
    
    @property
    def is_visible(self) -> bool:
        """Verifica se o componente está visível."""
        return self._config.visible
    
    def _generate_key(self, prefix: str = "component") -> str:
        """
        Gera uma chave única para o componente.
        
        Args:
            prefix: Prefixo da chave
        
        Returns:
            Chave única
        """
        if self._config.key:
            return self._config.key
        
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    @abstractmethod
    def render(self) -> Any:
        """
        Renderiza o componente.
        
        Returns:
            Resultado da renderização (depende do componente)
        """
        pass
    
    def __call__(self) -> Any:
        """Permite chamar o componente diretamente."""
        return self.render()


class ContainerComponent(BaseComponent):
    """
    Componente que pode conter outros componentes.
    """
    
    def __init__(
        self,
        children: list = None,
        config: Optional[ComponentConfig] = None
    ):
        """
        Inicializa o container.
        
        Args:
            children: Lista de componentes filhos
            config: Configuração do componente
        """
        super().__init__(config)
        self._children = children or []
    
    def add_child(self, component: BaseComponent) -> None:
        """
        Adiciona componente filho.
        
        Args:
            component: Componente a adicionar
        """
        self._children.append(component)
    
    def remove_child(self, component: BaseComponent) -> None:
        """
        Remove componente filho.
        
        Args:
            component: Componente a remover
        """
        if component in self._children:
            self._children.remove(component)
    
    def clear_children(self) -> None:
        """Remove todos os componentes filhos."""
        self._children.clear()
    
    def render_children(self) -> list:
        """
        Renderiza todos os componentes filhos.
        
        Returns:
            Lista de resultados da renderização
        """
        results = []
        for child in self._children:
            if child.is_visible:
                results.append(child.render())
        return results
    
    def render(self) -> Any:
        """Renderiza o container e seus filhos."""
        if not self.is_visible:
            return None
        
        return self.render_children()


class CallbackMixin:
    """
    Mixin para componentes que suportam callbacks.
    """
    
    def __init__(self):
        self._callbacks: Dict[str, Callable] = {}
    
    def on(self, event: str, callback: Callable) -> 'CallbackMixin':
        """
        Registra callback para um evento.
        
        Args:
            event: Nome do evento
            callback: Função a chamar
        
        Returns:
            Self para encadeamento
        """
        self._callbacks[event] = callback
        return self
    
    def trigger(self, event: str, *args, **kwargs) -> Any:
        """
        Dispara um evento.
        
        Args:
            event: Nome do evento
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
        
        Returns:
            Resultado do callback ou None
        """
        callback = self._callbacks.get(event)
        if callback:
            return callback(*args, **kwargs)
        return None
    
    def has_callback(self, event: str) -> bool:
        """
        Verifica se existe callback para o evento.
        
        Args:
            event: Nome do evento
        
        Returns:
            True se existir callback
        """
        return event in self._callbacks