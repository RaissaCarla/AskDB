# AskDB

**Consulte bancos de dados PostgreSQL usando linguagem natural.**

Projeto de Trabalho de Conclusão de Curso (TCC) em Análise e Desenvolvimento de
Sistemas — Instituto Federal de São Paulo (IFSP), Câmpus Guarulhos.

## Estado do desenvolvimento

O backend da V0 está em implementação/verificação na branch `marco-2-v0`, partindo
de `marco-1-20-pct`. Oferece CLI com contexto de negócio por conexão, geração e
validação de SQL, confirmação explícita e execução restrita com saída tabular.
A API FastAPI mantém geração/validação e Swagger, sem endpoint de execução.

DeepSeek BYOK é a integração remota prioritária; Ollama e OpenAI usam o mesmo
contrato. As provas reais e simuladas, pendências e limites estão em
[backend/evidencias-v0.md](backend/evidencias-v0.md). Disponibilidade de um
adaptador não significa que uma chamada real com chave já tenha sido validada.

Veja [as instruções do backend](backend/README.md) para instalação, configuração,
pasta local, seleção de provedor, CLI, Swagger e testes reproduzíveis.

## Fluxo da V0

Pergunta → esquema autorizado + contexto da conexão → geração → validação →
apresentação da SQL e destino → confirmação explícita → revalidação → execução
PostgreSQL somente leitura → resultado tabular local.

- Um `context.md` por conexão em `%LOCALAPPDATA%\AskDB\connections\<id>\context.md`.
- Até três tentativas totais por pergunta, sem correção para contornar bloqueios.
- Chave do provedor em tempo de execução, sem gravação pela aplicação.
- Timeout de 30 segundos e limite de resultado, com respeito à role e ao RLS.
- Resultados não são reenviados ao modelo nem usados como memória.

O projeto usa Python 3.11+, FastAPI, Pydantic, SQLGlot, psycopg, httpx e pytest,
com PostgreSQL sintético reproduzível por Docker Compose. O núcleo não depende
de um fornecedor de IA nem de uma interface gráfica.

## Evolução prevista

A V1 é o MVP desktop com Electron/React/TypeScript/Vite, SQLite dedicado a
configurações e conversas, entrevista para conhecimento validado por conexão,
proteção opcional de segredos e Control Plane básico. O SQLite referenciará o
arquivo Markdown por conexão; o texto de negócio continuará no arquivo.
V2 e V3 são possibilidades posteriores de explicação e visualização.

As definições OpenSpec são mantidas localmente e ignoradas pelo Git. A documentação
acadêmica está na branch `docs/relatorio-tecnico`; sua modelagem conceitual orienta
responsabilidades e não exige replicar todas as assinaturas do código.

## Diagrama de classes do backend V0

O arquivo editável está em [assets/diagrama-classes.mmd](assets/diagrama-classes.mmd).
O diagrama abaixo representa os tipos implementados, incluindo interfaces e
modelos de dados. Classes de frameworks e funções auxiliares foram resumidas.

```mermaid
classDiagram
    direction LR
    class GenerateSqlUseCase {
        +execute(SqlGenerationRequest) SqlProposal
        +correct(SqlProposal, ApplicationError) SqlProposal
    }
    class ContextBuilder {
        +build(connection_id, question, session) LLMContext
    }
    class TokenBudgetPolicy {
        +validate(memory, context) LLMContext
    }
    class ExecuteSqlUseCase {
        +execute(ExecuteSqlRequest) QueryResult
    }
    class PendingSqlRegistry {
        +register(SqlProposal) str
        +get(id, connection_id, session_id) SqlProposal
        +consume(id, connection_id, session_id) SqlProposal
        +invalidate_session(session_id)
    }
    class LLMClientPort {
        <<Protocol>>
        +generate(LLMContext) LLMResponse
    }
    class SchemaCatalogPort {
        <<Protocol>>
        +discover() SchemaCatalog
    }
    class ReadOnlyQueryPort {
        <<Protocol>>
        +execute(connection_id, sql) QueryResult
    }
    class KnowledgeFilePort {
        <<Protocol>>
        +read(connection_id) str
    }
    class SqlPolicyValidator {
        +validate(sql) ValidationResult
    }
    class MarkdownKnowledgeAdapter {
        +prepare(connection_id) Path
        +path(connection_id) Path
        +read(connection_id) str
    }
    class PostgresDatabaseAdapter {
        +discover() SchemaCatalog
        +execute(connection_id, sql) QueryResult
    }
    class OllamaLLMClientAdapter
    class DeepSeekLLMClientAdapter
    class OpenAILLMClientAdapter
    class DBConnection {
        +host
        +port
        +database
        +role
        +id
    }
    class LLMProfile {
        +provider
        +endpoint
        +model
        +context_window
        +output_reserve
    }
    class LLMContext {
        +messages
        +input_tokens_estimate
        +memory_tokens_estimate
    }
    class LLMResponse {
        +sql
        +input_tokens
        +output_tokens
    }
    class SessionContext {
        +connection_id
        +question_sql_pairs
        +active_question
        +reset(connection_id)
    }
    class SqlGenerationState {
        +question
        +attempts
        +terminal
    }
    class ExecuteSqlRequest {
        +proposal_id
        +connection_id
        +session_id
        +confirmed
    }
    class QueryResult {
        +columns
        +rows
        +duration_ms
        +truncated
    }
    class SqlGenerationRequest {
        +question
    }
    class SqlProposal {
        +id
        +sql
        +validation
        +connection_id
        +session_id
        +question_id
        +attempt
    }
    class DataModel {
        <<Pydantic>>
    }
    class ValidationResult {
        +status
        +reasons
    }
    class ValidationReason
    class SchemaCatalog
    class Table
    class Column
    class ForeignKey
    class Settings {
        +app_data_dir
        +max_rows
        +connection
        +profile() LLMProfile
    }
    class ApplicationError
    GenerateSqlUseCase --> ContextBuilder
    GenerateSqlUseCase --> LLMClientPort
    GenerateSqlUseCase --> SqlPolicyValidator
    GenerateSqlUseCase --> PendingSqlRegistry
    GenerateSqlUseCase --> SessionContext
    GenerateSqlUseCase ..> SqlGenerationRequest
    GenerateSqlUseCase ..> SqlProposal
    ContextBuilder --> SchemaCatalogPort
    ContextBuilder --> KnowledgeFilePort
    ContextBuilder --> TokenBudgetPolicy
    ContextBuilder ..> LLMContext
    TokenBudgetPolicy --> LLMProfile
    ExecuteSqlUseCase --> PendingSqlRegistry
    ExecuteSqlUseCase --> SqlPolicyValidator
    ExecuteSqlUseCase --> ReadOnlyQueryPort
    ExecuteSqlUseCase ..> ExecuteSqlRequest
    ExecuteSqlUseCase ..> QueryResult
    PendingSqlRegistry o-- SqlProposal
    SchemaCatalogPort <|.. PostgresDatabaseAdapter
    ReadOnlyQueryPort <|.. PostgresDatabaseAdapter
    KnowledgeFilePort <|.. MarkdownKnowledgeAdapter
    LLMClientPort <|.. OllamaLLMClientAdapter
    LLMClientPort <|.. DeepSeekLLMClientAdapter
    LLMClientPort <|.. OpenAILLMClientAdapter
    DeepSeekLLMClientAdapter --> LLMProfile
    OpenAILLMClientAdapter --> LLMProfile
    OllamaLLMClientAdapter --> Settings
    SessionContext --> SqlGenerationState
    SessionContext ..> DBConnection
    SqlProposal --> ValidationResult
    ValidationResult o-- ValidationReason
    SchemaCatalog o-- Table
    Table o-- Column
    Table o-- ForeignKey
    Settings ..> DBConnection
    Settings ..> LLMProfile
    GenerateSqlUseCase ..> ApplicationError
    DataModel <|-- DBConnection
    DataModel <|-- LLMProfile
    DataModel <|-- LLMContext
    DataModel <|-- LLMResponse
    DataModel <|-- SessionContext
    DataModel <|-- SqlGenerationState
    DataModel <|-- ExecuteSqlRequest
    DataModel <|-- QueryResult
    DataModel <|-- SqlGenerationRequest
    DataModel <|-- SqlProposal
    DataModel <|-- ValidationResult
    DataModel <|-- ValidationReason
    DataModel <|-- SchemaCatalog
    DataModel <|-- Table
    DataModel <|-- Column
    DataModel <|-- ForeignKey
    note for GenerateSqlUseCase "Somente gera e valida; nao executa SQL."
    note for ExecuteSqlUseCase "Confirmacao da SQL exata; consumo atomico antes do banco."
    note for SessionContext "Somente perguntas e SQLs; sem resultados."
    note for Settings "Dados locais em LOCALAPPDATA/AskDB; perfis sem chave."
```
