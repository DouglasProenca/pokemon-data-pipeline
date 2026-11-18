# Backlog inicial de tarefas

| Tarefa | Descrição | Requisito(s) | Evidência / teste esperado | Estado |
|---|---|---|---|---|
| T-01 | Confirmar coleção, sigla, group_id e disponibilidade do prefixo | RF-01, RF-02 | README e verificação de prefixo documentados | Pendente |
| T-02 | Preparar ambiente local e configuração por variáveis | RNF-01, RNF-04 | Clone/ambiente configurado sem segredo no Git | Pendente |
| T-03 | Implementar cliente HTTP TCGCSV com timeout, User-Agent e retry | RF-01, RNF-02 | Testes unitários e VCR | Pendente |
| T-04 | Implementar consultas PTAX e CDI | RF-03 | Testes de parser e VCR | Pendente |
| T-05 | Implementar gravador Raw imutável no RustFS | RF-02, RNF-01 | Teste de integração recusa sobrescrita | Pendente |
| T-06 | Implementar job/agendamento diário | RF-01, RF-03, RNF-02, RNF-05 | Execução agendada e log de lacunas | Pendente |
| T-07 | Validar modelos Pydantic e produzir Silver Parquet | RF-04 | Testes de schema, tipos e quarentena | Pendente |
| T-08 | Implementar reprocessamento idempotente | RF-07, RNF-03 | Duas execuções não duplicam linhas | Pendente |
| T-09 | Implementar Gold em esquema estrela | RF-05 | Testes SQL/consultas DuckDB | Pendente |
| T-10 | Implementar ASOF JOIN para câmbio | RF-06 | Teste de fim de semana e feriado | Pendente |
| T-11 | Implementar perguntas 1, 2 e 4 | RF-08 | Evidências dos três painéis locais | Pendente |
| T-12 | Implementar perguntas 3 e 5 com dados da turma | RF-08 | Evidências de consulta multicoleta | Pendente |
| T-13 | Implementar simulação das cinco carteiras | RF-09 | Testes de unidades inteiras, caixa, PTAX e CDI | Pendente |
| T-14 | Publicar dashboard e job; completar documentação e rastreabilidade | RNF-01 a RNF-05 | README, pytest, ATAM e matriz | Pendente |
