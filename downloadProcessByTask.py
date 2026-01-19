#!/usr/bin/env python3
"""
Download de processos por TAREFA.

Uso:
    python downloadProcessByTask.py --tarefa "Minutar sentenca" --perfil "Assessoria"
    python downloadProcessByTask.py -t "Minutar sentenca" -p "Assessoria" --favoritas
    python downloadProcessByTask.py --help
"""

import argparse
from pje_lib import PJEClient


def main():
    parser = argparse.ArgumentParser(
        description="Download de processos por TAREFA do PJE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python downloadProcessByTask.py -t "Minutar sentenca"
  python downloadProcessByTask.py -t "Minutar sentenca" -p "Assessoria"
  python downloadProcessByTask.py -t "Minutar sentenca" --favoritas
  python downloadProcessByTask.py -t "Minutar sentenca" --limite 5
  python downloadProcessByTask.py --listar-tarefas
  python downloadProcessByTask.py --listar-perfis
        """
    )
    
    parser.add_argument("-t", "--tarefa", type=str, help="Nome da tarefa a processar")
    parser.add_argument("-p", "--perfil", type=str, help="Nome do perfil a selecionar")
    
    parser.add_argument("--favoritas", action="store_true", help="Buscar em tarefas favoritas")
    parser.add_argument("--limite", type=int, help="Limitar quantidade de processos")
    parser.add_argument("--tipo-documento", type=str, default="Selecione", 
                        help="Tipo de documento (default: Selecione)")
    parser.add_argument("--tempo-espera", type=int, default=300, 
                        help="Tempo maximo de espera em segundos (default: 300)")
    parser.add_argument("--sem-download", action="store_true", 
                        help="Apenas solicitar, nao aguardar download")
    parser.add_argument("--download-dir", type=str, default="./downloads",
                        help="Diretorio para downloads (default: ./downloads)")
    
    parser.add_argument("--listar-tarefas", action="store_true", help="Listar tarefas disponiveis")
    parser.add_argument("--listar-perfis", action="store_true", help="Listar perfis disponiveis")
    
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    
    args = parser.parse_args()
    
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
            print("\n=== PERFIS DISPONIVEIS ===")
            for p in pje.listar_perfis():
                print(f"  [{p.index}] {p.nome_completo}")
            return
        
        if args.listar_tarefas:
            print("\n=== TAREFAS FAVORITAS ===")
            for t in pje.listar_tarefas_favoritas():
                print(f"  [FAV] {t.nome}: {t.quantidade_pendente} processos")
            
            print("\n=== TAREFAS GERAIS ===")
            for t in pje.listar_tarefas():
                print(f"  - {t.nome}: {t.quantidade_pendente} processos")
            return
        
        if args.tarefa:
            relatorio = pje.processar_tarefa(
                nome_tarefa=args.tarefa,
                usar_favoritas=args.favoritas,
                limite=args.limite,
                tipo_documento=args.tipo_documento,
                aguardar_download=not args.sem_download,
                tempo_espera=args.tempo_espera
            )
            
            print(f"\nProcessamento concluido!")
            print(f"  Processos: {relatorio['processos']}")
            print(f"  Sucesso: {relatorio['sucesso']}")
            print(f"  Arquivos: {len(relatorio['arquivos'])}")
            print(f"  Diretorio: {relatorio['diretorio']}")
        else:
            parser.print_help()
        
    finally:
        pje.close()


if __name__ == "__main__":
    main()
