# Evidências de implementação e verificação da V0

Branch: `marco-2-v0`, a partir de `marco-1-20-pct` (`906f64d`).
Este registro distingue comportamento implementado, testes simulados e chamadas
reais. Não representa garantia de correção geral das consultas nem de produção.

## Situação da entrega

O código da V0 está implementado: contexto por conexão em pasta dedicada,
orçamento, perfis Ollama/DeepSeek/OpenAI, geração/correção limitada, registro
temporário, confirmação explícita e execução PostgreSQL restrita pela CLI.
A API mantém somente geração, saúde e Swagger. README e Mermaid foram atualizados
com os 34 tipos próprios efetivamente presentes nos fontes.

**A prova real DeepSeek permanece pendente por decisão explícita do usuário nesta
sessão.** A tarefa 8.2 do OpenSpec não foi marcada como concluída. O adaptador foi
testado com transporte simulado; autenticação, cota, latência e qualidade da SQL
de uma chamada real com a chave do usuário ainda precisam ser observadas.
OpenAI também não teve chamada real: não havia chave disponível no processo do
agente. Essa limitação é separada da implementação e dos testes de contrato.

## Suíte determinística e PostgreSQL real

Comando executado na raiz, com os artefatos oficiais disponíveis para verificação
offline do orçamento:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py
```

Resultado final: **206 testes passaram, 2 foram ignorados e 1 aviso foi emitido**.

- O teste de symlink foi ignorado porque o Windows não concedeu privilégio para
  criar esse tipo de link. A proteção contra escape por junction foi executada
  e passou; os demais casos de confinamento e leitura também passaram.
- O teste de provedor real é opt-in e foi ignorado intencionalmente nessa suíte;
  a execução separada Ollama está registrada abaixo.
- O aviso é a depreciação do cliente Starlette baseado em httpx, já observada no
  marco anterior; não houve falha por esse aviso.

As verificações incluíram contratos estritos, configuração, IDs de conexão,
pasta por usuário, reinício/troca de diretório, Markdown ausente/inválido/excessivo,
orçamento e isolamento de sessão. Também cobriram autenticação/cota/timeouts,
respostas incompletas, comandos proibidos, correções limitadas e ausência de
chaves/resultados em prompts e logs.

No PostgreSQL 16 real: catálogo autorizado, permissões por coluna, RLS, role
administrativa recusada, divergência de identidade, execução da SQL exata,
transação read-only, timeout, truncamento em cursor de servidor, resultado vazio,
colunas repetidas, NULL/Decimal/data e sanitização de erros contendo valores.
Testes concorrentes confirmaram uma única execução por ID e consumo em falha.

Cada roteiro usou um projeto Docker de nome aleatório, porta livre, senhas
efêmeras, volume novo e dados fictícios. Contêiner, rede e volume desse projeto
foram removidos ao terminar; bancos/volumes preexistentes não foram alterados.
Configuração e Markdown dos testes ficaram em diretórios temporários. Nenhuma
chave ou DSN com credencial foi registrado como evidência.

## Prova real Ollama e API

```powershell
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py --real-provider ollama
```

Resultado: **1 teste de integração real passou**, com `qwen3.5:9b` instalado e
Ollama disponível. A prova realizou três chamadas reais ao modelo:

1. Pergunta de ranking por quantidade, usando o Markdown sintético; a CLI recebeu
   entrada controlada `sim`, executou uma vez e o resultado conferiu com a seed.
2. Segunda pergunta, ainda na sessão; a CLI recebeu `não` e cancelou a execução.
   Os valores da tabela anterior não estavam no payload enviado ao modelo.
3. Geração pela API FastAPI com HTTP 200 e proposta aprovada, sem execução.
   `/docs` e `/health` também responderam corretamente.

As entradas CLI foram controladas pelo teste; não se trata de uma demonstração
manual com operador. A API foi exercitada pelo cliente ASGI de testes, sem
servidor HTTP externo ou navegador. O Ollama e o PostgreSQL eram serviços reais.

| Chamada | Estimativa conservadora de entrada | Tokens de entrada reais | Tokens de saída reais |
|---|---:|---:|---:|
| CLI: ranking | 6626 | 1478 | 55 |
| CLI: segunda pergunta | 6895 | 1549 | 43 |
| API: geração independente | 6540 | 1461 | 11 |

Esses valores são uma observação dessa execução, não promessa de determinismo,
custo ou latência. O teste concluiu em aproximadamente 20 segundos, sem contar
a preparação e remoção do projeto Docker.

## Provedores remotos e orçamento

DeepSeek e OpenAI passaram em testes HTTP simulados de perfil/chave próprios,
conteúdo final, corpo grande/malformado, truncamento, raciocínio separado,
ferramentas, erros 401/402/429/5xx, timeout e ausência de retries/redirecionamentos.
O getpass não cai silenciosamente em entrada que ecoa a chave quando o terminal
não oferece entrada oculta.

O método `utf8_upper_bound_v1` foi comparado com tokenizadores oficiais em corpus
de português, SQL, Unicode e controles. DeepSeek V4/Qwen3.5-9B foram fixados por
hash em `tests/fixtures/tokenizer-manifest.json`, com `tokenizers==0.22.1`; OpenAI
usou `tiktoken==0.12.0`/`o200k_base`. São dependências de verificação, não de
inferência. A comparação com `usage` DeepSeek continua vinculada à prova pendente.

## Documentação e revisão

O diagrama foi renderizado com Mermaid CLI 12.2.0 e Chrome headless, gerando SVG
válido em cache. A conferência por AST encontrou 34 classes/interfaces/modelos
nos fontes e os mesmos 34 nomes no diagrama, sem faltas/extras. O bloco Mermaid
do README confere com `assets/diagrama-classes.mmd`.

`pip check` não encontrou dependências quebradas. A validação estrita da mudança
OpenSpec passou. Os arquivos OpenSpec continuam locais/ignorados; não houve
commit, push, deploy ou alteração na branch de documentação acadêmica.

## Critérios e próximos passos

| Critério | Situação verificada |
|---|---|
| Contexto por conexão na pasta local do aplicativo | Implementado; testes de arquivos e isolamento passaram |
| Markdown integral e regra de negócio | Testes simulados e prova Ollama real passaram |
| Orçamento e excesso explícito | Testes de limites/tokenizadores e uso Ollama passaram |
| Política conservadora e três tentativas totais | Testes positivos, adversariais e de correção passaram |
| Confirmação, revalidação e proposta exata | Testes unitários, concorrentes, PostgreSQL e CLI passaram |
| Leitura, role, RLS, timeout e retorno limitado | Integração PostgreSQL real passou |
| Resultado tabular e ausência de resultado na LLM | Testes determinísticos e prova Ollama passaram |
| DeepSeek BYOK implementado | Contrato simulado passou; prova real foi adiada pelo usuário |
| OpenAI secundário | Contrato simulado passou; sem chave para prova real |
| Desktop, entrevista completa, SQLite e histórico permanente | Permanecem para V1 |

Quando o usuário decidir realizar a prova DeepSeek, com `DEEPSEEK_API_KEY` no
ambiente do terminal, executar:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/verify_v0.py --real-provider deepseek
```

Para demonstração manual com dados sintéticos, usar `--demo-provider deepseek`.
Depois da prova, registrar o resultado real e só então concluir a tarefa 8.2.
