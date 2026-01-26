import streamlit as st
import re
from typing import List, Tuple, Optional

from .base import BasePage
from ..config import DOCUMENT_TYPE_CONFIG
from ..components.forms import TextArea, SelectBox
from ..components.buttons import ActionButton, NavigationButton
from ..components.lists import ProcessList


class DownloadByNumberPage(BasePage):
    """
    Página para download de processos por número CNJ.
    """
    
    PAGE_TITLE = "Download por Número de Processo"
    REQUIRES_AUTH = True
    REQUIRES_PROFILE = True
    
    def _render_sidebar(self) -> None:
        """Renderiza sidebar com configurações."""
        with st.sidebar:
            st.header("Configurações")
            
            # Tipo de documento
            self._document_type = st.selectbox(
                "Tipo de documento",
                options=list(DOCUMENT_TYPE_CONFIG.OPTIONS),
                index=0,
                key="select_tipo_doc"
            )
            
            st.markdown("---")
            
            # Botão voltar
            if st.button(
                "Voltar ao menu",
                use_container_width=True,
                key="btn_back_number"
            ):
                self._navigation.go_to_main_menu()
    
    @staticmethod
    def _validate_process_number(numero: str) -> bool:
        """
        Valida número de processo no formato CNJ.
        
        Args:
            numero: Número a validar
        
        Returns:
            True se válido
        """
        numero = numero.strip()
        pattern = r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$'
        return bool(re.match(pattern, numero))
    
    @staticmethod
    def _format_process_number(numero: str) -> Optional[str]:
        """
        Formata número de processo para formato CNJ.
        
        Args:
            numero: Número a formatar
        
        Returns:
            Número formatado ou None se inválido
        """
        # Extrair apenas números
        only_numbers = re.sub(r'[^\d]', '', numero)
        
        if len(only_numbers) != 20:
            return None
        
        # Formatar: NNNNNNN-DD.AAAA.J.TR.OOOO
        return (
            f"{only_numbers[:7]}-{only_numbers[7:9]}."
            f"{only_numbers[9:13]}.{only_numbers[13]}."
            f"{only_numbers[14:16]}.{only_numbers[16:20]}"
        )
    
    def _parse_input(self, text: str) -> Tuple[List[str], List[str]]:
        """
        Processa entrada de texto e separa processos válidos e inválidos.
        
        Args:
            text: Texto com números de processos
        
        Returns:
            Tuple (válidos, inválidos)
        """
        valid = []
        invalid = []
        
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        
        for line in lines:
            # Tentar formatar
            formatted = self._format_process_number(line)
            
            if formatted:
                valid.append(formatted)
            elif self._validate_process_number(line):
                valid.append(line)
            else:
                invalid.append(line)
        
        # Remover duplicados mantendo ordem
        valid = list(dict.fromkeys(valid))
        
        return valid, invalid
    
    def _render_instructions(self) -> None:
        """Renderiza instruções de uso."""
        st.markdown("""
        ### Instruções
        
        Digite os números dos processos que deseja baixar, um por linha.
        
        **Formatos aceitos:**
        - Com formatação: `0000001-23.2024.8.05.0001`
        - Sem formatação: `00000012320248050001`
        
        **Observação:** Os processos devem estar acessíveis no seu perfil atual.
        """)
    
    def _handle_start_download(self, processes: List[str]) -> None:
        """
        Inicia o download dos processos.
        
        Args:
            processes: Lista de números de processos válidos
        """
        self._navigation.go_to_processing_number(
            processes=processes,
            document_type=self._document_type
        )
    
    def _render_content(self) -> None:
        """Renderiza conteúdo da página."""
        # Inicializar variáveis da sidebar
        self._document_type = DOCUMENT_TYPE_CONFIG.DEFAULT
        
        # Instruções
        self._render_instructions()
        
        # Campo de entrada
        input_text = st.text_area(
            "Números dos processos",
            placeholder="0000001-23.2024.8.05.0001\n0000002-45.2024.8.05.0001",
            height=150,
            key="textarea_numeros"
        )
        
        if input_text:
            # Processar entrada
            valid_processes, invalid_processes = self._parse_input(input_text)
            
            # Mostrar lista de processos
            process_list = ProcessList(
                valid_processes=valid_processes,
                invalid_processes=invalid_processes,
                show_stats=True
            )
            process_list.render()
            
            # Botão de iniciar
            if valid_processes:
                st.markdown("---")
                
                if st.button(
                    "Iniciar download",
                    type="primary",
                    use_container_width=True,
                    key="btn_start_number"
                ):
                    self._handle_start_download(valid_processes)
        else:
            st.info("Digite pelo menos um número de processo para continuar")