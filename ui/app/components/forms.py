import streamlit as st
from typing import Optional, Callable, Any, List, Tuple
from dataclasses import dataclass

from .base import BaseComponent, ComponentConfig, CallbackMixin


@dataclass
class FormFieldConfig(ComponentConfig):
    """Configuração para campos de formulário."""
    
    label: str = ""
    placeholder: str = ""
    help_text: Optional[str] = None
    required: bool = False


class SearchInput(BaseComponent):
    """
    Campo de busca/filtro.
    """
    
    def __init__(
        self,
        key: str,
        label: str = "",
        placeholder: str = "Digite para buscar...",
        value: str = "",
        on_change: Optional[Callable] = None,
    ):
        """
        Inicializa o campo de busca.
        
        Args:
            key: Chave única
            label: Label do campo
            placeholder: Placeholder
            value: Valor inicial
            on_change: Callback ao mudar
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            placeholder=placeholder,
        )
        super().__init__(config)
        self._value = value
        self._on_change = on_change
    
    def render(self) -> str:
        """
        Renderiza o campo.
        
        Returns:
            Valor digitado
        """
        return st.text_input(
            label=self._config.label,
            value=self._value,
            placeholder=self._config.placeholder,
            key=self._config.key,
            on_change=self._on_change,
        )


class NumberInput(BaseComponent):
    """
    Campo numérico.
    """
    
    def __init__(
        self,
        key: str,
        label: str,
        min_value: int = 0,
        max_value: int = 100,
        value: int = 0,
        step: int = 1,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o campo numérico.
        
        Args:
            key: Chave única
            label: Label do campo
            min_value: Valor mínimo
            max_value: Valor máximo
            value: Valor inicial
            step: Incremento
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            help_text=help_text,
        )
        super().__init__(config)
        self._min_value = min_value
        self._max_value = max_value
        self._value = value
        self._step = step
    
    def render(self) -> int:
        """
        Renderiza o campo.
        
        Returns:
            Valor selecionado
        """
        return st.number_input(
            label=self._config.label,
            min_value=self._min_value,
            max_value=self._max_value,
            value=self._value,
            step=self._step,
            key=self._config.key,
            help=self._config.help_text,
        )


class SelectBox(BaseComponent):
    """
    Campo de seleção (dropdown).
    """
    
    def __init__(
        self,
        key: str,
        label: str,
        options: List[Any],
        index: int = 0,
        format_func: Optional[Callable] = None,
        on_change: Optional[Callable] = None,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o campo de seleção.
        
        Args:
            key: Chave única
            label: Label do campo
            options: Lista de opções
            index: Índice inicial
            format_func: Função para formatar opções
            on_change: Callback ao mudar
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            help_text=help_text,
        )
        super().__init__(config)
        self._options = options
        self._index = index
        self._format_func = format_func
        self._on_change = on_change
    
    def render(self) -> Any:
        """
        Renderiza o campo.
        
        Returns:
            Opção selecionada
        """
        return st.selectbox(
            label=self._config.label,
            options=self._options,
            index=self._index,
            format_func=self._format_func,
            key=self._config.key,
            on_change=self._on_change,
            help=self._config.help_text,
        )


class TextArea(BaseComponent):
    """
    Campo de texto multilinha.
    """
    
    def __init__(
        self,
        key: str,
        label: str,
        placeholder: str = "",
        value: str = "",
        height: int = 150,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o campo de texto.
        
        Args:
            key: Chave única
            label: Label do campo
            placeholder: Placeholder
            value: Valor inicial
            height: Altura em pixels
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            placeholder=placeholder,
            help_text=help_text,
        )
        super().__init__(config)
        self._value = value
        self._height = height
    
    def render(self) -> str:
        """
        Renderiza o campo.
        
        Returns:
            Texto digitado
        """
        return st.text_area(
            label=self._config.label,
            value=self._value,
            placeholder=self._config.placeholder,
            height=self._height,
            key=self._config.key,
            help=self._config.help_text,
        )


class Checkbox(BaseComponent):
    """
    Campo de checkbox.
    """
    
    def __init__(
        self,
        key: str,
        label: str,
        value: bool = False,
        on_change: Optional[Callable] = None,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o checkbox.
        
        Args:
            key: Chave única
            label: Label do campo
            value: Valor inicial
            on_change: Callback ao mudar
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            help_text=help_text,
        )
        super().__init__(config)
        self._value = value
        self._on_change = on_change
    
    def render(self) -> bool:
        """
        Renderiza o checkbox.
        
        Returns:
            True se marcado
        """
        return st.checkbox(
            label=self._config.label,
            value=self._value,
            key=self._config.key,
            on_change=self._on_change,
            help=self._config.help_text,
        )


class Slider(BaseComponent):
    """
    Campo de slider.
    """
    
    def __init__(
        self,
        key: str,
        label: str,
        min_value: int = 0,
        max_value: int = 100,
        value: int = 50,
        step: int = 1,
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o slider.
        
        Args:
            key: Chave única
            label: Label do campo
            min_value: Valor mínimo
            max_value: Valor máximo
            value: Valor inicial
            step: Incremento
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            help_text=help_text,
        )
        super().__init__(config)
        self._min_value = min_value
        self._max_value = max_value
        self._value = value
        self._step = step
    
    def render(self) -> int:
        """
        Renderiza o slider.
        
        Returns:
            Valor selecionado
        """
        return st.slider(
            label=self._config.label,
            min_value=self._min_value,
            max_value=self._max_value,
            value=self._value,
            step=self._step,
            key=self._config.key,
            help=self._config.help_text,
        )


class LoginForm(BaseComponent):
    """
    Formulário de login completo.
    """
    
    def __init__(
        self,
        key_prefix: str = "login",
        saved_username: str = "",
        saved_password: str = "",
        show_save_option: bool = True,
        default_save: bool = False,
        on_submit: Optional[Callable[[str, str, bool], None]] = None,
    ):
        """
        Inicializa o formulário de login.
        
        Args:
            key_prefix: Prefixo para chaves
            saved_username: Username salvo
            saved_password: Password salvo
            show_save_option: Se mostra opção de salvar
            default_save: Valor padrão do checkbox salvar
            on_submit: Callback ao submeter (username, password, save)
        """
        super().__init__()
        self._key_prefix = key_prefix
        self._saved_username = saved_username
        self._saved_password = saved_password
        self._show_save_option = show_save_option
        self._default_save = default_save
        self._on_submit = on_submit
    
    def render(self) -> Optional[Tuple[str, str, bool]]:
        """
        Renderiza o formulário.
        
        Returns:
            Tuple (username, password, save) se submetido, None caso contrário
        """
        with st.form(f"{self._key_prefix}_form", clear_on_submit=False):
            st.subheader("Login")
            
            username = st.text_input(
                "CPF",
                value=self._saved_username,
                placeholder="Digite seu CPF",
                key=f"{self._key_prefix}_username",
            )
            
            password = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
                key=f"{self._key_prefix}_password",
            )
            
            save_credentials = False
            if self._show_save_option:
                save_credentials = st.checkbox(
                    "Salvar credenciais neste computador",
                    value=self._default_save,
                    key=f"{self._key_prefix}_save",
                )
            
            submitted = st.form_submit_button(
                "Entrar",
                use_container_width=True,
                type="primary",
            )
            
            if submitted:
                if not username or not password:
                    st.error("Por favor, preencha CPF e senha")
                    return None
                
                if self._on_submit:
                    self._on_submit(username, password, save_credentials)
                
                return (username, password, save_credentials)
        
        return None


class PasswordInput(BaseComponent):
    """
    Campo de senha.
    """
    
    def __init__(
        self,
        key: str,
        label: str = "Senha",
        placeholder: str = "Digite sua senha",
        help_text: Optional[str] = None,
    ):
        """
        Inicializa o campo de senha.
        
        Args:
            key: Chave única
            label: Label do campo
            placeholder: Placeholder
            help_text: Texto de ajuda
        """
        config = FormFieldConfig(
            key=key,
            label=label,
            placeholder=placeholder,
            help_text=help_text,
        )
        super().__init__(config)
    
    def render(self) -> str:
        """
        Renderiza o campo.
        
        Returns:
            Senha digitada
        """
        return st.text_input(
            label=self._config.label,
            type="password",
            placeholder=self._config.placeholder,
            key=self._config.key,
            help=self._config.help_text,
        )