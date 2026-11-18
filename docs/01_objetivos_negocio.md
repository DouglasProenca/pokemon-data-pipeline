# Objetivos de negócio

## OBJ-01 — Identificar valorização e desvalorização
Permitir identificar as cartas da coleção que mais valorizaram e desvalorizaram desde o início da coleta, em reais, separando efeito do preço em dólar e efeito cambial.

**Métrica:** variação percentual entre primeiro e último dia disponíveis, por carta e acabamento, considerando o filtro mínimo de US$ 1 no primeiro dia.

## OBJ-02 — Comparar selados e cartas avulsas
Avaliar se os produtos selados preservaram valor melhor que as cartas avulsas da coleção.

**Métrica:** índices base 100; média dos produtos selados contra soma dos preços das cartas de raridade Double Rare em diante.

## OBJ-03 — Comparar coleções da turma
Identificar qual coleção apresentou maior valorização no período.

**Métrica:** soma do preço em reais de um exemplar de cada carta por coleção, em índice base 100; comparação com PTAX também em base 100.

## OBJ-04 — Entender concentração de valor por raridade
Mostrar como o valor da coleção está distribuído entre raridades e quantas cartas concentram 80% do valor.

**Métrica:** participação percentual de cada raridade no valor total no último dia disponível e contagem de cartas até atingir 80%.

## OBJ-05 — Comparar retorno e risco
Identificar cartas da turma com melhor relação entre retorno e volatilidade.

**Métrica:** retorno no período contra desvio-padrão dos retornos diários, para cartas acima de US$ 5.

## OBJ-06 — Comparar estratégias de alocação de R$ 1.000
Comparar carteiras de cartas avulsas, produtos selados, dólar e CDI, avaliadas pelo valor de liquidação.

**Métrica:** valor final e retorno acumulado, considerando unidades inteiras, caixa residual, PTAX de venda na compra, PTAX de compra na venda e taxa de venda parametrizável.

## Restrições e hipóteses
- Os dados de preço são observações diárias do TCGCSV; dias sem coleta não serão preenchidos artificialmente.
- A PTAX aplicada será a cotação de fechamento do próprio dia ou a última cotação de fechamento anterior disponível.
- A taxa de venda de 15% é hipótese inicial indicada no enunciado e deverá ser configurável e registrada em ADR.
- As análises que dependem dos dados da turma só estarão completas quando as silvers dos colegas estiverem disponíveis.
