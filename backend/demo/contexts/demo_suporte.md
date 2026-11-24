# Suporte

## Fila e períodos

- Cada linha em `chamados` é um chamado. A **fila ativa** reúne somente `status IN ('OPEN', 'IN_PROGRESS')`.
- A **fila crítica** é a parte da fila ativa com `prioridade IN ('ALTA', 'CRITICA')`.
- Filtre a equipe pelo nome de `equipes.nome`, usando `chamados.equipe_id = equipes.id`.
- Para contar **chamados do mês**, use a data de abertura `chamados.created_at`. Compare o mês e o ano com a data atual. Inclua todos os estados, salvo se a pergunta pedir um recorte de fila.
- `resolvido_em` é a data de resolução. O SLA em horas fica em `categorias.sla_horas`, ligada por `chamados.categoria_id`.
