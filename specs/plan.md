# Plano de arquitetura — versão inicial

## Diagrama C4 — Contexto

```mermaid
flowchart LR
    Colecionador["Colecionador"] --> Dashboard["Dashboard Pokémon TCG"]
    Dashboard --> Pipeline["Pipeline de dados do aluno"]
    Pipeline --> TCGCSV["TCGCSV / TCGplayer"]
    Pipeline --> BCB["Banco Central: PTAX e CDI"]
    Pipeline --> RustFS["RustFS da turma — S3"]
    Dashboard --> RustFS
    Dashboard --> DuckDB["DuckDB / consultas Gold"]
    RustFS --> SilverTurma["Silver de todas as coleções da turma"]
```

## Diagrama C4 — Contêineres

```mermaid
flowchart TB
    subgraph Projeto["Repositório do aluno"]
      Scheduler["Agendador diário"] --> Collector["Coletor Python"]
      Collector --> RawWriter["Gravador Raw imutável"]
      RawWriter --> S3["RustFS da turma / bucket tcg"]
      S3 --> Transform["Transformação Silver / Pydantic"]
      Transform --> Parquet["Silver Parquet"]
      Parquet --> Model["Modelagem Gold / DuckDB"]
      Model --> Gold["Gold Parquet / DuckDB"]
      Gold --> App["Dashboard Streamlit"]
      Tests["Pytest / VCR / Testcontainers"] -. valida .-> Collector
      Tests -. valida .-> Transform
      Tests -. valida .-> Model
    end
    TCGCSV["TCGCSV"] --> Collector
    BCB["APIs Banco Central"] --> Collector
    S3 --> OtherSilver["Silvers dos colegas"]
    OtherSilver --> Model
```

## Decisões arquiteturais pendentes
- ADR para particionamento e chave dos objetos brutos.
- ADR para estratégia de construção/reconstrução da Silver e Gold.
- ADR para esquema estrela e grãos das tabelas.
- ADR para regra de seleção da carteira `propria` e fallback de produto selado.
- ADR para operação do job (GitHub Actions ou Railway).

## Restrições conhecidas
- O RustFS da turma e as silvers dos colegas são sistemas externos.
- Nenhum segredo pode ser armazenado no Git.
- A PTAX aplicada a cada preço não pode ser posterior à data do preço.
- A gravação de Raw é imutável; Silver e Gold são derivadas e reprocessáveis.
