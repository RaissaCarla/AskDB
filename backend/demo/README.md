# Preparar a demo da V0 no Windows

A demo usa três bancos PostgreSQL fictícios no mesmo projeto Docker Compose. Cada conexão tem seu contexto local. O [roteiro para a banca](roteiro-demo-v0.md) reúne a sequência da apresentação e o gabarito.

Para montar o ambiente etapa por etapa e explicar como os módulos se comunicam, siga o [manual de infraestrutura da V0](manual-infra-v0.md).

## 1. Requisitos

- Uma cópia completa do AskDB na revisão que contém `backend/demo/`. Clone essa revisão ou use um ZIP dos arquivos do projeto.
- Python 3.11, com o iniciador `py` disponível. [Instalação do Python no Windows](https://www.python.org/downloads/windows/)
- Docker Desktop aberto com contêineres Linux e Docker Compose v2. [Instalação do Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
- Para apresentar com DeepSeek, conexão à internet e uma chave válida. Tenha a chave à mão para a entrada oculta.

## 2. Instalar e configurar

No PowerShell, abra a raiz da cópia do projeto.

```powershell
py -3.11 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -e ./backend
```

Se `backend/.env` estiver ausente, copie o modelo.

```powershell
Copy-Item backend/.env.example backend/.env
```

As senhas fictícias do modelo servem para a demo. `ASKDB_DEMO_POSTGRES_PORT` define a porta no notebook, por padrão `5434`. O modo demo monta as três conexões de leitura a partir dessa porta e de `ASKDB_READER_PASSWORD`. A chave externa é fornecida na CLI ou no ambiente do processo.

## 3. Abrir e ensaiar

```powershell
& .\backend\.venv\Scripts\python.exe .\backend\demo\prepare.py
```

A preparação sobe o PostgreSQL, verifica se a conta de leitura enxerga as três tabelas esperadas de cada banco e prepara os contextos. Em um volume novo, o PostgreSQL carrega um SQL completo por cenário a partir de `init/casos/`. Escolha DeepSeek, informe a chave e selecione Vendas, Suporte ou Estoque. Confira o contexto indicado na sessão e confirme a execução com `sim` depois de ler a SQL e o destino. No prompt da pergunta, use `trocar` para voltar à lista de conexões ou `sair` para fechar a CLI.

Para conferir a infraestrutura ou editar os contextos antes de abrir a CLI, use `prepare.py --prepare-only` com o mesmo Python. O comando mostra o caminho de cada contexto. Os arquivos ficam em `%LOCALAPPDATA%\AskDB\demo\connections\<id>\context.md` por padrão. A preparação atualiza as cópias intactas dos modelos iniciais e preserva as edições locais. De outra pasta, use os caminhos completos para o Python da cópia e para `prepare.py`, ambos entre aspas.

## 4. Encerrar

```powershell
& .\backend\.venv\Scripts\python.exe .\backend\demo\prepare.py --stop
```

O próximo ensaio reaproveita o volume do projeto `askdb-demo-v0`.

## Se a preparação falhar

| Sintoma                                                           | O que fazer                                                                                                                                                                                                                              |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docker indisponível                                               | Abra o Docker Desktop, aguarde o motor Linux e repita o comando.                                                                                                                                                                         |
| Porta ocupada                                                     | Altere `ASKDB_DEMO_POSTGRES_PORT` em `backend/.env` e repita. A nova porta cria outras identidades de contexto.                                                                                                                          |
| Senha alterada após a primeira carga                              | Restaure em `backend/.env` a senha usada na criação do volume.                                                                                                                                                                           |
| Tabelas ausentes ou sem acesso de leitura (`demo_schema_missing`) | Confira as permissões e os logs de inicialização. Se o volume for da primeira edição da demo, [suba a carga atual em um projeto separado](manual-infra-v0.md#carregar-os-cenários-em-um-volume-separado) para conservar o volume antigo. |

```powershell
docker compose --project-name askdb-demo-v0 --env-file backend/.env -f backend/demo/compose.yaml logs --tail 60 postgres
```
