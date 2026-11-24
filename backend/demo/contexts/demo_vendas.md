# Vendas

## Faturamento reconhecido

- Some `pagamentos.valor`, em reais, somente para pagamentos com `pagamentos.status = 'LIQUIDADO'` de pedidos com `pedidos.status = 'PAGO'`.
- Um pedido pode ter mais de um pagamento. Conte cada pagamento liquidado uma vez. O `pedidos.valor_total` é o valor original do pedido.
- Exclua parcelas pendentes e estornadas. Pagamento parcial liquidado de pedido ainda pendente fica fora.
- Para faturamento de clientes **empresariais**, filtre `clientes.segmento = 'EMPRESARIAL'`. O segmento vem do cadastro do cliente, independentemente do canal do pedido.
- Relacione `pagamentos.pedido_id` com `pedidos.id` e `pedidos.cliente_id` com `clientes.id`.
