# Validação ATAM

A validação ATAM será completada após as decisões arquiteturais e a implementação. Não registrar resultados hipotéticos como se fossem testes executados.

## Atributos de qualidade prioritários
- Continuidade da série diária.
- Integridade e imutabilidade do dado bruto.
- Interoperabilidade do contrato Silver da turma.
- Reprodutibilidade do pipeline.
- Segurança das credenciais.

## Cenários a detalhar
1. TCGCSV retorna HTTP 503 no horário da coleta.
2. Job tenta gravar novamente uma chave Raw já existente.
3. Uma Silver de colega apresenta coluna/tipo fora do contrato.
4. Coleta falha por um dia e precisa aparecer como lacuna.
5. Reprocessamento é executado duas vezes sobre o mesmo intervalo.

Para cada cenário, preencher fonte, estímulo, artefato, ambiente, resposta e medida de resposta, além de risco, ponto de sensibilidade e trade-off.
