CREATE TABLE pedidos (
    id integer PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('PAGO', 'PENDENTE', 'CANCELADO')),
    valor_total numeric(10, 2) NOT NULL CHECK (valor_total >= 0)
);

INSERT INTO pedidos VALUES
    (1, 'PAGO', 120.00),
    (2, 'PAGO', 80.00),
    (3, 'PENDENTE', 70.00),
    (4, 'CANCELADO', 50.00);

CREATE TABLE clientes (
    id integer PRIMARY KEY,
    nome text NOT NULL,
    segmento text NOT NULL CHECK (segmento IN ('EMPRESARIAL', 'VAREJO')),
    cidade text NOT NULL
);

INSERT INTO clientes VALUES
    (1, 'Norte Papelaria', 'EMPRESARIAL', 'Curitiba'),
    (2, 'Mariana Duarte', 'VAREJO', 'São Paulo'),
    (3, 'Oficina Sul', 'EMPRESARIAL', 'Porto Alegre'),
    (4, 'Rafael Moura', 'VAREJO', 'Campinas');

ALTER TABLE pedidos
    ADD COLUMN cliente_id integer REFERENCES clientes (id),
    ADD COLUMN criado_em date NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN canal text NOT NULL DEFAULT 'SITE' CHECK (canal IN ('SITE', 'LOJA', 'B2B'));

UPDATE pedidos SET cliente_id = id, criado_em = CURRENT_DATE - (9 - id),
    canal = CASE WHEN id IN (1, 3) THEN 'B2B' ELSE 'SITE' END
WHERE id BETWEEN 1 AND 4;

INSERT INTO pedidos (id, cliente_id, criado_em, canal, status, valor_total) VALUES
    (5, 3, CURRENT_DATE - 4, 'B2B', 'PAGO', 150.00),
    (6, 1, CURRENT_DATE - 3, 'LOJA', 'PAGO', 90.00),
    (7, 1, CURRENT_DATE - 2, 'B2B', 'PENDENTE', 200.00),
    (8, 4, CURRENT_DATE - 1, 'SITE', 'CANCELADO', 75.00)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE pagamentos (
    id integer PRIMARY KEY,
    pedido_id integer NOT NULL REFERENCES pedidos (id),
    meio text NOT NULL CHECK (meio IN ('PIX', 'CARTAO', 'BOLETO')),
    status text NOT NULL CHECK (status IN ('LIQUIDADO', 'PENDENTE', 'ESTORNADO')),
    valor numeric(10, 2) NOT NULL CHECK (valor > 0)
);

INSERT INTO pagamentos (id, pedido_id, meio, status, valor)
SELECT dados.* FROM (VALUES
    (1, 1, 'PIX', 'LIQUIDADO', 70.00),
    (2, 1, 'CARTAO', 'LIQUIDADO', 50.00),
    (3, 2, 'CARTAO', 'LIQUIDADO', 80.00),
    (4, 3, 'BOLETO', 'PENDENTE', 70.00),
    (5, 4, 'CARTAO', 'ESTORNADO', 50.00),
    (6, 5, 'PIX', 'LIQUIDADO', 150.00),
    (7, 6, 'PIX', 'LIQUIDADO', 60.00),
    (8, 6, 'CARTAO', 'ESTORNADO', 30.00),
    (9, 7, 'CARTAO', 'LIQUIDADO', 50.00),
    (10, 7, 'BOLETO', 'PENDENTE', 150.00),
    (11, 8, 'CARTAO', 'ESTORNADO', 75.00)
) AS dados (id, pedido_id, meio, status, valor)
JOIN pedidos ON pedidos.id = dados.pedido_id;
