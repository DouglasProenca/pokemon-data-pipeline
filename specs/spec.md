# Especificação do sistema — versão inicial

> Estado: rascunho inicial. Os requisitos devem ser revisados e aprovados antes da implementação. A coleção e o `group_id` ainda precisam ser preenchidos no README e na configuração local.

## Objetivos relacionados
- OBJ-01: rankings de valorização/desvalorização.
- OBJ-02: comparação selados × avulsos.
- OBJ-03: comparação de coleções da turma.
- OBJ-04: concentração por raridade.
- OBJ-05: risco × retorno.
- OBJ-06: desafio da carteira de R$ 1.000.

## Requisitos funcionais

### RF-01 — Coletar produtos e preços
**Objetivo:** OBJ-01, OBJ-02, OBJ-04, OBJ-05, OBJ-06.

Dado que a coleção foi configurada, quando o job diário executar após 20h UTC, então deverá consultar os endpoints de produtos e preços do TCGCSV para o `group_id` configurado, respeitando User-Agent próprio, pausa mínima de 100 ms, timeout e limite de chamadas.

### RF-02 — Gravar bruto sem sobrescrever
**Objetivo:** OBJ-01 a OBJ-06.

Dado que as respostas foram obtidas, quando forem gravadas no RustFS, então os arquivos originais deverão ser armazenados no prefixo exclusivo da coleção e data, sem alteração e sem sobrescrever objeto existente. Uma segunda tentativa para a mesma chave deverá ser recusada e testada.

### RF-03 — Coletar PTAX e CDI
**Objetivo:** OBJ-01, OBJ-03, OBJ-06.

Dado que o job diário executar, quando consultar o Banco Central, então deverá obter os boletins de PTAX do dia e a janela disponível do CDI (SGS série 12), gravando as respostas originais no prefixo da coleção.

### RF-04 — Construir Silver validada
**Objetivo:** OBJ-01 a OBJ-06.

Dado que existam arquivos brutos, quando a transformação Silver executar, então deverá produzir `colecao`, `produto`, `preco_diario`, `cambio_diario` e `cdi_diario` em Parquet, respeitando exatamente os nomes e tipos mínimos do contrato comum. Registros inválidos deverão ir para quarentena com motivo; preços ausentes permanecerão nulos.

### RF-05 — Construir Gold dimensional
**Objetivo:** OBJ-01 a OBJ-06.

Dado que a Silver esteja disponível, quando a Gold for construída, então deverá produzir um esquema estrela consultável pelo DuckDB, com fato de preço diário e dimensões de produto, coleção, data e acabamento, além do fato de câmbio diário.

### RF-06 — Converter preços para reais sem olhar o futuro
**Objetivo:** OBJ-01, OBJ-02, OBJ-03, OBJ-05, OBJ-06.

Dado um preço observado na data D, quando o valor em reais for calculado, então deverá ser usada a PTAX de fechamento de D ou a última PTAX de fechamento anterior a D, nunca uma cotação posterior, usando junção temporal equivalente a `ASOF JOIN`.

### RF-07 — Reprocessar sem duplicar
**Objetivo:** OBJ-01 a OBJ-06.

Dado o conjunto de arquivos brutos, quando o comando de reprocessamento for executado uma ou mais vezes, então Silver e Gold deverão ser reconstruídas de forma idempotente, sem duplicação de linhas.

### RF-08 — Responder às cinco perguntas no dashboard
**Objetivo:** OBJ-01 a OBJ-05.

Dado que a Gold esteja disponível, quando o usuário abrir o dashboard, então deverá conseguir consultar os cinco painéis definidos no enunciado, com valores em reais, acesso aos valores em dólar, imagem dos produtos citados e link para a página do produto.

### RF-09 — Calcular as cinco carteiras
**Objetivo:** OBJ-06.

Dado o primeiro dia de coleta e R$ 1.000, quando as carteiras forem simuladas diariamente, então deverão ser calculadas as estratégias `selado`, `cesta_raras`, `propria`, `dolar` e `cdi`, usando apenas informação disponível na data, unidades inteiras, PTAX correta, caixa residual e taxa de venda configurável.

## Requisitos não funcionais

### RNF-01 — Segurança de credenciais
Dado que o projeto seja versionado, quando qualquer commit for criado, então nenhuma credencial, token ou segredo poderá estar presente no repositório ou nos logs.

### RNF-02 — Resiliência da coleta
Dado que a fonte retorne erro temporário, quando o coletor executar, então deverá repetir chamadas com espera crescente, registrar a falha e não produzir dados fictícios.

### RNF-03 — Testabilidade
Dado que modelos, parsers e transformações sejam executados em testes unitários, quando a suíte rodar, então esses testes não deverão depender de rede externa. Integrações deverão usar respostas gravadas (VCR) e Testcontainers quando aplicável.

### RNF-04 — Reprodutibilidade
Dado um clone limpo do repositório, quando as instruções do README forem seguidas com as variáveis necessárias, então deverá ser possível executar o pipeline e os testes.

### RNF-05 — Observabilidade de lacunas
Dado que um dia não tenha coleta bem-sucedida, quando a execução terminar, então a lacuna deverá ser registrada e visível, sem interpolação ou invenção de valores.

## Critérios transversais
- O contrato Silver é obrigatório e compartilhado com a turma.
- O aluno grava somente no prefixo da própria coleção.
- Cada requisito deve estar ligado a objetivo, tarefa, componente e evidência em `docs/rastreabilidade.md`.
