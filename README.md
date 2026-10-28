# AskDB

**Consulte bancos de dados usando linguagem natural.**

O AskDB é um projeto de Trabalho de Conclusão de Curso (TCC) do curso de Análise e Desenvolvimento de Sistemas do Instituto Federal de São Paulo (IFSP) — Câmpus Guarulhos.

O projeto propõe uma aplicação desktop que utiliza Inteligência Artificial (IA) e Processamento de Linguagem Natural (PLN) para permitir que usuários consultem bancos de dados PostgreSQL por meio de perguntas em português, sem precisar escrever comandos SQL manualmente.

## Objetivo

Simplificar o acesso aos dados, permitindo que usuários sem conhecimento técnico em SQL obtenham informações por meio de perguntas em linguagem natural, com mecanismos de validação e segurança antes da execução das consultas.

## Funcionalidades previstas

- Configuração de conexão com bancos de dados PostgreSQL.
- Identificação automática da estrutura do banco de dados.
- Formulação de perguntas em linguagem natural.
- Geração de consultas SQL com auxílio de IA.
- Validação das consultas antes da execução.
- Restrição da execução a consultas de leitura autorizadas.
- Apresentação dos resultados em tabelas.
- Tratamento controlado de erros e tentativas de correção de consultas.

## Tecnologias previstas

**Backend**
- Python
- FastAPI
- SQLAlchemy
- Pydantic

**Frontend e aplicação desktop**
- React
- TypeScript
- Vite
- Electron

**Banco de dados**
- PostgreSQL

**Inteligência Artificial**
- Integração com modelos de linguagem para geração de SQL.

## Segurança

O AskDB será desenvolvido com foco na execução controlada de consultas. A aplicação deverá validar as instruções geradas e impedir operações de escrita ou alteração estrutural do banco de dados.

A utilização de amostras de registros como contexto para a IA dependerá de autorização explícita do usuário.

## Status do projeto

Em desenvolvimento.

As funcionalidades descritas representam o escopo planejado e poderão ser ajustadas durante a implementação e avaliação acadêmica.

## Contexto acadêmico

Projeto desenvolvido como Trabalho de Conclusão de Curso (TCC) em Análise e Desenvolvimento de Sistemas — IFSP, Câmpus Guarulhos.
