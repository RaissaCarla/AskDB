# Estoque

## Saldo liberado para venda

- O **saldo disponível para venda** é a soma de `quantidade_fisica - quantidade_reservada - quantidade_avariada` por produto, considerando apenas depósitos ativos com `tipo = 'EXPEDICAO'`.
- Filtre `depositos.ativo = TRUE`. Quarentena e depósitos desativados ficam fora, mesmo quando têm unidades físicas. Relacione `posicoes_estoque.deposito_id` com `depositos.id`.
- Para listar produtos disponíveis, mostre apenas os com saldo consolidado positivo, agrupando por `posicoes_estoque.produto`.
- Para identificar itens abaixo do mínimo, compare o saldo consolidado com `produtos.estoque_minimo`. O campo `posicoes_estoque.produto` corresponde a `produtos.nome`.
