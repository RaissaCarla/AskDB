# Manual de infraestrutura do AskDB V0 no Windows

Este guia monta o ambiente pelo PowerShell e pelo PostgreSQL, etapa por etapa. Comece pelo modo normal com um banco. Para reproduzir o seletor de Vendas, Suporte e Estoque, siga [Montar os três bancos da demo](#montar-os-três-bancos-da-demo). Use dados fictícios nos ensaios da banca.

## 1. Instalar as dependências

| Componente                               | Para que serve                                                                                                                                                                           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.11 com o comando `py`           | Executar a CLI, a API e os adaptadores. O ambiente virtual isola as dependências do AskDB. [Python para Windows](https://www.python.org/downloads/windows/)                              |
| PostgreSQL 16 e cliente `psql`           | Hospedar os dados e criar o usuário de leitura. Anote a porta e a senha administrativa definidas na instalação. [PostgreSQL para Windows](https://www.postgresql.org/download/windows/)  |
| Ollama **ou** uma conta com chave de API | Gerar SQL com um modelo local ou remoto. Escolha o caminho na etapa 5.                                                                                                                   |
| Docker Desktop com Compose v2            | Opcional. Use se preferir rodar o PostgreSQL de desenvolvimento ou o da demo em contêiner. [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/) |

Em uma cópia do projeto que inclui `backend/demo/`, abra o PowerShell na raiz e rode:

```powershell
py -3.11 -m venv backend/.venv
$python = Join-Path (Get-Location).Path 'backend\.venv\Scripts\python.exe'
& $python -m pip install -e ./backend
```

Os exemplos usam `psql` no `PATH` e a porta `5432` da instância local. Se o terminal não encontrar o comando, substitua `psql` por `& 'C:\Program Files\PostgreSQL\16\bin\psql.exe'`, ajustando o caminho à sua instalação.

## 2. Criar um banco e seu usuário de leitura

Abra o cliente como administrador. Essa conta cria a estrutura e concede acesso.

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -W
```

No `psql`, crie a role uma vez por instância e informe a senha de leitura quando `\password` pedir. Se `askdb_reader` já existir para os bancos da demo, reutilize a role e sua senha. A conta que o AskDB usa precisa de login, permissão para conectar ao banco, acesso ao esquema e `SELECT` nos objetos autorizados. [CREATE ROLE no PostgreSQL](https://www.postgresql.org/docs/16/sql-createrole.html), [GRANT no PostgreSQL](https://www.postgresql.org/docs/16/sql-grant.html)

```sql
CREATE ROLE askdb_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
\password askdb_reader

CREATE DATABASE askdb_manual;
\connect askdb_manual

CREATE TABLE public.pedidos (
    id integer PRIMARY KEY,
    status text NOT NULL,
    valor_total numeric(10, 2) NOT NULL
);

INSERT INTO public.pedidos VALUES
    (1, 'PAGO', 120.00),
    (2, 'PAGO', 80.00),
    (3, 'PENDENTE', 70.00);

REVOKE ALL ON DATABASE askdb_manual FROM PUBLIC;
GRANT CONNECT ON DATABASE askdb_manual TO askdb_reader;
GRANT USAGE ON SCHEMA public TO askdb_reader;
GRANT SELECT ON TABLE public.pedidos TO askdb_reader;
\quit
```

O exemplo usa um banco novo e dedicado. Em um banco existente, peça ao administrador que autorize as tabelas ou colunas que o AskDB pode ler. A role deve ficar sem propriedade das tabelas, permissões de escrita e papéis que concedam privilégios adicionais. O adaptador rejeita superusuário e roles com `BYPASSRLS`. Se houver políticas de acesso por linha (RLS), o PostgreSQL as aplica à consulta.

Valide com a própria conta de leitura, pela porta que o aplicativo vai usar.

```powershell
psql -h 127.0.0.1 -p 5432 -U askdb_reader -d askdb_manual -W
```

```sql
SELECT current_user, current_database();
SELECT id, status, valor_total FROM public.pedidos ORDER BY id;
SELECT has_table_privilege('public.pedidos', 'SELECT') AS pode_ler,
       has_table_privilege('public.pedidos', 'INSERT,UPDATE,DELETE,TRUNCATE') AS pode_escrever;
\quit
```

Você deve ver `askdb_reader`, `askdb_manual`, três linhas de exemplo e `pode_ler = t`, `pode_escrever = f`.

## 3. Configurar a conexão no AskDB

Crie `backend/.env` em UTF-8. Use [`.env.example`](../.env.example) como referência ou comece com os valores abaixo. Se já tiver um `.env`, edite apenas os campos necessários.

```dotenv
DATABASE_URL=postgresql://askdb_reader:SENHA_NA_URI@127.0.0.1:5432/askdb_manual
LLM_PROVIDER=ollama
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
```

Substitua `SENHA_NA_URI` pela senha da role de leitura. Na URL, use codificação percentual para caracteres reservados, como `@` → `%40` e `#` → `%23`. No prompt de senha do `psql`, informe a senha original. `DATABASE_URL` reúne usuário, senha, host, porta e nome do banco. No modo normal, use na URL o nome da role de leitura que você criou. A aplicação lê o arquivo pelo caminho do backend mesmo se você abrir a CLI de outra pasta. Variáveis do processo PowerShell têm precedência sobre as do arquivo. [URIs de conexão do PostgreSQL](https://www.postgresql.org/docs/16/libpq-connect.html#LIBPQ-CONNSTRING-URIS)

## 4. Criar o contexto local da conexão

No PowerShell, consulte o caminho calculado pelo próprio AskDB e crie manualmente a pasta.

```powershell
$contextPath = & $python -X utf8 -c "from askdb.settings import Settings; s = Settings.from_env(); print(s.app_data_dir / 'connections' / s.connection.id / 'context.md')"
New-Item -ItemType Directory -Path (Split-Path -Parent $contextPath) -Force | Out-Null
notepad $contextPath
```

Salve o arquivo como `context.md` em UTF-8. Use uma regra que represente o significado dos dados para o usuário.

```markdown
# Vendas de exemplo

- Use a tabela public.pedidos. O valor em reais está em valor_total.
- Faturamento reconhecido é a soma de valor_total dos pedidos com status PAGO.
- Exclua pedidos pendentes do faturamento reconhecido.
```

Por padrão, o caminho é `%LOCALAPPDATA%\AskDB\connections\<id>\context.md`. O identificador deriva de host, porta, banco e usuário PostgreSQL. Por isso, trocar `127.0.0.1` por `localhost`, mudar a porta ou usar outra role seleciona outro arquivo. A senha fica fora do identificador. Para escolher outra raiz local, defina `ASKDB_APP_DATA_DIR` com caminho absoluto antes de calcular o caminho.

O arquivo é lido novamente a cada geração. No modo normal, a CLI avisa se ainda não houver arquivo e permite perguntar com contexto de negócio vazio. No modo `--demo`, cada conexão precisa de um `context.md` preenchido para abrir a sessão.

## 5. Preparar o modelo de linguagem

### Ollama local

Instale e abra o Ollama no Windows. No PowerShell, baixe o modelo e confira se o serviço o disponibiliza. [Ollama no Windows](https://docs.ollama.com/windows), [Consulta aos modelos disponíveis](https://docs.ollama.com/api/tags)

```powershell
ollama pull qwen3.5:9b
ollama list
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models | Select-Object name
```

Use `LLM_PROVIDER=ollama` como padrão no `.env` ou selecione **Ollama** no menu da CLI. Com o serviço disponível, o AskDB envia as mensagens para `OLLAMA_URL` e pede o modelo de `OLLAMA_MODEL`. A inferência roda no processo do Ollama e a SQL volta para a aplicação. A chave é dispensada nesse perfil. A instalação do Ollama, o serviço em execução e o download do modelo são etapas da preparação do PC.

### DeepSeek ou OpenAI com chave de API

Para o caminho remoto, tenha acesso à internet e uma chave válida com acesso ao modelo. Selecione **DeepSeek** ou **OpenAI** no menu. Os perfis atuais usam `deepseek-flash` e `gpt-4.1-mini`, respectivamente. A CLI pede a chave com entrada oculta caso a variável do provedor não exista no processo. Você pode escolher o provedor padrão em `LLM_PROVIDER` e continuar fornecendo a chave só na abertura da CLI.

Como alternativa à entrada na CLI, carregue a chave na sessão do PowerShell. Esse caminho também serve para a API HTTP, que depende da variável do processo para autenticação remota.

```powershell
$env:DEEPSEEK_API_KEY = [Net.NetworkCredential]::new('', (Read-Host 'Chave DeepSeek' -AsSecureString)).Password
```

Para OpenAI, use `OPENAI_API_KEY`. O AskDB lê essas variáveis do processo em execução. Mantenha a chave fora de `backend/.env`, de `context.md` e do Git. A autenticação usa a chave do provedor, e a conexão PostgreSQL mantém sua própria senha.

## 6. Abrir e verificar

### CLI para consultar e executar

```powershell
& $python -X utf8 -m askdb.entrypoints.cli
```

Escolha o modelo. Pergunte **«Qual é o faturamento reconhecido?»** para usar a regra do exemplo. Confira na SQL o filtro por `PAGO` e leia o destino da execução. Digite `sim` para confirmar. O resultado esperado é **R$ 200,00**. Digite `sair` para encerrar.

### API HTTP para gerar e validar SQL

A CLI funciona de forma independente da API. Para testar o HTTP, abra outro PowerShell na raiz do projeto. Ajuste `LLM_PROVIDER` em `backend/.env` para o provedor que o servidor deve usar. Se escolher um provedor remoto, defina a variável da chave nesse mesmo terminal antes de subir o processo.

```powershell
& .\backend\.venv\Scripts\python.exe -m askdb.entrypoints.api
```

Abra `http://127.0.0.1:8000/docs` e execute `POST /queries/generate` com este corpo:

```json
{ "question": "Qual é o faturamento reconhecido?" }
```

Inspecione `sql` e `validation` na resposta. O contrato HTTP termina na geração e validação. A confirmação humana e a execução são feitas pela CLI. `http://127.0.0.1:8000/health` confirma que o processo responde. Use a geração para verificar também a comunicação com o banco e o provedor.

## Montar os três bancos da demo

O modo `--demo` espera os bancos `demo_vendas`, `demo_suporte` e `demo_estoque` em `127.0.0.1`, na mesma porta, com a role `askdb_reader`. Há dois jeitos de preparar o PostgreSQL.

### Criar os bancos e carregar os dados à mão

1. No PowerShell, na raiz do projeto, abra `psql` como administrador. Crie `askdb_reader` conforme a etapa 2 caso a role ainda não exista.
2. Crie os três bancos vazios:

    ```sql
    CREATE DATABASE demo_vendas;
    CREATE DATABASE demo_suporte;
    CREATE DATABASE demo_estoque;
    ```

3. Ainda no `psql`, escolha cada banco novo e aplique o SQL completo do cenário em `init/casos/`. O bloco abaixo mostra Vendas. Repita o bloco trocando `vendas` por `suporte` e por `estoque`:

    ```sql
    \set ON_ERROR_STOP on
    \connect demo_vendas
    BEGIN;
    \i backend/demo/init/casos/vendas.sql
    REVOKE ALL ON DATABASE demo_vendas FROM PUBLIC;
    GRANT CONNECT ON DATABASE demo_vendas TO askdb_reader;
    GRANT USAGE ON SCHEMA public TO askdb_reader;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO askdb_reader;
    COMMIT;
    ```

4. Teste o login de leitura em cada destino conforme a etapa 2. No `psql`, `\dt public.*` deve listar três tabelas por banco.
5. No `backend/.env`, ajuste `ASKDB_DEMO_POSTGRES_PORT` para a porta da instância que recebeu os três bancos e `ASKDB_READER_PASSWORD` para a senha original da role de leitura. Nesse modo, o AskDB monta as URLs das três conexões a partir desses valores e do catálogo fixo. Para apontar a API para um desses bancos, configure `DATABASE_URL` explicitamente e prepare o contexto do modo normal.

### Subir o PostgreSQL de demonstração pelo Compose

Esta é a alternativa a criar os bancos, a role e os dados manualmente. Abra o Docker Desktop e defina `ASKDB_ADMIN_PASSWORD`, `ASKDB_READER_PASSWORD` e `ASKDB_DEMO_POSTGRES_PORT` no mesmo `backend/.env`. A porta padrão publicada é `5434`. Rode os comandos abaixo na raiz:

```powershell
docker compose --env-file backend/.env -f backend/demo/compose.yaml up -d --wait
docker compose --env-file backend/.env -f backend/demo/compose.yaml ps
```

Em um volume novo, o PostgreSQL roda os arquivos de inicialização e provisiona os três cenários completos. Em um volume existente, ele reutiliza o esquema, os dados e as senhas da primeira carga. Para encerrar o contêiner e manter os dados, use o mesmo comando Compose com `stop`. [Variáveis no Docker Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)

### Carregar os cenários em um volume separado

Se o volume antigo contém a primeira edição da demo, crie outro projeto Compose com uma porta livre. Assim você pode usar a carga atual e preservar o volume antigo. No PowerShell, este exemplo usa a porta `15434`:

```powershell
$env:ASKDB_DEMO_POSTGRES_PORT = '15434'
docker compose --project-name askdb-demo-v0-novo --env-file backend/.env -f backend/demo/compose.yaml up -d --wait
```

Crie os contextos para a nova porta e abra a CLI na mesma sessão do PowerShell conforme a próxima seção. Para parar o projeto separado, mantenha os mesmos parâmetros do Compose e troque `up -d --wait` por `stop`.

### Colocar os três contextos e abrir a CLI

Com os bancos de qualquer um dos dois caminhos disponíveis, obtenha os três caminhos locais sem imprimir credenciais:

```powershell
@'
from askdb.entrypoints.cli.demo import demo_connections
from askdb.settings import read_environment

for case in demo_connections(read_environment()):
    settings = case.settings
    path = settings.app_data_dir / "connections" / settings.connection.id / "context.md"
    print(case.name, path, sep=" | ")
'@ | & $python -X utf8 -
```

Para cada caminho listado, crie a pasta e salve o Markdown correspondente de [`contexts/`](contexts/). Por padrão, esses arquivos ficam em `%LOCALAPPDATA%\AskDB\demo\connections\<id>\context.md`. Por exemplo, para Vendas, substitua `CAMINHO_DO_CONTEXT_DE_VENDAS` pelo caminho absoluto completo mostrado no comando anterior. Se o destino já existir, abra o arquivo para comparar e faça apenas as alterações desejadas.

```powershell
$contextPath = 'CAMINHO_DO_CONTEXT_DE_VENDAS'
New-Item -ItemType Directory -Path (Split-Path -Parent $contextPath) -Force | Out-Null
if (-not (Test-Path -LiteralPath $contextPath)) {
    Copy-Item backend/demo/contexts/demo_vendas.md -Destination $contextPath
}
```

Repita com `demo_suporte.md` e `demo_estoque.md`, cada um no seu destino. Abra a CLI, selecione o provedor e escolha uma conexão.

```powershell
& $python -X utf8 -m askdb.entrypoints.cli --demo
```

Use `trocar` no prompt da pergunta. A CLI mantém o modelo selecionado e abre uma sessão nova para a outra conexão. Siga as perguntas e os resultados esperados no [roteiro da banca](./roteiro-demo-v0.md).

## Referência das variáveis de ambiente

| Variável                                   | Quem usa e valor de referência                                                                                                                                   |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                             | CLI normal e API. URI PostgreSQL com a role de leitura.                                                                                                          |
| `ASKDB_ADMIN_PASSWORD`                     | Docker Compose. Define a senha do administrador na inicialização. A preparação usa o administrador do contêiner para criar ou atualizar a infraestrutura.        |
| `ASKDB_READER_PASSWORD`                    | Inicialização do Compose e modo `--demo`. Em um banco montado à mão, use a senha que você já definiu na role.                                                    |
| `ASKDB_POSTGRES_PORT`                      | Porta publicada pelo Compose de desenvolvimento `backend/compose.yaml`. Padrão `5433`. Se usar esse Compose, ajuste `DATABASE_URL` à porta publicada.            |
| `ASKDB_DEMO_POSTGRES_PORT`                 | Porta publicada pelo Compose da demo e usada pelo seletor. Padrão `5434`. Se montou o banco fora do Compose, informe a porta real da instância.                  |
| `ASKDB_APP_DATA_DIR`                       | Raiz dos arquivos do aplicativo. Padrão `%LOCALAPPDATA%\AskDB`. Aceita um caminho absoluto e o modo demo acrescenta a subpasta `demo`.                           |
| `LLM_PROVIDER`                             | Perfil padrão da CLI e perfil da API. `ollama` por padrão. Também aceita `deepseek` e `openai`.                                                                  |
| `OLLAMA_URL`, `OLLAMA_MODEL`               | Endereço e modelo local. Padrões `http://127.0.0.1:11434` e `qwen3.5:9b`.                                                                                        |
| `LLM_MODEL`                                | Substitui o modelo do provedor definido em `LLM_PROVIDER`. O orçamento de contexto exige um perfil de modelo suportado.                                          |
| `LLM_TIMEOUT`, `CONNECT_TIMEOUT`           | Limites de chamada e conexão do provedor de IA. Padrões de 120 s e 5 s.                                                                                          |
| `LLM_CONTEXT_WINDOW`, `LLM_OUTPUT_RESERVE` | Janela configurada e reserva da saída. Padrões de 16384 e 2048 tokens. Se o conteúdo exceder o orçamento, o AskDB informa o erro para permitir ajuste explícito. |
| `ASKDB_MAX_ROWS`                           | Limite de linhas exibidas por execução. Padrão `100`, de `1` a `1000`.                                                                                           |
| `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`       | Autenticação do provedor remoto. Forneça no ambiente do processo ou na entrada oculta da CLI.                                                                    |

## O que explicar à banca

```mermaid
flowchart LR
    U["Pessoa faz uma pergunta"] --> C["AskDB monta o contexto"]
    P["Esquema autorizado no PostgreSQL"] --> C
    M["context.md da conexão"] --> C
    C --> L["Ollama local ou API de IA"]
    L --> V["AskDB valida a SQL"]
    V -->|aprovada| H["Pessoa confere SQL e destino"]
    H -->|sim| D["PostgreSQL executa em transação de leitura"]
    D --> R["CLI mostra o resultado"]
```

1. **Três responsabilidades.** A pessoa faz a pergunta e confirma a execução. A role PostgreSQL limita os dados que a aplicação pode consultar. A chave de API, quando usada, autentica apenas a chamada de IA.
2. **Interpretação em duas etapas.** `Settings` resolve a infraestrutura. O adaptador PostgreSQL descobre tabelas, colunas e relações visíveis à role. O `ContextBuilder` reúne o esquema, as regras do Markdown, a pergunta e os pares de pergunta e SQL da sessão. O modelo interpreta esse conteúdo para propor a consulta. Com Ollama, a inferência roda no PC. Com um provedor remoto, esse conteúdo vai à API. As linhas retornadas pelo banco ficam locais.
3. **Validação e controle de execução.** A política de SQL verifica a proposta e a CLI mostra a consulta exata e o destino. `sim` autoriza uma execução em transação de leitura, sujeita às permissões, ao timeout e ao limite de linhas do aplicativo.
4. **Separação entre bancos.** Cada conexão resolve um Markdown próprio, que permanece em disco. O histórico e as propostas ficam em memória nesta V0. `trocar` cria outra sessão com o contexto da conexão escolhida e reinicia o histórico. A demo representa alguém que já cadastrou as conexões. O cadastro e o onboarding da futura interface ficam para a próxima etapa.
