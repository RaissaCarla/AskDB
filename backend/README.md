# Backend AskDB — marco de 20%

O backend oferece geração e validação de propostas SQL por FastAPI e por CLI,
compartilhando o mesmo caso de uso, com catálogo PostgreSQL real e Ollama local.
As verificações e evidências ambientais estão em `evidencias-marco20.md`.

## Preparar ambiente (PowerShell, na raiz do repositório)

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e './backend[dev]'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

Python 3.11 ou superior é necessário. Use o executável do ambiente virtual para
evitar conflitos com outras instalações Python no PATH.

## Configuração

API e CLI carregam automaticamente `backend/.env`, independentemente da pasta
atual do terminal. Para um checkout novo, copie `backend/.env.example` para
`backend/.env` e ajuste os valores. O arquivo local é ignorado pelo Git.
Variáveis já definidas no terminal prevalecem sobre o arquivo; remova valores
antigos com `Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue` se necessário.
O exemplo contém credenciais públicas exclusivas de desenvolvimento local.
O carregamento não modifica variáveis globais nem grava senhas pela aplicação.

| Variável | Valor inicial |
|---|---|
| DATABASE_URL | Obrigatória, URI PostgreSQL |
| OLLAMA_URL | http://127.0.0.1:11434 |
| OLLAMA_MODEL | qwen3.5:9b |
| LLM_TIMEOUT | 120 segundos |
| CONNECT_TIMEOUT | 5 segundos |

Configuração inválida gera mensagem sanitizada. O campo que contém a conexão
é protegido na representação dos objetos; isso não substitui um cofre de segredos.

## Organização

- `queries`: modelos da pergunta/proposta, política e caso de uso.
- `databases`: catálogo autorizado, contrato e integração PostgreSQL.
- `llm`: contrato e integração Ollama.
- `entrypoints`: entradas HTTP e terminal que compartilham o caso de uso.
- `settings.py`: configuração única por ambiente.
- `tests/unit` e `tests/integration`: verificações determinísticas e banco real.

## Política SQL inicial

O validador aceita uma única SELECT com projeções, filtros, JOINs, GROUP BY/HAVING,
ORDER BY, DISTINCT, LIMIT/OFFSET e COUNT, SUM, AVG, MIN, MAX, LOWER, UPPER e COALESCE
não qualificadas. Inspeciona toda a árvore sintática PostgreSQL com lista positiva
de expressões. Motivos de bloqueio têm código estável e mensagem em português.

Escrita, DDL, múltiplos comandos, SELECT INTO, locks, catálogos do sistema,
funções desconhecidas, CTEs, subconsultas, UNION e outras construções não suportadas
são bloqueados, inclusive em expressões internas. A aprovação não comprova
existência de objetos, interpretação correta, baixo custo ou segurança de execução.
Nenhuma SQL gerada será executada neste marco.

## PostgreSQL de demonstração

Com `backend/.env` configurado, suba o banco na raiz do repositório:

```powershell
docker compose --env-file backend/.env -f backend/compose.yaml up -d --wait
```

Para outra porta, altere `ASKDB_POSTGRES_PORT` no arquivo antes de subir e use essa porta
em `DATABASE_URL`. A aplicação nunca deve usar a credencial administrativa.
As senhas deste exemplo são exclusivas de desenvolvimento. Não use senhas reais
do usuário nem copie as variáveis para arquivos versionados.

A seed é aplicada somente na primeira inicialização do volume. Reiniciar o
contêiner preserva dados e credenciais anteriores. Não apague volumes existentes
para repetir testes: prefira um projeto Compose novo e uma porta livre.

O catálogo usa somente tabelas de aplicação, colunas com SELECT efetivo e
relacionamentos cujas duas pontas são autorizadas. É descoberto por solicitação,
sem amostras e sem cache. A role de demonstração não tem escrita, superuser ou
BYPASSRLS; informações de catálogo não substituem permissões reais no banco.

Para os testes reais, aponte `ASKDB_TEST_DATABASE_URL` para a role de leitura e
`ASKDB_TEST_ADMIN_URL` para a role administrativa **somente do banco de teste**:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/integration -q
```

Sem essas variáveis, testes de integração são explicitamente ignorados. O banco
de testes inclui tabelas restritas e chaves compostas para conferir o isolamento.

## Ollama local

Prepare o runtime Ollama e o modelo manualmente. Confira `ollama list` e, se
necessário, execute `ollama pull qwen3.5:9b` por sua decisão. A aplicação não
instala runtime, baixa modelos, troca de provedor ou repete chamadas automaticamente.
O endpoint e modelo são configurados pelas variáveis da tabela acima.

O adaptador usa a [API de chat do Ollama](https://docs.ollama.com/api/chat),
sem streaming de tokens para o usuário. Lê somente o conteúdo final, nunca o
raciocínio separado. Remove apenas um bloco Markdown integral; explicações ou
comandos extras não são descartados para tentar aprovar uma parte da resposta.

Limites iniciais: 64 KiB de resposta HTTP, 16000 caracteres de SQL, contexto de
32000 caracteres, conexão de 5 s e inferência de 120 s. Contexto excessivo é
recusado sem corte silencioso; caracteres não equivalem a tokens.
`LLM_TIMEOUT` e `CONNECT_TIMEOUT` podem ser ajustados. Modelo ausente gera
`llm_unavailable`, timeout gera `llm_timeout` e saída incompleta/inválida gera
`llm_invalid_response`. Verifique runtime/modelo, recursos disponíveis e limites
quando houver falhas. Perguntas e metadados continuam sujeitos à política fixa.

## Fluxo e erros

`GenerateSqlUseCase` valida a pergunta, descobre o catálogo, monta o contexto,
chama a LLM uma vez e aplica a política. `bootstrap.build_use_case` compõe os
adaptadores; nenhum contrato de execução SQL existe nesta entrega.

Eventos do logger `askdb` são JSON com fase, código e duração, sem conteúdo da
pergunta, SQL completa, senha ou resposta externa. Categorias públicas:
`configuration_error`, `database_unavailable`, `schema_unavailable`,
`llm_unavailable`, `llm_timeout`, `llm_invalid_response`.
Logs não são auditoria inviolável; erros externos são substituídos por mensagens
fixas e seguras. Aprovação significa apenas conformidade com a política inicial.

## FastAPI e Swagger

Depois de configurar o banco e o Ollama, inicie na raiz do repositório:

```powershell
backend/.venv/Scripts/python.exe -m askdb.entrypoints.api
```

O servidor inicia em `127.0.0.1:8000`. Abra `http://127.0.0.1:8000/docs` para o
Swagger. `GET /health` retorna `{"status":"ok"}` sem consultar banco/modelo.
`POST /queries/generate` recebe `{"question":"Quais são os cinco produtos mais vendidos?"}`.
Uma resposta tem o formato:

```json
{"sql":"SELECT nome FROM produtos LIMIT 5","validation":{"status":"approved","reasons":[]}}
```

SQL proibida também retorna HTTP 200, com status `blocked` e motivos
`[{"code":"...","message":"..."}]`. Erros usam `{"error":{"code":"...","message":"..."}}`:
entrada inválida 422; banco/catálogo/modelo/configuração indisponível 503;
timeout LLM 504; resposta LLM inválida 502; inesperados 500. Campos extras são
rejeitados. Não há CORS amplo nem execução SQL nesta API.

## CLI mínima

```powershell
backend/.venv/Scripts/python.exe -m askdb.entrypoints.cli
```

Não é preciso iniciar o servidor HTTP. A CLI chama diretamente o mesmo caso de
uso da API, usando banco e modelo configurados. Exemplo de interação (a SQL real
pode variar conforme o modelo):

```text
Sua pergunta > Liste os produtos

Consultando o esquema, gerando e validando a SQL... Aguarde.

------------------------------------------------------------
SQL proposta

SELECT nome FROM produtos

------------------------------------------------------------
[OK] Proposta aprovada pela política inicial.
Você pode inspecionar e copiar a SQL acima.
Tempo total: 2.0 s | SQL não executada.
------------------------------------------------------------

Sua pergunta > sair

Sessão encerrada. Até a próxima!
```

O tempo exibido é o tempo total de processamento e varia conforme o ambiente.
Mensagens de erro incluem dicas de configuração quando disponíveis. Eventos
técnicos em nível INFO não aparecem na interação normal da CLI.
Pergunta inválida ou falha tratada permite tentar novamente. `sair`, EOF ou
Ctrl+C encerra. Não há memória entre perguntas, persistência de conversa ou
execução da SQL. O comando da API usa o mesmo núcleo e pode ser experimentado
separadamente pelo Swagger.

## Evoluções previstas

O marco produz propostas sem executar a SQL. Execução com confirmação e
contexto por conexão pertencem à evolução V0; desktop, entrevista e persistência
pertencem à V1. CTEs e subconsultas permanecerão bloqueadas neste marco e poderão
ser avaliadas futuramente, com ampliação da política e dos testes.
