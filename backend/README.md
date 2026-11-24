# Backend AskDB — V0

O backend oferece geração contextualizada e validação de SQL por CLI e FastAPI.
A CLI permite confirmar e executar a proposta exata em PostgreSQL somente leitura.
DeepSeek BYOK, Ollama e OpenAI usam o mesmo contrato. O estado das verificações
reais e simuladas está em [evidencias-v0.md](evidencias-v0.md); o registro do marco
anterior permanece em `evidencias-marco20.md`.

Para apresentar a V0 com três bancos fictícios, siga o [guia da demo no Windows](demo/README.md).

## Preparar ambiente

Na raiz do repositório, com Python 3.11+:

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e './backend[dev]'
backend/.venv/Scripts/python.exe -m pytest backend/tests -m 'not integration' -q
```

API e CLI carregam `backend/.env`, independente da pasta atual. Copie
`.env.example` e ajuste a conexão de desenvolvimento; variáveis do processo
prevalecem. A aplicação não regrava esse arquivo. Não use credencial administrativa
no fluxo da aplicação. Chaves remotas não são lidas do `.env`: use ambiente do
processo ou entrada oculta na CLI.

| Variável | Padrão / finalidade |
|---|---|
| `DATABASE_URL` | URI PostgreSQL obrigatória, com role explícita e de leitura |
| `LLM_PROVIDER` | `ollama`; selecione `deepseek` ou `openai` explicitamente |
| `LLM_MODEL` | Substitui o modelo do provedor configurado |
| `OLLAMA_URL`, `OLLAMA_MODEL` | `http://127.0.0.1:11434`, `qwen3.5:9b` |
| `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` | Chave runtime própria do provedor selecionado |
| `LLM_TIMEOUT`, `CONNECT_TIMEOUT` | 120 s e 5 s |
| `LLM_CONTEXT_WINDOW`, `LLM_OUTPUT_RESERVE` | 16384 e 2048 tokens |
| `ASKDB_MAX_ROWS` | 100 linhas, entre 1 e 1000 |
| `ASKDB_APP_DATA_DIR` | Override absoluto da pasta de dados por usuário |

## PostgreSQL sintético

```powershell
docker compose --env-file backend/.env -f backend/compose.yaml up -d --wait
```

Configure as senhas de desenvolvimento exigidas pelo Compose e `DATABASE_URL`
com a role `askdb_reader`. A porta padrão é 5433, alterável por
`ASKDB_POSTGRES_PORT`. A seed comercial contém clientes, produtos, pedidos e
itens, além de fixtures para permissões, chaves compostas, RLS, tipos e truncamento.
A seed só é aplicada em volume novo. Não remova volumes existentes para repetir
uma verificação; use o roteiro isolado abaixo.

## Pasta local e contexto por conexão

```text
%LOCALAPPDATA%\AskDB\
  connections\
    <id-da-conexao>\
      context.md
```

O ID considera host, porta, database e role, sem senha. Duas roles no mesmo banco
possuem contextos separados. O caminho não depende do checkout, da pasta de
instalação ou do diretório corrente. A composição prepara apenas os diretórios,
sem criar nem sobrescrever o Markdown. A CLI mostra o caminho absoluto esperado.
Para consultar esse caminho antes de iniciar:

```powershell
backend/.venv/Scripts/python.exe -c "from askdb.settings import Settings; s=Settings.from_env(); print(s.app_data_dir / 'connections' / s.connection.id / 'context.md')"
```

Prepare o arquivo manualmente em UTF-8; [examples/context.md](examples/context.md)
é uma referência sintética. Ausência permite contexto vazio informado. Arquivo
ilegível, UTF-8 inválido, tamanho excessivo ou escape por link/junction causa erro
explícito. Override de raiz deve ser absoluto e não há fallback silencioso para
uma pasta do repositório. Testes usam somente diretórios temporários.

`ContextBuilder` combina políticas fixas, catálogo autorizado atual, Markdown
integral, pergunta e pares de pergunta/SQL permitida da sessão. Markdown e
histórico são dados, sem autoridade para alterar políticas. Resultados, amostras,
segredos e erros brutos não entram no contexto da LLM. O arquivo fica no disco
após encerrar; as conversas e propostas pendentes ficam só em memória na V0.
SQLite e histórico persistente pertencem à V1, com referência `contexto_path` ao
Markdown por conexão.

## Perfis de IA e BYOK

A CLI apresenta DeepSeek, Ollama e OpenAI para seleção explícita. O perfil
DeepSeek usa `https://api.deepseek.com` e `deepseek-flash`; o perfil OpenAI usa
`https://api.openai.com/v1` e `gpt-4.1-mini`. Modelos são configuráveis, mas o
orçamento só aceita aqueles cujo método foi validado. Não há troca automática
de provedor ou modelo em caso de falha.

A chave é obtida do ambiente real do processo ou de `getpass` na CLI. No PowerShell:

```powershell
$env:LLM_PROVIDER = 'deepseek'
$env:DEEPSEEK_API_KEY = [Net.NetworkCredential]::new('', (Read-Host 'Chave DeepSeek' -AsSecureString)).Password
backend/.venv/Scripts/python.exe -m askdb.entrypoints.cli
```

Não coloque a chave no contexto, no chat nem em arquivos versionados. O código
não a grava: ela fica na autenticação HTTPS e não faz parte do `LLMProfile` ou
prompt. O provedor remoto recebe pergunta, esquema, Markdown e pares pergunta/SQL;
resultados ficam locais. Para OpenAI, use `OPENAI_API_KEY` e `LLM_PROVIDER=openai`.
Cada adaptador tem configuração e parâmetros próprios; apenas helpers privados
de transporte/normalização são compartilhados.

Ollama deve estar preparado manualmente, com `qwen3.5:9b` disponível. A aplicação
não instala runtime nem baixa modelos/tokenizadores ao perguntar. O transporte
não repete chamadas. Só conteúdo final completo é candidato a SQL; raciocínio,
ferramentas e saídas truncadas são rejeitados. Limites de resposta: 64 KiB de
corpo e 16000 caracteres de SQL final.

### Orçamento de contexto

`TokenBudgetPolicy` usa `utf8_upper_bound_v1`: bytes UTF-8 do texto, com margem de
512 tokens mais 64 por mensagem para o envelope. É estimativa conservadora,
validada para os perfis suportados, não contagem exata; pode recusar texto que
caberia no modelo. Os limites são 8000 para Markdown e
`min(16000, janela - reserva)` para toda a entrada, com reserva inicial de 2048.
Não há corte silencioso de regras ou pares: reduza explicitamente o arquivo ou
inicie outra sessão quando necessário.

Artefatos oficiais DeepSeek V4 e Qwen3.5-9B estão fixados por SHA-256 em
`tests/fixtures/tokenizer-manifest.json`. A verificação offline usa
`tokenizers==0.22.1`; OpenAI usa `tiktoken==0.12.0`/`o200k_base`, apenas no extra
`tokenizer-verification`. Uso retornado em chamadas reais é a referência efetiva.

## Geração, correção e execução

1. A pergunta textual é normalizada e validada (1–2000 caracteres).
2. O catálogo respeita a role configurada, sem superuser/BYPASSRLS.
3. A geração usa contexto limitado e aplica `SqlPolicyValidator`.
4. Uma proposta permitida fica em memória por dez minutos, vinculada à SQL exata,
   conexão, sessão e pergunta. Nova pergunta/cancelamento invalida a anterior.
5. A CLI mostra SQL e destino e exige `sim`/`s`; vazio, negativa, EOF e interrupção
   não confirmam. `approved` da política não equivale a confirmação humana.
6. `ExecuteSqlUseCase` revalida e consome atomicamente a proposta antes do banco.
   Erro posterior também consome o ID, sem execução duplicada ou retry oculto.
7. O executor usa transação read-only, timeout de 30 s, lock timeout de 5 s e
   `search_path=pg_catalog,public`; RLS e privilégios continuam valendo.
8. Um cursor de servidor busca no máximo `max_rows+1`, apresenta até o limite e
   indica truncamento. A SQL confirmada não é reescrita. Recursos são liberados
   com rollback/fechamento também em erro ou cancelamento.

A política admite SELECT simples, filtros, JOIN, agrupamento, ordenação, DISTINCT,
LIMIT/OFFSET e COUNT, SUM, AVG, MIN, MAX, LOWER, UPPER, COALESCE. Para períodos,
admite CURRENT_DATE e EXTRACT de mês ou ano de uma coluna ou de CURRENT_DATE. Escrita, DDL,
comandos múltiplos, INTO, locks, catálogos de sistema, funções desconhecidas,
CTEs, subconsultas e UNION continuam bloqueados.

Há até três chamadas totais de geração por pergunta, incluindo correções após
execução. SQL malformada, resposta final inválida, conversão para texto ou inteiro
em um SELECT compatível e erros elegíveis de sintaxe/resolução permitem correção.
A conversão permanece bloqueada e a nova proposta deve removê-la. Uma nova SQL recebe novo ID, nova validação
e nova confirmação. Bloqueio de segurança, autenticação, cota, permissão,
indisponibilidade, timeout ou resultado incerto não causam outra chamada automática.
Feedback de erro usa categorias fixas, sem mensagens/valores brutos do servidor.

Isso não comprova interpretação de negócio, custo baixo ou segurança para todo
PostgreSQL arbitrário. O limite de linhas não limita todo processamento nem o
tamanho de um valor isolado. Política, identidade restrita, RLS e limites são
camadas complementares.

## CLI e API

```powershell
backend/.venv/Scripts/python.exe -m askdb.entrypoints.cli
backend/.venv/Scripts/python.exe -m askdb.entrypoints.api
```

A CLI não depende do servidor HTTP. Cada pergunta pode usar pares anteriores da
sessão, nunca os resultados. `sair`, EOF ou Ctrl+C encerram e invalidam pendências.

A API escuta `127.0.0.1:8000`, oferece Swagger em `http://127.0.0.1:8000/docs` e
`GET /health` sem consultar dependências. `POST /queries/generate` continua
aceitando somente `{"question":"Quais são os cinco produtos mais vendidos?"}`.
A resposta preserva `sql` e `validation.status/reasons` e acrescenta metadados de
proposta. Cada requisição é independente. A API não possui endpoint de execução,
nem CORS amplo ou recepção de chaves no corpo HTTP.

Erros usam `{"error":{"code":"...","message":"..."}}`: 422 para entrada/contexto
excessivo, 503 para configuração/banco/contexto/provedor indisponível (incluindo
chave/cota remota), 504 para timeout LLM, 502 para resposta inválida ou limite de
tentativas e 500 para inesperados. As categorias `query_*` descrevem erros da
execução CLI. Eventos JSON de `askdb` contêm fase, categoria, duração e tentativas,
sem perguntas, SQLs completas, resultados ou credenciais.

## Classes e organização

O diagrama implementado está no [README principal](../README.md) e em
[assets/diagrama-classes.mmd](../assets/diagrama-classes.mmd). Ele mantém a linha
conceitual do apêndice de `docs/relatorio-tecnico`; `InferencePort` é um nome
antigo substituído por `LLMClientPort`. A organização segue a arquitetura
hexagonal pragmática, com os casos de uso em `queries/` e contratos nas
fronteiras com o PostgreSQL, a IA e os arquivos de contexto.

Os adaptadores de entrada ficam em `entrypoints/`. A API está em `api.py`.
O pacote `cli/` agrupa o comando em `__main__.py`, a interação e as sessões em
`app.py`, a formatação Rich em `terminal.py` e o catálogo da demo em `demo.py`.
O script `backend/demo/prepare.py` cuida do Compose e instala os contextos de
exemplo.

| Tipos | Responsabilidade |
|---|---|
| `GenerateSqlUseCase`, `SqlPolicyValidator` | Gerar/corrigir e validar, sem executar |
| `ExecuteSqlUseCase`, `PendingSqlRegistry`, `ReadOnlyQueryPort` | Confirmação, revalidação e execução única |
| `SchemaCatalogPort`, `PostgresDatabaseAdapter` | Descoberta autorizada e execução PostgreSQL restrita |
| `LLMClientPort`, `OllamaLLMClientAdapter`, `DeepSeekLLMClientAdapter`, `OpenAILLMClientAdapter` | Contrato comum e integrações de IA |
| `ContextBuilder`, `TokenBudgetPolicy`, `KnowledgeFilePort`, `MarkdownKnowledgeAdapter` | Contexto completo por conexão e orçamento |
| `DataModel`, `SqlGenerationRequest`, `SqlProposal`, `ValidationResult`, `ValidationReason` | Dados/validação do fluxo |
| `DBConnection`, `LLMProfile`, `LLMContext`, `LLMResponse` | Identidade e comunicação sem chave no perfil |
| `SessionContext`, `SqlGenerationState`, `ExecuteSqlRequest`, `QueryResult` | Memória, tentativas, confirmação e resultado |
| `SchemaCatalog`, `Table`, `Column`, `ForeignKey` | Metadados técnicos autorizados |
| `Settings`, `ApplicationError` | Configuração e falhas controladas |

`bootstrap.build_use_case()` compõe a geração; `build_cli_session()` compartilha
registro/conexão entre geração e executor. Os modelos não viram automaticamente
tabelas SQLite. Desktop, entrevista completa, cofre, SQLite, Control Plane,
amostras e histórico persistente continuam fora desta V0.

## Verificação reproduzível

```powershell
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py --real-provider ollama
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py --real-provider deepseek
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py --demo-provider deepseek
```

O primeiro roteiro executa testes determinísticos e PostgreSQL real, sem chave
nem inferência. `--real-provider` executa a prova automatizada opt-in com duas
perguntas, uma confirmação, um cancelamento e uma geração pela API; exige serviço/chave runtime.
`--demo-provider` abre a CLI para interação manual no ambiente sintético.

Cada execução cria projeto Docker de nome aleatório, porta livre, senhas efêmeras,
volume exclusivo e pasta temporária de app; ao terminar remove somente os recursos
que criou. Não reutiliza nem apaga bancos/volumes preexistentes. Saídas capturadas
pelo roteiro são sanitizadas. Os testes reais são distintos dos simulados; ausência
de chave não é prova real concluída. Veja o registro de evidências para o estado atual.
