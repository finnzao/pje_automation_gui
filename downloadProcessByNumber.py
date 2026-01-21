#!/usr/bin/env python3
"""
Download de processos por NÚMERO.

Uso:
    python downloadProcessByNumber.py --numero "0000001-23.2024.8.05.0001"
    python downloadProcessByNumber.py -n "0000001-23.2024.8.05.0001" -n "0000002-45.2024.8.05.0001"
    python downloadProcessByNumber.py --arquivo lista_processos.txt
    python downloadProcessByNumber.py --help
"""

import argparse
import sys
from pathlib import Path
from pje_lib import PJEClient


def ler_numeros_de_arquivo(filepath: str) -> list:
    """Lê números de processos de um arquivo (um por linha)."""
    numeros = []
    path = Path(filepath)
    
    if not path.exists():
        print(f"Arquivo não encontrado: {filepath}")
        return []
    
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#'):
                numeros.append(linha)
    
    return numeros


def main():
    parser = argparse.ArgumentParser(
        description="Download de processos por NÚMERO do PJE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Download de um processo
  python downloadProcessByNumber.py -n "0000001-23.2024.8.05.0001"
  
  # Download de vários processos
  python downloadProcessByNumber.py -n "0000001-23.2024.8.05.0001" -n "0000002-45.2024.8.05.0001"
  
  # Download a partir de arquivo (um número por linha)
  python downloadProcessByNumber.py --arquivo lista_processos.txt
  
  # Com perfil específico
  python downloadProcessByNumber.py -n "0000001-23.2024.8.05.0001" -p "Assessoria"
  
  # Apenas buscar (sem baixar)
  python downloadProcessByNumber.py -n "0000001-23.2024.8.05.0001" --apenas-buscar

Formatos aceitos:
  - Com formatação: 0000001-23.2024.8.05.0001
  - Sem formatação: 00000012320248050001
        """
    )
    
    parser.add_argument("-n", "--numero", type=str, action="append",
                        help="Número do processo (pode usar múltiplas vezes)")
    parser.add_argument("--arquivo", type=str,
                        help="Arquivo com lista de números (um por linha)")
    parser.add_argument("-p", "--perfil", type=str, 
                        help="Nome do perfil a selecionar")
    
    parser.add_argument("--tipo-documento", type=str, default="Selecione", 
                        help="Tipo de documento (default: Selecione)")
    parser.add_argument("--tempo-espera", type=int, default=300, 
                        help="Tempo máximo de espera em segundos (default: 300)")
    parser.add_argument("--sem-download", action="store_true", 
                        help="Apenas solicitar, não aguardar download")
    parser.add_argument("--download-dir", type=str, default="./downloads",
                        help="Diretório para downloads (default: ./downloads)")
    
    parser.add_argument("--apenas-buscar", action="store_true",
                        help="Apenas buscar o processo, sem baixar")
    parser.add_argument("--listar-perfis", action="store_true", 
                        help="Listar perfis disponíveis")
    
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    
    args = parser.parse_args()
    
    # Coletar números de processos
    numeros = []
    
    if args.numero:
        numeros.extend(args.numero)
    
    if args.arquivo:
        numeros.extend(ler_numeros_de_arquivo(args.arquivo))
    
    # Criar cliente
    pje = PJEClient(
        download_dir=args.download_dir,
        debug=args.debug
    )
    
    try:
        if not pje.login():
            print("Falha no login! Verifique as credenciais no arquivo .env")
            print("O arquivo .env deve conter:")
            print("  PJE_USER=seu_cpf")
            print("  PJE_PASSWORD=sua_senha")
            return
        
        if args.perfil:
            if not pje.select_profile(args.perfil):
                print(f"Falha ao selecionar perfil: {args.perfil}")
                return
        
        if args.listar_perfis:
            print("\n=== PERFIS DISPONÍVEIS ===")
            for p in pje.listar_perfis():
                print(f"  [{p.index}] {p.nome_completo}")
            return
        
        if not numeros:
            parser.print_help()
            return
        
        # Remover duplicados mantendo ordem
        numeros = list(dict.fromkeys(numeros))
        
        print(f"\n=== {len(numeros)} PROCESSO(S) PARA PROCESSAR ===")
        for n in numeros:
            print(f"  - {n}")
        print()
        
        if args.apenas_buscar:
            # Apenas buscar informações
            print("=== BUSCANDO PROCESSOS ===\n")
            for numero in numeros:
                print(f"Buscando: {numero}...")
                info = pje.buscar_processo_por_numero(numero)
                if info:
                    print(f"  ✓ Encontrado!")
                    print(f"    ID: {info['id_processo']}")
                    print(f"    Método: {info['metodo']}")
                    if info.get('chave_acesso'):
                        print(f"    Chave: {info['chave_acesso'][:20]}...")
                else:
                    print(f"  ✗ Não encontrado")
                print()
        else:
            # Processar downloads
            relatorio = pje.processar_numeros(
                numeros_processos=numeros,
                tipo_documento=args.tipo_documento,
                aguardar_download=not args.sem_download,
                tempo_espera=args.tempo_espera
            )
            
            print(f"\n=== RESULTADO ===")
            print(f"  Status: {relatorio['status']}")
            print(f"  Processos: {relatorio['processos']}")
            print(f"  Sucesso: {relatorio['sucesso']}")
            print(f"  Falha: {relatorio['falha']}")
            print(f"  Arquivos: {len(relatorio['arquivos'])}")
            print(f"  Integridade: {relatorio['integridade']}")
            print(f"  Diretório: {relatorio['diretorio']}")
            
            if relatorio.get('erros'):
                print(f"\n  Erros:")
                for erro in relatorio['erros']:
                    print(f"    - {erro}")
            
            falhas = relatorio.get('retries', {}).get('processos_falha_definitiva', [])
            if falhas:
                print(f"\n  Processos com falha definitiva:")
                for p in falhas:
                    print(f"    - {p}")
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()
