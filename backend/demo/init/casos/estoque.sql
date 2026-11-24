CREATE TABLE posicoes_estoque (
    id integer PRIMARY KEY,
    produto text NOT NULL UNIQUE,
    quantidade_fisica integer NOT NULL CHECK (quantidade_fisica >= 0),
    quantidade_reservada integer NOT NULL CHECK (quantidade_reservada >= 0),
    quantidade_avariada integer NOT NULL CHECK (quantidade_avariada >= 0),
    CHECK (quantidade_reservada + quantidade_avariada <= quantidade_fisica)
);

INSERT INTO posicoes_estoque VALUES
    (1, 'Cadernos', 20, 6, 2),
    (2, 'Cabos', 15, 3, 1),
    (3, 'Adaptadores', 7, 5, 2);

CREATE TABLE produtos (
    nome text PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    categoria text NOT NULL,
    estoque_minimo integer NOT NULL CHECK (estoque_minimo >= 0)
);

INSERT INTO produtos VALUES
    ('Cadernos', 'PAP-001', 'Papelaria', 10),
    ('Cabos', 'INF-002', 'Informática', 14),
    ('Adaptadores', 'INF-003', 'Informática', 8),
    ('Mouse', 'INF-004', 'Informática', 5),
    ('Cartuchos', 'INF-005', 'Informática', 7);

INSERT INTO produtos (nome, sku, categoria, estoque_minimo)
SELECT produto, 'LEG-' || id, 'Outros', 0 FROM posicoes_estoque
ON CONFLICT (nome) DO NOTHING;

CREATE TABLE depositos (
    id integer PRIMARY KEY,
    nome text NOT NULL UNIQUE,
    cidade text NOT NULL,
    tipo text NOT NULL CHECK (tipo IN ('EXPEDICAO', 'QUARENTENA')),
    ativo boolean NOT NULL
);

INSERT INTO depositos VALUES
    (1, 'Centro', 'Curitiba', 'EXPEDICAO', true),
    (2, 'Sul', 'São José dos Pinhais', 'EXPEDICAO', true),
    (3, 'Triagem', 'Curitiba', 'QUARENTENA', true),
    (4, 'Unidade anterior', 'Londrina', 'EXPEDICAO', false);

ALTER TABLE posicoes_estoque
    ADD COLUMN deposito_id integer NOT NULL DEFAULT 1 REFERENCES depositos (id),
    DROP CONSTRAINT posicoes_estoque_produto_key,
    ADD FOREIGN KEY (produto) REFERENCES produtos (nome),
    ADD UNIQUE (produto, deposito_id);

INSERT INTO posicoes_estoque (id, produto, deposito_id, quantidade_fisica, quantidade_reservada, quantidade_avariada) VALUES
    (4, 'Cadernos', 2, 5, 1, 0),
    (5, 'Cabos', 2, 8, 2, 1),
    (6, 'Adaptadores', 3, 9, 0, 0),
    (7, 'Mouse', 4, 14, 0, 0),
    (8, 'Cartuchos', 2, 6, 2, 0)
ON CONFLICT DO NOTHING;
