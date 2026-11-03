CREATE TABLE clientes (id integer PRIMARY KEY, nome text NOT NULL);
CREATE TABLE produtos (id integer PRIMARY KEY, nome text NOT NULL, preco numeric(12,2) NOT NULL);
CREATE TABLE pedidos (id integer PRIMARY KEY, cliente_id integer NOT NULL REFERENCES clientes(id));
CREATE TABLE itens_pedido (
    pedido_id integer REFERENCES pedidos(id),
    produto_id integer REFERENCES produtos(id),
    quantidade integer NOT NULL,
    PRIMARY KEY (pedido_id, produto_id)
);
INSERT INTO clientes VALUES (1, 'Cliente fictício A'), (2, 'Cliente fictício B');
INSERT INTO produtos VALUES (1, 'Caderno', 20), (2, 'Caneta', 5), (3, 'Pasta', 12);
INSERT INTO pedidos VALUES (1, 1), (2, 2);
INSERT INTO itens_pedido VALUES (1, 1, 2), (1, 2, 8), (2, 2, 4), (2, 3, 1);

-- Objetos de teste que não devem vazar para o catálogo autorizado.
CREATE TABLE restrita (id integer PRIMARY KEY, segredo text);
CREATE TABLE parcial (id integer PRIMARY KEY, publico text, privado text);
CREATE TABLE referencia_restrita (id integer PRIMARY KEY, destino integer REFERENCES restrita(id));
CREATE TABLE chave_composta (a integer, b integer, PRIMARY KEY (a,b));
CREATE TABLE referencia_composta (id integer PRIMARY KEY, x integer, y integer,
    FOREIGN KEY (x,y) REFERENCES chave_composta(a,b));
