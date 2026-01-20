# PJE Download Manager v2.1

Sistema de download automatizado de processos do PJE-TJBA (Tribunal de Justiça da Bahia).

## 📋 Resumo da Aplicação

O **PJE Download Manager** é uma ferramenta que automatiza o download em massa de processos judiciais do sistema PJE. A aplicação oferece:

### Funcionalidades Principais

| Funcionalidade | Descrição |
|----------------|-----------|
| **Download por Tarefa** | Baixa todos os processos de uma tarefa específica (ex: "Minutar sentença") |
| **Download por Etiqueta** | Baixa processos marcados com uma etiqueta específica (ex: "Urgente") |
| **Download por Número** | Baixa processo(s) específico(s) informando o número CNJ |
| **Interface Gráfica** | Interface web amigável via Streamlit |
| **Linha de Comando** | Scripts CLI para automação avançada |
| **Cancelamento** | Permite cancelar o processamento a qualquer momento |
| **Verificação de Integridade** | Confirma se todos os arquivos foram baixados corretamente |
| **Retries Automáticos** | Tenta novamente downloads que falharam |

### Fluxo de Funcionamento

```
1. Login (CPF + Senha)
      ↓
2. Seleção de Perfil (Assessoria, Gabinete, etc.)
      ↓
3. Escolha do Tipo de Download:
   ├── Por Tarefa → Lista tarefas → Seleciona → Baixa processos
   ├── Por Etiqueta → Busca etiqueta → Seleciona → Baixa processos
   └── Por Número → Informa número(s) → Baixa processo(s)
      ↓
4. Processamento (com barra de progresso)
      ↓
5. Resultado (relatório + arquivos baixados)
```

### Arquitetura do Sistema

```
pje_download_manager/
├── app.py                      # Interface gráfica (Streamlit)
├── downloadProcessByTask.py    # CLI - Download por tarefa
├── downloadProcessByTag.py     # CLI - Download por etiqueta
├── pje_lib/                    # Biblioteca de automação
│   ├── client.py               # Cliente principal (PJEClient)
│   ├── config.py               # Configurações (URLs, constantes)
│   ├── models/                 # Modelos de dados
│   │   └── __init__.py         # Usuario, Perfil, Tarefa, Processo, etc.
│   ├── core/                   # Componentes fundamentais
│   │   ├── http_client.py      # Cliente HTTP configurado
│   │   └── session_manager.py  # Gerenciador de sessão/cookies
│   ├── services/               # Serviços especializados
│   │   ├── auth_service.py     # Autenticação SSO
│   │   ├── task_service.py     # Gerenciamento de tarefas
│   │   ├── tag_service.py      # Gerenciamento de etiquetas
│   │   └── download_service.py # Download de processos
│   └── utils/                  # Utilitários
│       └── __init__.py         # Logger, helpers, etc.
└── ui/                         # Interface
    └── credential_manager.py   # Gerenciador de credenciais
```

## 🚀 Instalação

### Requisitos
- Python 3.8 ou superior
- Pip (gerenciador de pacotes)

### Passos

```bash
# 1. Clone ou baixe o projeto

# 2. Instale as dependências
pip install -r requirements.txt

# 3. (Opcional) Configure credenciais no .env
cp .env.example .env
# Edite o arquivo .env com seu CPF e senha
```

## 💻 Uso

### Interface Gráfica (Recomendado)

```bash
# Iniciar a interface
streamlit run app.py

# Ou use o script de inicialização
python iniciar.py
```

### Linha de Comando

```bash
# Download por Tarefa
python downloadProcessByTask.py -t "Minutar sentença" -p "Assessoria"

# Download por Etiqueta
python downloadProcessByTag.py -e "Urgente" --limite 10

# Listar tarefas disponíveis
python downloadProcessByTask.py --listar-tarefas

# Listar perfis
python downloadProcessByTag.py --listar-perfis
```

## 🔧 Correções na Versão 2.1

### Download por Número
- **Problema**: O sistema não conseguia encontrar o ID do processo via API
- **Solução**: Implementados 3 métodos alternativos de busca:
  1. Busca via API de consulta pública
  2. Busca via painel de tarefas do usuário
  3. Busca via etiquetas do usuário

### Cancelamento
- **Problema**: Clicar em "Cancelar" não interrompia o processamento
- **Solução**: Flag de cancelamento verificado em múltiplos pontos do loop:
  - No início de cada iteração
  - Antes e depois de cada operação de busca
  - Durante a espera de downloads
  - Durante os retries

## ⚠️ Limitações Conhecidas

1. **Download por Número**: O processo precisa estar acessível no perfil atual (em alguma tarefa ou etiqueta)
2. **Processos Sigilosos**: Podem falhar se o usuário não tiver permissão
3. **Rate Limiting**: O PJE pode temporariamente bloquear muitas requisições seguidas

## 📁 Onde ficam os arquivos?

- **Downloads**: `./downloads/` (organizado por tarefa/etiqueta/data)
- **Logs**: `./.logs/` (logs de execução)
- **Sessão**: `./.session/` (cookies para manter login)
- **Configurações**: `./.config/` (credenciais salvas)

## 🔐 Segurança

- Credenciais são criptografadas localmente
- Sessão é armazenada apenas no computador local
- Nenhum dado é enviado para servidores externos

## 📄 Licença

Uso interno - Tribunal de Justiça da Bahia
