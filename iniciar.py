import sys
import subprocess
import time
import webbrowser
import socket
import os
from pathlib import Path


APP_NAME = "PJE Download Manager"
APP_FILE = "app.py"
DEFAULT_PORT = 8505
HOST = "127.0.0.1"


def print_header():
    print(f"  {APP_NAME}")


def check_python_version():
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"[ERRO] Python 3.8 ou superior e necessario.")
        print(f"       Versao atual: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_module(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def install_requirements():
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("[AVISO] Arquivo requirements.txt nao encontrado.")
        return False
    
    print("[INFO] Instalando dependencias...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file),
            "--quiet", "--disable-pip-version-check"
        ])
        print("[OK] Dependencias instaladas com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao instalar dependencias: {e}")
        return False


def check_dependencies() -> bool:
    required_modules = {
        "streamlit": "streamlit",
        "requests": "requests",
        "dotenv": "python-dotenv"
    }
    
    missing = []
    for module, package in required_modules.items():
        if not check_module(module):
            missing.append(package)
    
    if missing:
        print(f"[INFO] Modulos faltando: {', '.join(missing)}")
        return install_requirements()
    
    print("[OK] Todas as dependencias estao instaladas")
    return True


def find_available_port(start_port: int = 8505, max_tries: int = 10) -> int:
    for port in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((HOST, port))
                return port
        except OSError:
            continue
    return start_port


def open_browser(url: str, delay: float = 2.0):
    time.sleep(delay)
    print(f"[INFO] Abrindo navegador: {url}")
    webbrowser.open(url)


def run_streamlit(port: int):
    app_path = Path(__file__).parent / APP_FILE
    
    if not app_path.exists():
        print(f"[ERRO] Arquivo {APP_FILE} nao encontrado!")
        return False
    
    url = f"http://{HOST}:{port}"
    
    print(f"[INFO] Iniciando servidor na porta {port}...")
    print(f"[INFO] Acesse: {url}")
    print()
    print("[INFO] Para encerrar, pressione Ctrl+C")
    print()
    
    import threading
    browser_thread = threading.Thread(target=open_browser, args=(url, 3.0))
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.port", str(port),
            "--server.address", HOST,
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--theme.primaryColor", "#667eea",
            "--theme.backgroundColor", "#ffffff",
            "--theme.secondaryBackgroundColor", "#f0f2f6"
        ])
    except KeyboardInterrupt:
        print()
        print("[INFO] Servidor encerrado pelo usuario.")
    
    return True


def main():
    print_header()
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if not check_python_version():
        input("\nPressione Enter para sair...")
        sys.exit(1)
    
    if not check_dependencies():
        input("\nPressione Enter para sair...")
        sys.exit(1)
    
    print()
    
    port = find_available_port(DEFAULT_PORT)
    if port != DEFAULT_PORT:
        print(f"[INFO] Porta {DEFAULT_PORT} em uso, usando {port}")
    
    run_streamlit(port)


if __name__ == "__main__":
    main()
