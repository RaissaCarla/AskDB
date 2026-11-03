# Evidências do marco de 20%

Verificação realizada em 03/11/2026, na branch `marco-1-20-pct`.
Este registro descreve o comportamento observado no ambiente de desenvolvimento,
sem representar garantia de correção geral das SQLs ou segurança de produção.

## Ambiente

- Python 3.11.3 em ambiente virtual, pacote instalado em modo editável.
- PostgreSQL 16 em Docker, projeto de teste isolado `askdb-marco20-verificacao`.
- Porta temporária 55433, pois 5433 já estava ocupada; banco existente preservado.
- Role `askdb_reader`: SELECT permitido; INSERT, UPDATE e DELETE negados.
- Ollama local disponível com `qwen3.5:9b` instalado.
- Credenciais temporárias permaneceram no ambiente dos processos/contêiner de teste,
  sem serem registradas neste documento ou versionadas.
- Após a verificação, o contêiner, volume e rede exclusivos desse teste foram
  removidos. Nenhum banco ou volume preexistente foi alterado.

## Testes automatizados

Resultado: **92 testes passaram**, incluindo os quatro testes de integração com
PostgreSQL real. Não houve dependência do Ollama para essa suíte.

Cobertura exercitada: limites da entrada; contratos; configuração; permissões de
tabelas/colunas; ordem de chaves compostas; ocultação de FK com destino restrito;
falhas de conexão e fechamento de recursos; rejeição de superuser/BYPASSRLS;
SQL permitida/proibida; falhas e respostas incompletas do Ollama; API/CLI;
equivalência das entradas e ausência de execução de propostas.

Uma advertência de depreciação do cliente de testes Starlette/httpx foi emitida.
Ela não causou falha; a migração desse cliente poderá acompanhar atualização
futura das dependências de teste.

Neste ambiente gerenciado, sockets do cliente HTTP de testes, Docker e Ollama
exigiram execução fora do sandbox. A instalação de dependências também exigiu
acesso à rede fora dele. Isso foi tratado por elevação das ferramentas, sem
reduzir requisitos ou ignorar verificações.

## Demonstração com modelo real

Pergunta enviada pela API FastAPI e pela CLI:

```text
Quais sao os cinco produtos mais vendidos por quantidade?
```

As duas entradas compartilharam o mesmo caso de uso e retornaram:

```sql
SELECT p.nome, SUM(i.quantidade) AS total_vendido
FROM public.itens_pedido i
JOIN public.produtos p ON i.produto_id = p.id
GROUP BY p.nome
ORDER BY total_vendido DESC
LIMIT 5;
```

A API respondeu HTTP 200 com `validation.status = approved` e `reasons = []`.
A CLI exibiu a SQL e `Decisão: aprovada`, encerrando após `sair`.
A API foi exercitada em processo pelo cliente ASGI de testes, sem servidor
HTTP externo. A CLI foi exercitada com entrada/saída controlada para reproduzir
a sessão. Foram feitas duas chamadas reais ao modelo; a igualdade das SQLs
nesta demonstração não é uma promessa de determinismo da LLM.

O catálogo incluiu tabelas comerciais e fixtures autorizadas. A tabela `restrita`
e a coluna `parcial.privado` ficaram ausentes; a FK para destino restrito foi
omitida. Nenhuma amostra ou SQL gerada foi executada/enviada ao banco.

## Bloqueios e falhas reproduzíveis

A suíte confirmou bloqueio de DELETE, INSERT, UPDATE, DROP, múltiplos comandos,
SELECT INTO, FOR UPDATE, pg_sleep, funções proibidas aninhadas, catálogos de
sistema, CTEs comuns/recursivas, subconsultas e UNION. Esses bloqueios usam
respostas simuladas, não dependem de convencer o modelo a produzir um ataque.

Timeout da LLM produz HTTP 504 e `llm_timeout`; indisponibilidade produz 503;
resposta incompleta/inválida produz 502; erro inesperado produz 500 sanitizado.
Pergunta inválida produz 422 antes das dependências. A CLI informa as categorias
e permite uma nova pergunta após falhas recuperáveis.

## Situação da entrega

Critérios do marco atendidos na verificação: ambiente/seed, role restrita,
catálogo real, integração Ollama, núcleo desacoplado, validação positiva/negativa,
entrada e erros controlados, testes sem modelo, API, CLI e documentação.

Execução SQL, confirmação de execução, memória por conexão e correção automática
continuam para evolução V0. Desktop, entrevista e persistência pertencem à V1.
CTEs e subconsultas são somente possibilidades de expansão, sem aceite ou
cronograma confirmado para esses marcos.
