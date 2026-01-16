# ⚖️ PJE Download Manager

Sistema de download automático de processos do **PJE-TJBA** (Tribunal de Justiça da Bahia).

![Interface do PJE Download Manager](docs/screenshot.png)

---

## 📋 Índice

1. [O que é](#-o-que-é)
2. [Instalação Rápida](#-instalação-rápida)
3. [Como Usar](#-como-usar)
4. [Perguntas Frequentes](#-perguntas-frequentes)
5. [Uso Avançado (Terminal)](#-uso-avançado-terminal)
6. [Solução de Problemas](#-solução-de-problemas)

---

## 🎯 O que é

O **PJE Download Manager** é uma ferramenta que automatiza o download de processos judiciais do PJE, permitindo:

- ✅ Download em massa por **Tarefa** (ex: "Minutar sentença")
- ✅ Download em massa por **Etiqueta** (ex: processos marcados como "Urgente")
- ✅ Interface gráfica fácil de usar
- ✅ Acompanhamento em tempo real do progresso
- ✅ Relatórios de execução

---

## 🚀 Instalação Rápida

### Passo 1: Instalar Python

Se você ainda não tem Python instalado:

1. Acesse [python.org/downloads](https://www.python.org/downloads/)
2. Baixe a versão 3.10 ou superior
3. Durante a instalação, **marque a opção "Add Python to PATH"**

### Passo 2: Baixar o Programa

1. Baixe o arquivo ZIP do programa
2. Extraia para uma pasta de sua preferência (ex: `C:\PJE-Download`)

### Passo 3: Instalar Dependências

Abra o **Prompt de Comando** (Windows) ou **Terminal** (Mac/Linux) na pasta do programa e execute:

```bash
pip install -r requirements.txt
```

### Passo 4: Iniciar o Programa

Execute o comando:

```bash
streamlit run app.py
```

O programa abrirá automaticamente no seu navegador! 🎉

---

## 📖 Como Usar

### 1️⃣ Login

![Tela de Login](docs/login.png)

1. Digite seu **CPF** (apenas números)
2. Digite sua **senha** do PJE
3. Opcionalmente, marque "Salvar login neste computador"
4. Clique em **Entrar**

### 2️⃣ Selecionar Perfil

![Tela de Perfil](docs/perfil.png)

- Escolha o perfil que deseja usar (ex: Assessoria, Gabinete)
- Clique no perfil desejado

### 3️⃣ Escolher Tipo de Download

![Menu Principal](docs/menu.png)

- **Download por Tarefa**: Baixa processos de uma tarefa específica
- **Download por Etiqueta**: Baixa processos marcados com uma etiqueta

### 4️⃣ Selecionar e Baixar

#### Por Tarefa:
1. Navegue pela lista de tarefas
2. Use a busca para filtrar
3. Clique em **Baixar** na tarefa desejada

#### Por Etiqueta:
1. Digite o nome da etiqueta
2. Selecione a etiqueta encontrada
3. Clique em **Baixar**

### 5️⃣ Acompanhar Progresso

![Progresso](docs/progresso.png)

- Veja o andamento em tempo real
- Acompanhe qual processo está sendo baixado
- Visualize o log de execução

### 6️⃣ Resultado

![Resultado](docs/resultado.png)

- Veja o resumo do processamento
- Clique em **Abrir Pasta de Downloads** para ver os arquivos
- Baixe o relatório em JSON se desejar

---

## ❓ Perguntas Frequentes

### Onde ficam os arquivos baixados?

Na pasta `downloads` dentro do diretório do programa. Você pode clicar em "Abrir Pasta de Downloads" para acessá-la diretamente.

### Minhas credenciais são seguras?

Sim! Se você marcar "Salvar login neste computador", suas credenciais são:
- Armazenadas **localmente** no seu computador
- **Criptografadas** antes de serem salvas
- Nunca enviadas para servidores externos

### Posso processar todos os processos de uma vez?

Sim, mas recomendamos processar em lotes menores (50-100 processos) para evitar problemas com o PJE.

### O programa funciona em segundo plano?

Não. Mantenha a janela do navegador aberta durante o processamento.

---

## 🖥️ Uso Avançado (Terminal)

Para usuários avançados, o programa também funciona via linha de comando:

### Download por Tarefa

```bash
# Baixar todos os processos de uma tarefa
python downloadProcessByTask.py -t "Minutar sentença"

# Com perfil específico
python downloadProcessByTask.py -t "Minutar sentença" -p "Assessoria"

# Limitar quantidade
python downloadProcessByTask.py -t "Minutar sentença" --limite 10

# Listar tarefas disponíveis
python downloadProcessByTask.py --listar-tarefas
```

### Download por Etiqueta

```bash
# Baixar processos de uma etiqueta
python downloadProcessByTag.py -e "Felipe"

# Buscar etiquetas
python downloadProcessByTag.py --buscar-etiqueta "Fel"

# Listar perfis
python downloadProcessByTag.py --listar-perfis
```

### Usando arquivo .env

Crie um arquivo `.env` na pasta do programa:

```
PJE_USER=00000000000
PJE_PASSWORD=sua_senha
```

---

## 🔧 Solução de Problemas

### "Falha no login"

- Verifique se CPF e senha estão corretos
- Tente fazer login diretamente no PJE para confirmar que as credenciais funcionam
- Aguarde alguns minutos e tente novamente (pode ser rate limit)

### "Sessão expirada"

- Faça login novamente
- Se persistir, clique em "Usar outras credenciais" e faça novo login

### "Nenhuma tarefa encontrada"

- Verifique se o perfil selecionado está correto
- Algumas tarefas só aparecem para perfis específicos

### "Erro ao baixar processo"

- Pode ser um processo sigiloso ou com acesso restrito
- O sistema continuará com os próximos processos

### O programa não abre

1. Verifique se o Python está instalado: `python --version`
2. Verifique se as dependências estão instaladas: `pip list`
3. Tente reinstalar: `pip install -r requirements.txt --force-reinstall`

---

## 📝 Estrutura de Arquivos

```
pje_download_manager/
├── app.py                      # Interface gráfica (Streamlit)
├── downloadProcessByTask.py    # Script CLI - Download por tarefa
├── downloadProcessByTag.py     # Script CLI - Download por etiqueta
├── requirements.txt            # Dependências Python
├── .env.example                # Exemplo de configuração
├── README.md                   # Este arquivo
│
├── pje_lib/                    # Biblioteca de automação
│   ├── __init__.py
│   ├── client.py               # Cliente principal
│   ├── config.py               # Configurações
│   ├── models/                 # Modelos de dados
│   ├── core/                   # Componentes fundamentais
│   ├── services/               # Serviços (auth, task, tag, download)
│   └── utils/                  # Utilitários
│
├── ui/                         # Interface
│   ├── __init__.py
│   └── credential_manager.py   # Gerenciador de credenciais
│
├── downloads/                  # Pasta de downloads (criada automaticamente)
├── .config/                    # Configurações locais (criada automaticamente)
├── .session/                   # Dados de sessão (criada automaticamente)
└── .logs/                      # Logs de execução (criada automaticamente)
```

---

## 📄 Licença

Este software é fornecido "como está", sem garantias de qualquer tipo. Use por sua conta e risco.

---

## 🤝 Suporte

Em caso de dúvidas ou problemas, verifique:
1. Se as credenciais do PJE estão corretas
2. Se o PJE está funcionando normalmente
3. Se há conexão com a internet

---

**Desenvolvido para facilitar o trabalho de advogados, assessores e servidores do TJBA** ⚖️
