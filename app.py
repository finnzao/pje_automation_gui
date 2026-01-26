"""
PJE Download Manager - Ponto de entrada da aplicação.

Este arquivo serve como ponto de entrada para o Streamlit.
Toda a lógica foi movida para o módulo ui.app.
"""

import sys
from pathlib import Path

# Garantir que o diretório raiz está no path
sys.path.insert(0, str(Path(__file__).parent))

# Importar e executar a aplicação
from ui.app.main import Application


def main():
    """Função principal de entrada."""
    app = Application()
    app.run()


if __name__ == "__main__":
    main()