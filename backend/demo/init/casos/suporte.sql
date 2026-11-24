CREATE TABLE chamados (
    id integer PRIMARY KEY,
    assunto text NOT NULL,
    status text NOT NULL CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CANCELED'))
);

INSERT INTO chamados VALUES
    (1, 'Atualizar cadastro', 'OPEN'),
    (2, 'Dúvida sobre fatura', 'OPEN'),
    (3, 'Revisar solicitação', 'IN_PROGRESS'),
    (4, 'Confirmar recebimento', 'RESOLVED'),
    (5, 'Chamado duplicado', 'CANCELED');

CREATE TABLE equipes (
    id integer PRIMARY KEY,
    nome text NOT NULL UNIQUE,
    canal_principal text NOT NULL
);

INSERT INTO equipes VALUES
    (1, 'Atendimento', 'CHAT'),
    (2, 'Financeiro', 'PORTAL'),
    (3, 'Plataforma', 'EMAIL');

CREATE TABLE categorias (
    id integer PRIMARY KEY,
    nome text NOT NULL UNIQUE,
    sla_horas integer NOT NULL CHECK (sla_horas > 0)
);

INSERT INTO categorias VALUES (1, 'Cadastro', 48), (2, 'Faturamento', 24), (3, 'Incidente', 8);

ALTER TABLE chamados
    ADD COLUMN equipe_id integer REFERENCES equipes (id),
    ADD COLUMN categoria_id integer REFERENCES categorias (id),
    ADD COLUMN created_at date NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN resolvido_em date,
    ADD COLUMN prioridade text NOT NULL DEFAULT 'MEDIA'
        CHECK (prioridade IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA'));

UPDATE chamados
SET equipe_id = dados.equipe, categoria_id = dados.categoria, prioridade = dados.prioridade,
    created_at = dados.abertura, resolvido_em = dados.resolucao
FROM (VALUES
    (1, 1, 1, 'MEDIA', date_trunc('month', CURRENT_DATE)::date, NULL::date),
    (2, 2, 2, 'ALTA', CURRENT_DATE, NULL),
    (3, 3, 3, 'CRITICA', CURRENT_DATE, NULL),
    (4, 2, 2, 'CRITICA', date_trunc('month', CURRENT_DATE)::date, CURRENT_DATE),
    (5, 2, 2, 'ALTA', date_trunc('month', CURRENT_DATE)::date - 1, NULL)
) AS dados (id, equipe, categoria, prioridade, abertura, resolucao)
WHERE chamados.id = dados.id;

INSERT INTO chamados (id, assunto, equipe_id, categoria_id, status, prioridade, created_at, resolvido_em) VALUES
    (6, 'Ajustar cobrança recorrente', 2, 2, 'IN_PROGRESS', 'CRITICA', CURRENT_DATE, NULL),
    (7, 'Reemitir nota fiscal', 2, 2, 'RESOLVED', 'ALTA',
        (CURRENT_DATE - INTERVAL '1 year')::date, (CURRENT_DATE - INTERVAL '1 year')::date),
    (8, 'Acesso ao painel de integrações', 3, 3, 'OPEN', 'BAIXA', date_trunc('month', CURRENT_DATE)::date - 1, NULL)
ON CONFLICT (id) DO NOTHING;
