#!/bin/bash
# ========================================
# PJE Download Manager - Inicializacao
# ========================================

echo ""
echo "========================================"
echo "  PJE Download Manager"
echo "========================================"
echo ""

# Verifica se Python esta instalado
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "[ERRO] Python nao encontrado!"
    echo "Por favor, instale Python 3.8 ou superior."
    exit 1
fi

# Executa o script de inicializacao Python
$PYTHON iniciar.py
