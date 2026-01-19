# PJE Download Manager

Sistema de download automatico de processos do PJE-TJBA (Tribunal de Justica da Bahia).

## Indice

1. O que e
2. Instalacao Rapida
3. Como Usar
4. Perguntas Frequentes
5. Uso Avancado (Terminal)
6. Solucao de Problemas

## O que e

O PJE Download Manager e uma ferramenta que automatiza o download de processos judiciais do PJE, permitindo:

- Download em massa por Tarefa (ex: "Minutar sentenca")
- Download em massa por Etiqueta (ex: processos marcados como "Urgente")
- Interface grafica facil de usar
- Acompanhamento em tempo real do progresso
- Relatorios de execucao

## Instalacao Rapida

### Passo 1: Instalar Python

Se voce ainda nao tem Python instalado:

1. Acesse python.org/downloads
2. Baixe a versao 3.10 ou superior
3. Durante a instalacao, marque a opcao "Add Python to PATH"

### Passo 2: Baixar o Programa

1. Baixe o arquivo ZIP do programa
2. Extraia para uma pasta de sua preferencia (ex: C:\PJE-Download)

### Passo 3: Instalar Dependencias

Abra o Prompt de Comando (Windows) ou Terminal (Mac/Linux) na pasta do programa e execute:

```bash
pip install -r requirements.txt
```

### Passo 4: Iniciar o Programa

Execute o comando:

```bash
streamlit run app.py
```

O programa abrira automaticamente no seu navegador!

## Como Usar

### 1. Login

1. Digite seu CPF (apenas numeros)
2. Digite sua senha do PJE
3. Opcionalmente, marque "Salvar login neste computador"
4. Clique em Entrar

### 2. Selecionar Perfil

- Escolha o perfil que deseja usar (ex: Assessoria, Gabinete)
- Clique no perfil desejado

### 3. Escolher Tipo de Download

- Download por Tarefa: Baixa processos de uma tarefa especifica
- Download por Etiqueta: Baixa processos marcados com uma etiqueta

### 4. Selecionar e Baixar

Por Tarefa:
1. Navegue pela lista de tarefas
2. Use a busca para filtrar
3. Clique em Baixar na tarefa desejada

Por Etiqueta:
1. Digite o nome da etiqueta
2. Selecione a etiqueta encontrada
3. Clique em Baixar

### 5. Acompanhar Progresso

- Veja o andamento em tempo real
- Acompanhe qual processo esta sendo baixado
- Visualize o log de execucao

### 6. Resultado

- Veja o resumo do processamento
- Clique em Abrir Pasta de Downloads para ver os arquivos
- Baixe o relatorio em JSON se desejar

## Perguntas Frequentes

### Onde ficam os arquivos baixados?

Na pasta downloads dentro do diretorio do programa. Voce pode clicar em "Abrir Pasta de Downloads" para acessa-la diretamente.

### Minhas credenciais sao seguras?

Sim! Se voce marcar "Salvar login neste computador", suas credenciais sao:
- Armazenadas localmente no seu computador
- Criptografadas antes de serem salvas
- Nunca enviadas para servidores externos

### Posso processar todos os processos de uma vez?

Sim, mas recomendamos processar em lotes menores (50-100 processos) para evitar problemas com o PJE.

### O programa funciona em segundo plano?

Nao. Mantenha a janela do navegador aberta durante o processamento.

## Uso Avancado (Terminal)

Para usuarios avancados, o programa tambem funciona via linha de comando:

### Download por Tarefa

```bash
# Baixar todos os processos de uma tarefa
python downloadProcessByTask.py -t "Minutar sentenca"

# Com perfil especifico
python downloadProcessByTask.py -t "Minutar sentenca" -p "Assessoria"

# Limitar quantidade
python downloadProcessByTask.py -t "Minutar sentenca" --limite 10

# Listar tarefas disponiveis
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

Crie um arquivo .env na pasta do programa:

```
PJE_USER=00000000000
PJE_PASSWORD=sua_senha
```

## Solucao de Problemas

### "Falha no login"

- Verifique se CPF e senha estao corretos
- Tente fazer login diretamente no PJE para confirmar que as credenciais funcionam
- Aguarde alguns minutos e tente novamente (pode ser rate limit)

### "Sessao expirada"

- Faca login novamente
- Se persistir, clique em "Usar outras credenciais" e faca novo login

### "Nenhuma tarefa encontrada"

- Verifique se o perfil selecionado esta correto
- Algumas tarefas so aparecem para perfis especificos

### "Erro ao baixar processo"

- Pode ser um processo sigiloso ou com acesso restrito
- O sistema continuara com os proximos processos

### O programa nao abre

1. Verifique se o Python esta instalado: python --version
2. Verifique se as dependencias estao instaladas: pip list
3. Tente reinstalar: pip install -r requirements.txt --force-reinstall

## Estrutura de Arquivos

```
pje_download_manager/
  app.py                      # Interface grafica (Streamlit)
  downloadProcessByTask.py    # Script CLI - Download por tarefa
  downloadProcessByTag.py     # Script CLI - Download por etiqueta
  requirements.txt            # Dependencias Python
  .env.example                # Exemplo de configuracao
  README.md                   # Este arquivo
  pje_lib/                    # Biblioteca de automacao
    __init__.py
    client.py                 # Cliente principal
    config.py                 # Configuracoes
    models/                   # Modelos de dados
    core/                     # Componentes fundamentais
    services/                 # Servicos (auth, task, tag, download)
    utils/                    # Utilitarios
  ui/                         # Interface
    __init__.py
    credential_manager.py     # Gerenciador de credenciais
  downloads/                  # Pasta de downloads (criada automaticamente)
  .config/                    # Configuracoes locais (criada automaticamente)
  .session/                   # Dados de sessao (criada automaticamente)
  .logs/                      # Logs de execucao (criada automaticamente)
```
