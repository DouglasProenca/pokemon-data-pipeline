# Pokémon Data Pipeline

Pipeline de engenharia de dados para acompanhar diariamente preços de cartas e produtos selados de uma coleção Pokémon TCG, converter valores para reais usando a PTAX e comparar o desempenho com dólar e CDI.

> **Configuração pendente:** preencher coleção, sigla e `group_id` após confirmar a disponibilidade do prefixo no RustFS da turma.

## Coleção escolhida

- Nome: ME01 - Mega Evolution
- Sigla: MEG
- TCGplayer: 24380
- Responsável: Douglas Proença Rolim de Souza
- Prefixo de escrita: 26/09/2025

Antes da primeira gravação, confirmar que esse prefixo ainda não existe no bucket `tcg` do RustFS da turma. Cada aluno escreve apenas no prefixo de sua coleção.

## Stack prevista

Python, Requests, Pydantic, Parquet/PyArrow, DuckDB, RustFS (S3-compatible), Streamlit, Pytest, VCR.py e Testcontainers.

## Pré-requisitos

- macOS
- Python 3.11 ou superior (recomendado: Python 3.12)
- Git
- Credenciais individuais do RustFS fornecidas pelo professor (não colocar no Git)

Confira as ferramentas:

```bash
python3 --version
git --version
```

## Preparar ambiente local

```bash
cd pokemon-data-pipeline
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

As dependências serão adicionadas conforme os requisitos forem aprovados e implementados. Não execute coleta antes de confirmar o `group_id` e as credenciais do RustFS.

## Configuração local

```bash
cp .env.example .env
```

Preencha `.env` localmente com os dados recebidos do professor. Nunca compartilhe ou versione esse arquivo.

## Execução

Os comandos de coleta, reprocessamento, testes e dashboard serão documentados aqui após a implementação das respectivas tarefas.

## Arquitetura

- `raw/`: respostas originais, imutáveis.
- `silver/`: tabelas tipadas em Parquet no contrato comum da turma.
- `gold/`: modelo dimensional no DuckDB.
- `dashboard/`: aplicação de análise.
- `docs/` e `specs/`: artefatos de SDD, arquitetura, decisões e rastreabilidade.

## Histórico de coleta

Registrar abaixo os dias sem coleta, com data e motivo. Não reconstruir nem inventar preços de dias ausentes.

| Data | Situação | Motivo/evidência |
|---|---|---|
