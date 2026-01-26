import streamlit as st
from typing import Optional, Callable, Any
from dataclasses import dataclass

from .base import BaseComponent, ComponentConfig, CallbackMixin


@dataclass
class ButtonConfig(ComponentConfig):
    """Configuração específica para botões."""
    
    label: str = "Button"
    type: str = "secondary"  # primary, secondary
    use_container_width: bool = False
    icon: Optional[str] = None
    help_text: Optional[str] = None


class ButtonComponent(BaseComponent, CallbackMixin):
    """
    Componente de botão básico.
    
    Encapsula st.button com funcionalidades adicionais.
    """
    
    def __init__(
        self,
        label: str,
        key: str,
        on_click: Optional[Callable] = None,
        button_type: str = "secondary",
        use_container_width: bool = False,
        disabled: bool = False,
        icon: Optional[str] = None,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o botão.
        
        Args:
            label: Texto do botão
            key: Chave única
            on_click: Callback ao clicar
            button_type: Tipo (primary/secondary)
            use_container_width: Se ocupa largura total
            disabled: Se está desabilitado
            icon: Ícone opcional
            help_text: Texto de ajuda
        """
        config = ButtonConfig(
            key=key,
            label=label,
            type=button_type,
            use_container_width=use_container_width,
            disabled=disabled,
            icon=icon,
            help_text=help_text,
        )
        BaseComponent.__init__(self, config)
        CallbackMixin.__init__(self)
        
        self._label = label
        self._on_click = on_click
        
        if on_click:
            self.on("click", on_click)
    
    @property
    def label(self) -> str:
        """Retorna o label do botão."""
        display_label = self._label
        if self._config.icon:
            display_label = f"{self._config.icon} {display_label}"
        return display_label
    
    def render(self) -> bool:
        """
        Renderiza o botão.
        
        Returns:
            True se o botão foi clicado
        """
        if not self.is_visible:
            return False
        
        clicked = st.button(
            label=self.label,
            key=self._config.key,
            type=self._config.type,
            disabled=self._config.disabled,
            use_container_width=self._config.use_container_width,
            help=self._config.help_text,
        )
        
        if clicked and self.has_callback("click"):
            self.trigger("click")
        
        return clicked


class ActionButton(ButtonComponent):
    """
    Botão de ação principal (primary).
    """
    
    def __init__(
        self,
        label: str,
        key: str,
        on_click: Optional[Callable] = None,
        use_container_width: bool = True,
        disabled: bool = False,
        icon: Optional[str] = None,
    ):
        super().__init__(
            label=label,
            key=key,
            on_click=on_click,
            button_type="primary",
            use_container_width=use_container_width,
            disabled=disabled,
            icon=icon,
        )


class NavigationButton(ButtonComponent):
    """
    Botão de navegação (secondary).
    """
    
    def __init__(
        self,
        label: str,
        key: str,
        on_click: Optional[Callable] = None,
        use_container_width: bool = True,
        disabled: bool = False,
        icon: Optional[str] = None,
    ):
        super().__init__(
            label=label,
            key=key,
            on_click=on_click,
            button_type="secondary",
            use_container_width=use_container_width,
            disabled=disabled,
            icon=icon,
        )


class CancelButton(ButtonComponent):
    """
    Botão de cancelamento.
    """
    
    def __init__(
        self,
        key: str,
        on_click: Optional[Callable] = None,
        label: str = "Cancelar",
        use_container_width: bool = True,
    ):
        super().__init__(
            label=label,
            key=key,
            on_click=on_click,
            button_type="secondary",
            use_container_width=use_container_width,
            icon="🛑",
        )


class ConfirmationDialog(BaseComponent):
    """
    Diálogo de confirmação com dois botões.
    """
    
    def __init__(
        self,
        message: str,
        confirm_label: str = "Sim",
        cancel_label: str = "Não",
        key_prefix: str = "confirm",
        on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
    ):
        """
        Inicializa o diálogo.
        
        Args:
            message: Mensagem de confirmação
            confirm_label: Label do botão de confirmação
            cancel_label: Label do botão de cancelamento
            key_prefix: Prefixo para chaves
            on_confirm: Callback ao confirmar
            on_cancel: Callback ao cancelar
        """
        super().__init__()
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._key_prefix = key_prefix
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
    
    def render(self) -> Optional[bool]:
        """
        Renderiza o diálogo.
        
        Returns:
            True se confirmou, False se cancelou, None se nenhum
        """
        st.warning(self._message)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                self._confirm_label,
                key=f"{self._key_prefix}_confirm",
                type="primary",
                use_container_width=True,
            ):
                if self._on_confirm:
                    self._on_confirm()
                return True
        
        with col2:
            if st.button(
                self._cancel_label,
                key=f"{self._key_prefix}_cancel",
                use_container_width=True,
            ):
                if self._on_cancel:
                    self._on_cancel()
                return False
        
        return None


class ButtonGroup(BaseComponent):
    """
    Grupo de botões em linha.
    """
    
    def __init__(
        self,
        buttons: list,
        columns: Optional[int] = None,
    ):
        """
        Inicializa o grupo.
        
        Args:
            buttons: Lista de ButtonComponent
            columns: Número de colunas (None = automático)
        """
        super().__init__()
        self._buttons = buttons
        self._columns = columns or len(buttons)
    
    def render(self) -> list:
        """
        Renderiza o grupo de botões.
        
        Returns:
            Lista de resultados (True/False para cada botão)
        """
        results = []
        cols = st.columns(self._columns)
        
        for i, button in enumerate(self._buttons):
            col_index = i % self._columns
            with cols[col_index]:
                results.append(button.render())
        
        return results