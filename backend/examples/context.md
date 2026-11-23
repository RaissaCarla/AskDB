# Contexto de negócio — demonstração sintética

Este exemplo se aplica ao banco comercial fictício de desenvolvimento.

## Termos e regras confirmadas para a demonstração

- "Produtos mais vendidos" significa maior soma de `itens_pedido.quantidade` por produto.
- Volume de vendas é quantidade de unidades, e não número de pedidos nem valor em dinheiro.
- O nome comercial de um produto está em `produtos.nome`.
- O relacionamento entre itens e produtos usa `itens_pedido.produto_id = produtos.id`.

## Limites de interpretação

- O esquema técnico autorizado é obtido do PostgreSQL a cada geração.
- O banco de exemplo não registra status de cancelamento nem data do pedido.
- Não inventar filtros de data ou cancelamento quando essas informações não existem no esquema.
