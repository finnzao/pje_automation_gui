import streamlit as st
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass
from pathlib import Path

from .base import BaseComponent


@dataclass
class ListItemConfig:
    """Configuração para item de lista."""
    
    title: str = ""
    subtitle: str = ""
    badge: Optional[str] = None
    icon: Optional[str] = None
    data: Any = None


class ItemList(BaseComponent):
    """
    Lista genérica de itens com ações.
    """
    
    def __init__(
        self,
        items: List[Dict[str, Any]],
        on_item_click: Optional[Callable[[Any], None]] = None,
        action_label: str = "Selecionar",
        key_prefix: str = "list",
        show_divider: bool = True,
        empty_message: str = "Nenhum item encontrado",
    ):
        """
        Inicializa a lista.
        
        Args:
            items: Lista de items (dicts com title, subtitle, badge, data)
            on_item_click: Callback ao clicar em item
            action_label: Label do botão de ação
            key_prefix: Prefixo para chaves
            show_divider: Se mostra divisores
            empty_message: Mensagem quando vazio
        """
        super().__init__()
        self._items = items
        self._on_item_click = on_item_click
        self._action_label = action_label
        self._key_prefix = key_prefix
        self._show_divider = show_divider
        self._empty_message = empty_message
    
    def render(self) -> Optional[Any]:
        """
        Renderiza a lista.
        
        Returns:
            Data do item clicado ou None
        """
        if not self._items:
            st.info(self._empty_message)
            return None
        
        clicked_item = None
        
        for idx, item in enumerate(self._items):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Título
                title = item.get("title", "")
                icon = item.get("icon", "")
                if icon:
                    title = f"{icon} {title}"
                
                st.markdown(f"**{title}**")
                
                # Subtítulo
                subtitle = item.get("subtitle", "")
                if subtitle:
                    st.caption(subtitle)
            
            with col2:
                # Badge
                badge = item.get("badge", "")
                if badge:
                    st.caption(badge)
                
                # Botão de ação
                if st.button(
                    self._action_label,
                    key=f"{self._key_prefix}_{idx}",
                    use_container_width=True,
                ):
                    clicked_item = item.get("data", item)
                    if self._on_item_click:
                        self._on_item_click(clicked_item)
            
            if self._show_divider:
                st.markdown("---")
        
        return clicked_item


class ProfileList(BaseComponent):
    """
    Lista especializada para perfis.
    """
    
    def __init__(
        self,
        profiles: List[Any],
        on_select: Optional[Callable[[Any], None]] = None,
        key_prefix: str = "profile",
        filter_text: str = "",
    ):
        """
        Inicializa a lista de perfis.
        
        Args:
            profiles: Lista de objetos Perfil
            on_select: Callback ao selecionar
            key_prefix: Prefixo para chaves
            filter_text: Texto para filtrar
        """
        super().__init__()
        self._profiles = profiles
        self._on_select = on_select
        self._key_prefix = key_prefix
        self._filter_text = filter_text.lower()
    
    def _filter_profiles(self) -> List[Any]:
        """Filtra perfis pelo texto de busca."""
        if not self._filter_text:
            return self._profiles
        
        return [
            p for p in self._profiles
            if self._filter_text in p.nome_completo.lower()
        ]
    
    def _format_profile_display(self, profile: Any) -> str:
        """Formata nome do perfil para exibição."""
        nome_display = f"**{profile.nome}**"
        
        detalhes = []
        if profile.orgao:
            detalhes.append(profile.orgao)
        if profile.cargo:
            detalhes.append(profile.cargo)
        
        if detalhes:
            nome_display += f" - {' / '.join(detalhes)}"
        
        if hasattr(profile, 'favorito') and profile.favorito:
            nome_display += " ★"
        
        return nome_display
    
    def render(self) -> Optional[Any]:
        """
        Renderiza a lista de perfis.
        
        Returns:
            Perfil selecionado ou None
        """
        filtered = self._filter_profiles()
        
        if not filtered:
            st.warning("Nenhum perfil encontrado com o filtro aplicado")
            return None
        
        selected = None
        
        for profile in filtered:
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(self._format_profile_display(profile))
            
            with col2:
                key = f"{self._key_prefix}_{profile.index}_{profile.nome[:10]}"
                if st.button("Selecionar", key=key, use_container_width=True):
                    selected = profile
                    if self._on_select:
                        self._on_select(profile)
            
            st.markdown("---")
        
        return selected


class TaskList(BaseComponent):
    """
    Lista especializada para tarefas.
    """
    
    def __init__(
        self,
        tasks: List[Any],
        on_select: Optional[Callable[[Any], None]] = None,
        key_prefix: str = "task",
        filter_text: str = "",
        action_label: str = "Baixar",
    ):
        """
        Inicializa a lista de tarefas.
        
        Args:
            tasks: Lista de objetos Tarefa
            on_select: Callback ao selecionar
            key_prefix: Prefixo para chaves
            filter_text: Texto para filtrar
            action_label: Label do botão
        """
        super().__init__()
        self._tasks = tasks
        self._on_select = on_select
        self._key_prefix = key_prefix
        self._filter_text = filter_text.lower()
        self._action_label = action_label
    
    def _filter_tasks(self) -> List[Any]:
        """Filtra tarefas pelo texto de busca."""
        if not self._filter_text:
            return self._tasks
        
        return [
            t for t in self._tasks
            if self._filter_text in t.nome.lower()
        ]
    
    def render(self) -> Optional[Any]:
        """
        Renderiza a lista de tarefas.
        
        Returns:
            Tarefa selecionada ou None
        """
        filtered = self._filter_tasks()
        
        if not filtered:
            st.warning("Nenhuma tarefa encontrada")
            return None
        
        selected = None
        
        for idx, task in enumerate(filtered):
            col1, col2, col3 = st.columns([5, 1, 1])
            
            with col1:
                st.markdown(f"**{task.nome}**")
            
            with col2:
                st.caption(f"{task.quantidade_pendente} pendente(s)")
            
            with col3:
                key = f"{self._key_prefix}_{idx}_{task.id}"
                if st.button(self._action_label, key=key, use_container_width=True):
                    selected = task
                    if self._on_select:
                        self._on_select(task)
            
            st.markdown("---")
        
        return selected


class TagList(BaseComponent):
    """
    Lista especializada para etiquetas.
    """
    
    def __init__(
        self,
        tags: List[Any],
        on_select: Optional[Callable[[Any], None]] = None,
        key_prefix: str = "tag",
        action_label: str = "Baixar",
    ):
        """
        Inicializa a lista de etiquetas.
        
        Args:
            tags: Lista de objetos Etiqueta
            on_select: Callback ao selecionar
            key_prefix: Prefixo para chaves
            action_label: Label do botão
        """
        super().__init__()
        self._tags = tags
        self._on_select = on_select
        self._key_prefix = key_prefix
        self._action_label = action_label
    
    def render(self) -> Optional[Any]:
        """
        Renderiza a lista de etiquetas.
        
        Returns:
            Etiqueta selecionada ou None
        """
        if not self._tags:
            return None
        
        selected = None
        
        for idx, tag in enumerate(self._tags):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"**{tag.nome}**")
            
            with col2:
                key = f"{self._key_prefix}_{idx}_{tag.id}"
                if st.button(self._action_label, key=key, use_container_width=True):
                    selected = tag
                    if self._on_select:
                        self._on_select(tag)
            
            st.markdown("---")
        
        return selected


class ProcessList(BaseComponent):
    """
    Lista de processos (números CNJ).
    """
    
    def __init__(
        self,
        valid_processes: List[str],
        invalid_processes: List[str] = None,
        show_stats: bool = True,
        max_display: int = 50,
    ):
        """
        Inicializa a lista de processos.
        
        Args:
            valid_processes: Processos válidos
            invalid_processes: Processos inválidos
            show_stats: Se mostra estatísticas
            max_display: Máximo de itens a exibir
        """
        super().__init__()
        self._valid = valid_processes
        self._invalid = invalid_processes or []
        self._show_stats = show_stats
        self._max_display = max_display
    
    def render(self) -> None:
        """Renderiza a lista de processos."""
        # Estatísticas
        if self._show_stats:
            col1, col2 = st.columns(2)
            
            with col1:
                if self._valid:
                    st.success(f"Válidos: {len(self._valid)}")
            
            with col2:
                if self._invalid:
                    st.error(f"Inválidos: {len(self._invalid)}")
        
        # Lista de válidos
        if self._valid:
            with st.expander(f"Ver processos válidos ({len(self._valid)})"):
                for proc in self._valid[:self._max_display]:
                    st.code(proc)
                
                if len(self._valid) > self._max_display:
                    st.caption(
                        f"... e mais {len(self._valid) - self._max_display} processo(s)"
                    )
        
        # Lista de inválidos
        if self._invalid:
            with st.expander(f"Ver processos inválidos ({len(self._invalid)})"):
                for proc in self._invalid[:self._max_display]:
                    st.code(proc)


class FileList(BaseComponent):
    """
    Lista de arquivos baixados.
    """
    
    def __init__(
        self,
        files: List[str],
        max_display: int = 50,
        title: str = "Arquivos baixados",
    ):
        """
        Inicializa a lista de arquivos.
        
        Args:
            files: Lista de caminhos de arquivos
            max_display: Máximo de itens a exibir
            title: Título do expander
        """
        super().__init__()
        self._files = files
        self._max_display = max_display
        self._title = title
    
    def render(self) -> None:
        """Renderiza a lista de arquivos."""
        if not self._files:
            return
        
        with st.expander(f"{self._title} ({len(self._files)})"):
            for file_path in self._files[:self._max_display]:
                st.text(Path(file_path).name)
            
            if len(self._files) > self._max_display:
                st.caption(
                    f"... e mais {len(self._files) - self._max_display} arquivo(s)"
                )


class ErrorList(BaseComponent):
    """
    Lista de erros.
    """
    
    def __init__(
        self,
        errors: List[str],
        title: str = "Ver erros",
    ):
        """
        Inicializa a lista de erros.
        
        Args:
            errors: Lista de mensagens de erro
            title: Título do expander
        """
        super().__init__()
        self._errors = errors
        self._title = title
    
    def render(self) -> None:
        """Renderiza a lista de erros."""
        if not self._errors:
            return
        
        with st.expander(f"{self._title} ({len(self._errors)})"):
            for error in self._errors:
                st.error(error)