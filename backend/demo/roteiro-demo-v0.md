# Roteiro da demo do AskDB V0

## Abertura

> Para esta demonstração, imagine que a pessoa já entrou no aplicativo e cadastrou três conexões PostgreSQL. Ela chegou à tela de consulta e vai escolher o modelo e o banco com que quer trabalhar. Nesta V0, representamos essa tela pelo terminal.

> O AskDB usa o esquema acessível ao usuário e as regras de negócio do contexto daquela conexão para propor uma SQL. A pessoa pode revisar a consulta e o destino antes de autorizar a execução. O resultado aparece em uma tabela.

## No terminal

1. Abra a CLI conforme o [guia de preparação no Windows](README.md).
2. Selecione DeepSeek. Informe a chave na entrada oculta e aponte o modelo efetivo exibido no menu.
3. Selecione **Vendas** e aponte o banco, o usuário PostgreSQL e o contexto carregado. Leia a regra de negócio do caso.
4. Faça a pergunta, confira a regra aplicada na SQL e mostre o destino. Digite `sim` e compare a tabela com o gabarito.
5. Use `trocar`, selecione **Suporte** e repita. Use `trocar` novamente para demonstrar **Estoque**. O modelo permanece selecionado e cada conexão começa uma sessão com seu próprio esquema e contexto.

## Três perguntas para o ensaio

Os dados são fictícios e cada pergunta usa uma regra do `context.md` da conexão selecionada.

| Conexão | Pergunta                                                                    | O que conferir na SQL                                                                                                                 | Resultado esperado                      |
| ------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Vendas  | Qual é o faturamento reconhecido de clientes empresariais?                  | Cruzar clientes, pedidos e pagamentos. Somar pagamentos liquidados de pedidos pagos para o segmento empresarial.                      | **R$ 330,00**                           |
| Suporte | Quantos chamados estão na fila crítica do Financeiro?                       | Usar o nome da equipe, os estados `OPEN` e `IN_PROGRESS` e as prioridades `ALTA` e `CRITICA`.                                         | **2 chamados**                          |
| Estoque | Quais produtos têm saldo disponível para venda e qual é o saldo de cada um? | Somar saldo físico menos reservas e avarias por produto. Considerar só depósitos ativos de expedição e saldos consolidados positivos. | **Cabos 16, Cadernos 16 e Cartuchos 4** |

Em Suporte, faça também a pergunta «Quantos chamados temos esse mês?». Ela usa a data de abertura `created_at` e conta todos os estados no mês e ano atuais. A carga inclui **5 chamados no mês da preparação**, mais exemplos do mês anterior e do ano anterior. Em outro mês, o total acompanha as datas gravadas.

Se a SQL omitir a regra, recuse a execução e reformule a pergunta. A SQL gerada pode variar entre rodadas.

## Encerramento

> A V0 demonstra o caminho da pergunta em português até a consulta revisada e executada no PostgreSQL. Na V1, a interface desktop vai incorporar as etapas anteriores a esta tela, como entrar no aplicativo e cadastrar e gerenciar as próprias conexões.

Digite `sair` para fechar a CLI. Pare a infraestrutura com o comando do guia, tópico "Encerrar"
