# Pesquisa: Endpoints de Conversão CNJ → idProcesso e Código de Autenticação (ca)

## Resumo Executivo

A análise dos arquivos HAR revelou **dois fluxos distintos** para abrir processos:

1. **Via Pesquisa Pública** - Requer captcha, o `idProcesso` e `ca` são retornados no HTML da resposta
2. **Via Painel de Tarefas** - **NÃO requer captcha**, usa endpoint REST dedicado para gerar o `ca`

### Endpoint Chave Descoberto (Tarefas)
```
GET /pje/seam/resource/rest/pje-legacy/painelUsuario/gerarChaveAcessoProcesso/{idProcesso}
```
Este endpoint retorna diretamente o código `ca` como texto, sem necessidade de captcha.

---

## 1. Endpoint Principal de Pesquisa

### URL
```
POST https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/listView.seam
```

### Função
Este é o endpoint que recebe o número CNJ desmembrado e retorna os resultados da pesquisa, incluindo o `idProcesso` e o código `ca`.

### Parâmetros do Número CNJ (desmembrado)

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `fPP:numeroProcesso:numeroSequencial` | Número sequencial | `8128688` |
| `fPP:numeroProcesso:numeroDigitoVerificador` | Dígito verificador | `83` |
| `fPP:numeroProcesso:Ano` | Ano do processo | `2024` |
| `fPP:numeroProcesso:ramoJustica` | Código do ramo (8 = Justiça Estadual) | `8` |
| `fPP:numeroProcesso:respectivoTribunal` | Código do tribunal (05 = TJBA) | `05` |
| `fPP:numeroProcesso:NumeroOrgaoJustica` | Código do órgão/vara | `0001` |

### Exemplo de CNJ Completo
```
8128688-83.2024.8.05.0001
   │      │   │   │  │  │
   │      │   │   │  │  └── NumeroOrgaoJustica (0001)
   │      │   │   │  └───── respectivoTribunal (05)
   │      │   │   └──────── ramoJustica (8)
   │      │   └──────────── Ano (2024)
   │      └──────────────── numeroDigitoVerificador (83)
   └─────────────────────── numeroSequencial (8128688)
```

### Outros Parâmetros Obrigatórios

| Parâmetro | Valor |
|-----------|-------|
| `AJAXREQUEST` | `_viewRoot` |
| `fPP:tencentCaptchaTicket` | Token do captcha resolvido |
| `fPP:tencentCaptchaRandStr` | String aleatória do captcha |
| `javax.faces.ViewState` | ID de estado da view (ex: `j_id28`) |

---

## 2. Resposta da Pesquisa

A resposta é um documento HTML/XML que contém uma tabela com os processos encontrados. Dentro desta resposta:

### Onde aparece o `idProcesso`

O `idProcesso` aparece em múltiplos lugares na resposta:

1. **Nos IDs dos elementos HTML:**
   ```html
   <td id="fPP:processosTable:15540469:j_id464">
   ```

2. **No evento onclick do link:**
   ```javascript
   'parameters':{'idProcessoSelecionado':15540469, ...}
   ```

3. **No ID da linha da tabela:**
   ```html
   <tr class="rich-table-row">
     <td id="fPP:processosTable:15540469:...">
   ```

---

## 3. Fluxo de Abertura do Processo (2 etapas)

### Etapa 1: Pesquisa (retorna lista com idProcesso)

```
POST /pje/Processo/ConsultaProcesso/listView.seam
    └── Envia: número CNJ desmembrado + captcha
    └── Recebe: HTML com tabela contendo idProcesso (ex: 15540469)
```

### Etapa 2: Seleção do Processo (gera o código `ca`)

```
POST /pje/Processo/ConsultaProcesso/listView.seam
    └── Envia: idProcessoSelecionado=15540469
    └── Recebe: JavaScript com URL completa incluindo o `ca`
```

### Resposta da Etapa 2 (geração do `ca`)
```javascript
var linkAutosDigitais = "https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam?idProcesso=";
linkAutosDigitais += "15540469&ca=0a237ecf469ddad996da4b544b3ba0552a7c94f747ead32bb770e0eba9689a31eb9e7db051137985e23a8fc338a700b8a1427afc19d16902";
window.open(linkAutosDigitais, 'autos15540469');
```

---

## 4. Código de Autenticação (`ca`)

### Características
- **Tamanho:** ~100 caracteres hexadecimais
- **Formato:** String hexadecimal (caracteres 0-9 e a-f)
- **Geração:** Server-side, não pode ser calculado pelo cliente
- **Propósito:** Token de autenticação/autorização para acessar o processo
- **Validade:** Possivelmente vinculado à sessão do usuário

### Exemplos encontrados:
```
ca=2f927bc3fdf595ca9c7de22e6ba3673c7d4f0af2be440251c81f2f6a74c31465540078797cccad27eff1a95d5a3df54add68

ca=0a237ecf469ddad996da4b544b3ba0552a7c94f747ead32bb770e0eba9689a31eb9e7db051137985e23a8fc338a700b8a1427afc19d16902
```

---

## 5. Endpoint de Visualização do Processo

### URL
```
GET https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam
```

### Parâmetros Query String

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `idProcesso` | ID interno do processo | `6005691` |
| `ca` | Código de autenticação | `2f927bc3fdf...` |
| `idTaskInstance` | (Opcional) ID da tarefa | `10902356705` |

### Exemplo Completo
```
https://pje.tjba.jus.br/pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam?idProcesso=6005691&ca=2f927bc3fdf595ca9c7de22e6ba3673c7d4f0af2be440251c81f2f6a74c31465540078797cccad27eff1a95d5a3df54add68&idTaskInstance=10902356705
```

---

## 6. Diagrama do Fluxo Completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FLUXO DE ABERTURA DE PROCESSO                  │
└─────────────────────────────────────────────────────────────────────┘

 ENTRADA: CNJ 8128688-83.2024.8.05.0001
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 1: Resolver Captcha (Tencent)                                 │
│ GET https://ca.turing.captcha.qcloud.com/cap_union_prehandle        │
│ Retorna: ticket + randStr                                           │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 2: Pesquisar Processo                                         │
│ POST /pje/Processo/ConsultaProcesso/listView.seam                   │
│                                                                     │
│ Enviar:                                                             │
│   - numeroSequencial: 8128688                                       │
│   - numeroDigitoVerificador: 83                                     │
│   - Ano: 2024                                                       │
│   - ramoJustica: 8                                                  │
│   - respectivoTribunal: 05                                          │
│   - NumeroOrgaoJustica: 0001                                        │
│   - tencentCaptchaTicket: [token]                                   │
│   - tencentCaptchaRandStr: [string]                                 │
│                                                                     │
│ Retorna: HTML com tabela, contendo idProcesso=15540469              │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 3: Selecionar Processo (Click no link)                        │
│ POST /pje/Processo/ConsultaProcesso/listView.seam                   │
│                                                                     │
│ Enviar:                                                             │
│   - idProcessoSelecionado: 15540469                                 │
│   - ajaxSingle: fPP:processosTable:15540469:j_id467                 │
│                                                                     │
│ Retorna: JavaScript com URL contendo ca                             │
│   idProcesso=15540469&ca=0a237ecf469ddad996da4b544b3ba...          │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 4: Abrir Autos Digitais                                       │
│ GET /pje/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam   │
│                                                                     │
│ Query params:                                                       │
│   - idProcesso: 15540469                                            │
│   - ca: 0a237ecf469ddad996da4b544b3ba0552a7c94f747ead32bb...       │
│                                                                     │
│ Retorna: Página completa do processo                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. FLUXO VIA TAREFAS (SEM CAPTCHA) ⭐

### Descoberta Principal

Quando o usuário está autenticado e acessa processos pelo **Painel de Tarefas**, existe um endpoint REST dedicado que gera o código `ca` **sem necessidade de captcha**.

### Endpoint de Geração do `ca`

```
GET https://pje.tjba.jus.br/pje/seam/resource/rest/pje-legacy/painelUsuario/gerarChaveAcessoProcesso/{idProcesso}
```

### Características
| Aspecto | Valor |
|---------|-------|
| Método | GET |
| Autenticação | Cookie de sessão |
| Response Type | `text/plain` |
| Captcha | **NÃO REQUER** |
| Retorno | Código `ca` diretamente como string |

### Exemplo de Uso (JavaScript do Frontend)

```javascript
// Código extraído do frontend PJE (22-es2015.js)
carregarChaveProcesso(idProcesso) {
    return this.http.get(
        this.getLegacyUrl(this.urlPrefix + "/gerarChaveAcessoProcesso/" + idProcesso),
        { responseType: "text" }
    );
}

// Uso para abrir processo
carregarChaveProcesso(this.idProcessoTrf).subscribe(ca => {
    let url = "/Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam" +
              "?idProcesso=" + this.idProcessoTrf +
              "&ca=" + ca;
    
    if (this.idTaskInstance != null) {
        url += "&idTaskInstance=" + this.idTaskInstance;
    }
    
    window.open(this.config.pjeLegacyWebRootFromPayload + url);
});
```

### Fluxo Completo via Tarefas

```
┌─────────────────────────────────────────────────────────────────────┐
│           FLUXO DE ABERTURA VIA TAREFAS (SEM CAPTCHA)               │
└─────────────────────────────────────────────────────────────────────┘

 Usuário autenticado no PJE
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 1: Listar Tarefas                                             │
│ POST /seam/resource/rest/pje-legacy/painelUsuario/tarefas           │
│                                                                     │
│ Request body: {"numeroProcesso":"","competencia":"","etiquetas":[]} │
│                                                                     │
│ Retorna: Lista de tarefas com id e quantidade                       │
│   [{"id": 7473880873, "nome": "Minutar ato de decisão", ...}]       │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 2: Listar Processos da Tarefa                                 │
│ POST /seam/resource/rest/pje-legacy/painelUsuario/                  │
│       recuperarProcessosTarefaPendenteComCriterios/{nomeTarefa}     │
│                                                                     │
│ Retorna: Lista de processos com idProcesso e idTaskInstance         │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 3: Gerar Chave de Acesso (ca) ⭐ SEM CAPTCHA                  │
│ GET /seam/resource/rest/pje-legacy/painelUsuario/                   │
│     gerarChaveAcessoProcesso/{idProcesso}                           │
│                                                                     │
│ Headers: Cookie de sessão                                           │
│ Response: ca (texto plano)                                          │
│   Exemplo: "0a237ecf469ddad996da4b544b3ba0552a7c94f747ead32bb..."   │
└─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 4: Abrir Processo                                             │
│ GET /Processo/ConsultaProcesso/Detalhe/listAutosDigitais.seam       │
│     ?idProcesso={idProcesso}&ca={ca}&idTaskInstance={idTask}        │
│                                                                     │
│ Retorna: Página completa do processo                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Diferença dos Dois Fluxos

| Aspecto | Via Pesquisa Pública | Via Tarefas |
|---------|---------------------|-------------|
| Captcha | ✅ Obrigatório (Tencent) | ❌ Não requer |
| Autenticação | Pode ser anônimo | Requer login |
| Endpoint `ca` | Embutido no HTML | REST dedicado |
| Conversão CNJ→ID | Server-side no HTML | Já vem na lista de tarefas |

---

## 8. Endpoints REST Descobertos

### Base URL
```
https://pje.tjba.jus.br/pje/seam/resource/rest/pje-legacy
```

### Endpoints do Painel de Usuário

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/painelUsuario/tarefas` | POST | Lista tarefas do usuário |
| `/painelUsuario/tarefas/minutas` | GET | Lista tarefas de minutas |
| `/painelUsuario/tarefasFavoritas` | POST | Lista tarefas favoritas |
| `/painelUsuario/processos/{id}` | GET | Detalhes de um processo |
| `/painelUsuario/gerarChaveAcessoProcesso/{idProcesso}` | GET | **Gera o código `ca`** |
| `/painelUsuario/lembretes/{id}` | DELETE | Remove lembrete |

### Endpoints de Tarefas

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/painelUsuario/recuperarProcessosTarefaPendenteComCriterios/{nome}/{page}` | POST | Lista processos de uma tarefa |
| `/painelUsuario/recuperarProcessoPorTarefaIdentificador/{nome}/{id}` | GET | Busca processo específico |

---

## 9. Conclusões

1. **Dois fluxos distintos:** O sistema PJE oferece duas formas de acessar processos:
   - **Pesquisa pública:** Requer captcha, `ca` vem embutido no HTML
   - **Painel de tarefas:** Sem captcha, endpoint REST dedicado para gerar `ca`

2. **Endpoint chave para automação:** 
   ```
   GET /seam/resource/rest/pje-legacy/painelUsuario/gerarChaveAcessoProcesso/{idProcesso}
   ```
   Este endpoint permite gerar o código `ca` diretamente, sem captcha, desde que o usuário esteja autenticado.

3. **Conversão CNJ → idProcesso:** 
   - Na pesquisa: acontece server-side, retornado no HTML
   - Nas tarefas: o `idProcesso` já vem na lista de processos da tarefa

4. **Código `ca`:** É um hash de ~100 caracteres que funciona como token de autorização. Pode ser gerado:
   - Automaticamente pelo servidor ao clicar em um resultado de pesquisa
   - Via endpoint REST para usuários autenticados no painel de tarefas

5. **Autenticação:** O acesso via tarefas requer cookie de sessão válido, mas dispensa captcha.

6. **Possibilidade de automação:** Com uma sessão autenticada, é possível automatizar a abertura de processos usando o endpoint `gerarChaveAcessoProcesso`, sem precisar resolver captchas.