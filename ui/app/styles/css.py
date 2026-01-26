import streamlit as st
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Colors:
    """Paleta de cores da aplicação."""
    
    PRIMARY: str = "#667eea"
    PRIMARY_HOVER: str = "#5a6fd6"
    
    SUCCESS: str = "#155724"
    SUCCESS_BG: str = "#d4edda"
    
    WARNING: str = "#856404"
    WARNING_BG: str = "#fff3cd"
    
    ERROR: str = "#721c24"
    ERROR_BG: str = "#f8d7da"
    
    INFO: str = "#0c5460"
    INFO_BG: str = "#d1ecf1"
    
    BACKGROUND: str = "#ffffff"
    SECONDARY_BG: str = "#f0f2f6"
    TEXT: str = "#262730"
    
    SHADOW: str = "rgba(0,0,0,0.15)"


class StyleManager:
    """
    Gerenciador centralizado de estilos CSS.
    
    Fornece métodos para aplicar estilos globais
    e gerar estilos para componentes específicos.
    """
    
    COLORS = Colors()
    
    @classmethod
    def get_global_css(cls) -> str:
        """Retorna CSS global da aplicação."""
        return f"""
        <style>
            /* Ocultar elementos padrão do Streamlit */
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            
            /* Container principal */
            .block-container {{
                padding-top: 2rem;
                max-width: 1200px;
            }}
            
            /* Botões */
            .stButton > button {{
                border-radius: 4px;
                font-weight: 500;
                transition: all 0.3s ease;
            }}
            
            .stButton > button:hover {{
                transform: translateY(-1px);
                box-shadow: 0 2px 8px {cls.COLORS.SHADOW};
            }}
            
            /* Barra de progresso */
            .stProgress > div > div > div {{
                background-color: {cls.COLORS.PRIMARY};
            }}
            
            /* Métricas */
            [data-testid="stMetricValue"] {{
                font-size: 1.5rem;
            }}
            
            /* Badges de status */
            .status-badge {{
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 12px;
                font-size: 0.875rem;
                font-weight: 500;
            }}
            
            .status-success {{
                background-color: {cls.COLORS.SUCCESS_BG};
                color: {cls.COLORS.SUCCESS};
            }}
            
            .status-warning {{
                background-color: {cls.COLORS.WARNING_BG};
                color: {cls.COLORS.WARNING};
            }}
            
            .status-error {{
                background-color: {cls.COLORS.ERROR_BG};
                color: {cls.COLORS.ERROR};
            }}
            
            .status-info {{
                background-color: {cls.COLORS.INFO_BG};
                color: {cls.COLORS.INFO};
            }}
            
            /* Cards */
            .card {{
                background-color: {cls.COLORS.BACKGROUND};
                border-radius: 8px;
                padding: 1.5rem;
                box-shadow: 0 2px 4px {cls.COLORS.SHADOW};
                margin-bottom: 1rem;
            }}
            
            .card-title {{
                font-size: 1.25rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
                color: {cls.COLORS.TEXT};
            }}
            
            .card-description {{
                color: #666;
                margin-bottom: 1rem;
            }}
            
            /* Lista de itens */
            .list-item {{
                padding: 0.75rem 0;
                border-bottom: 1px solid #eee;
            }}
            
            .list-item:last-child {{
                border-bottom: none;
            }}
            
            /* Cabeçalho de página */
            .page-header {{
                margin-bottom: 1.5rem;
            }}
            
            .page-title {{
                font-size: 2rem;
                font-weight: 700;
                color: {cls.COLORS.TEXT};
            }}
            
            .page-subtitle {{
                color: #666;
                font-size: 0.9rem;
            }}
        </style>
        """
    
    @classmethod
    def apply_global_styles(cls) -> None:
        """Aplica estilos globais à aplicação."""
        st.markdown(cls.get_global_css(), unsafe_allow_html=True)
    
    @classmethod
    def get_status_badge_html(cls, status: str, text: str = None) -> str:
        """
        Gera HTML para badge de status.
        
        Args:
            status: Tipo do status (success, warning, error, info)
            text: Texto a exibir (opcional)
        
        Returns:
            HTML do badge
        """
        display_text = text or status.replace("_", " ").title()
        css_class = f"status-{status}" if status in ["success", "warning", "error", "info"] else "status-info"
        
        return f'<span class="status-badge {css_class}">{display_text}</span>'
    
    @classmethod
    def get_card_html(cls, title: str, description: str = "", content: str = "") -> str:
        """
        Gera HTML para card.
        
        Args:
            title: Título do card
            description: Descrição (opcional)
            content: Conteúdo HTML adicional (opcional)
        
        Returns:
            HTML do card
        """
        desc_html = f'<p class="card-description">{description}</p>' if description else ""
        
        return f"""
        <div class="card">
            <h3 class="card-title">{title}</h3>
            {desc_html}
            {content}
        </div>
        """
    
    @classmethod
    def get_status_badge_for_processing(cls, status: str) -> str:
        """
        Retorna HTML do badge baseado no status de processamento.
        
        Args:
            status: Status do processamento
        
        Returns:
            HTML do badge
        """
        from ..config import STATUS_CONFIG
        
        status_mapping = {
            STATUS_CONFIG.CONCLUIDO: ("success", "Concluído"),
            STATUS_CONFIG.CONCLUIDO_COM_FALHAS: ("warning", "Concluído com falhas"),
            STATUS_CONFIG.CANCELADO: ("error", "Cancelado"),
            STATUS_CONFIG.ERRO: ("error", "Erro"),
            STATUS_CONFIG.PROCESSANDO: ("info", "Processando"),
        }
        
        if status in status_mapping:
            badge_type, text = status_mapping[status]
            return cls.get_status_badge_html(badge_type, text)
        
        display_text = STATUS_CONFIG.get_display_text(status)
        return cls.get_status_badge_html("info", display_text)