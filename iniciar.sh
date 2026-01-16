#!/bin/bash
# ========================================
# PJE Download Manager - Inicialização
# ========================================

echo ""
echo "========================================"
echo "  PJE Download Manager"
echo "========================================"
echo ""

# Verifica se Python está instalado
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "[ERRO] Python não encontrado!"
    echo "Por favor, instale Python 3.8 ou superior."
    exit 1
fi

# Executa o script de inicialização Python
$PYTHON iniciar.py
