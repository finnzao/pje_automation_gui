@echo off
REM ========================================
REM PJE Download Manager - Inicializacao
REM ========================================

echo.
echo  ========================================
echo   PJE Download Manager
echo  ========================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Por favor, instale Python 3.8 ou superior.
    echo Acesse: https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Durante a instalacao, marque a opcao
    echo "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Executa o script de inicializacao Python
python iniciar.py

pause
