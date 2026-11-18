# AGENTS.md — Pokémon Data Pipeline

## Objetivo
Construir um pipeline diário de dados do Pokémon TCG para analisar cartas e produtos selados como ativos de coleção. O pipeline coleta dados do TCGCSV e do Banco Central, grava o bruto de forma imutável no RustFS da turma, transforma os dados em Silver/Gold e disponibiliza análises em um dashboard Python.

## Regras de trabalho
1. Siga Spec-Driven Development: persona → objetivos → especificação → plano → tarefas → implementação → validação ATAM.
2. Não implemente uma funcionalidade sem requisito e tarefa associados.
3. Faça uma tarefa pequena por vez; inclua ou atualize os testes na mesma alteração.
4. Não invente preços, cotações, datas, produtos ou evidências. Dado ausente deve permanecer ausente/nulo e lacunas devem ser registradas.
5. O bruto (`raw/`) é imutável: nunca sobrescrever ou apagar objetos já gravados.
6. A Silver deve respeitar exatamente os nomes e tipos mínimos do contrato comum da turma.
7. Transformações Silver/Gold devem ser reconstruíveis a partir do bruto e idempotentes.
8. Toda decisão arquitetural relevante deve ser registrada em `docs/adr/`.
9. Atualize `docs/rastreabilidade.md` quando requisitos, decisões, componentes ou testes mudarem.
10. Registre os prompts CREATE realmente utilizados em `docs/prompts.md`. Não invente histórico de prompts.

## Segurança e segredos
- Nunca versionar `.env`, tokens, senhas, access keys, secret keys ou credenciais do RustFS.
- Usar `.env.example` apenas com nomes de variáveis e valores fictícios/vazios.
- Nunca imprimir credenciais em logs ou mensagens de erro.
- Não colar credenciais em issues, commits ou documentação.
- Se uma credencial for exposta, avisar o responsável e solicitar rotação/revogação.

## Fontes e limites da coleta
- TCGCSV: usar `User-Agent` próprio, respeitar pelo menos 100 ms entre chamadas e no máximo 10.000 requisições/dia.
- Executar a coleta diária somente após a atualização da fonte (depois de 20h UTC).
- Usar timeout, repetição com espera crescente e registro explícito de falha.
- Não contornar proteções anti-robô. Não fazer scraping fora dos termos/robots.txt.
- Não preencher dias ausentes com valores inventados ou com cotações futuras.

## Gates de qualidade
- Antes de implementar: requisito, critério de aceite e tarefa documentados.
- Antes de gravar Silver na área compartilhada: validar esquema/tipos com DuckDB contra o contrato da turma.
- Antes de considerar uma tarefa concluída: testes correspondentes executados e evidência registrada.
- Antes de entregar: execução a partir de clone limpo, `pytest`, verificação de segredos e matriz de rastreabilidade revisada.

## Convenção de commits
Formato: `tipo(T-xx): descrição [RF-yy]` ou `[RNF-yy]`.
Exemplo: `feat(T-05): gravador raw recusa sobrescrita [RF-02]`.

## Comandos esperados
Os comandos definitivos serão registrados no README após a implementação do CLI. A intenção é disponibilizar comandos únicos para coleta diária, reprocessamento e execução do dashboard.
