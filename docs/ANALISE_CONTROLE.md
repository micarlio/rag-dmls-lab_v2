# Avaliação dos mecanismos de controle

Análise retrospectiva dos mecanismos, com procedimento descrito em
[DESENHO_EXPERIMENTAL.md](DESENHO_EXPERIMENTAL.md). Não houve nova inferência,
ajuste de prompts ou alteração dos dados brutos.

Rodada: `results/runs/20261018T182531677492Z_81b2dd68bc`.
Condição A, com contextos iniciais construídos. Manifesto `complete`, 80 respostas
únicas: 20 perguntas x quatro variantes x semente 42. Qwen 2.5 3B e
embeddinggemma:300m, Ollama local no M1 de 8 GB.

## Conclusão sustentada pela análise

Há benefício observável dos mecanismos: as buscas adicionais encontram informações
que faltavam no pacote inicial; o Self-RAG também corrige justificativas e elimina
valores sem apoio em casos específicos. A etapa de seleção frequentemente impede
que esse benefício chegue ao gerador. O verificador pode proteger informações
erradas ou induzir revisões prejudiciais.

O resultado sustenta um estudo exploratório de mecanismos e condições de falha.
Não sustenta superioridade geral de Adaptive ou Self-RAG sobre o baseline, nem
"máxima fidelidade factual". Benefício de busca, benefício de revisão e melhora
integral da resposta são desfechos distintos.

## Procedimento e unidade de avaliação

Foram examinadas todas as 20 perguntas, 40 cadeias de controle, 80 respostas finais
e 111 pareceres factuais do Self-RAG, incluindo pareceres de candidatos rejeitados.
As anotações foram feitas após observar os resultados; o foco em mecanismos foi
explicitado pelo usuário durante/depois da coleta. Não é uma análise pré-registrada.

A referência são os pedidos e rubricas do manifesto, conferidos nas fontes.
Necessidades inventadas pelo planejador não viram novas obrigações do usuário.
Os cinco PDFs conferem com seus hashes; as 286 páginas do cache conferem com
uma nova extração dos mesmos PDFs. Todas as passagens finais verificadas são
substrings literais das páginas extraídas. Literalidade não comprova interpretação.

Para cada pergunta/variante, foram distinguidos:

1. Conteúdo suficiente, parcial ou ausente no pacote inicial.
2. Informação nova relevante recuperada pelas buscas adicionais.
3. Informação nova efetivamente entregue no contexto de geração.
4. Efeito da seleção/revisão, incluindo correção, preservação, recusa e regressão.
5. Esforço do pipeline e qualidade final como medida complementar.

Um complemento pode apoiar apenas parte de um critério. Contar "houve entrega
útil" não significa que todas as evidências necessárias foram entregues, que a
resposta usou a evidência ou que o controle superou o baseline.

Na comparação entre variantes, os contextos iniciais controlados são comuns,
mas o planejamento e o escopo de geração diferem. Sem uma ablação, nem toda
diferença frente ao baseline pode ser atribuída isoladamente à seleção ou à crítica.
Comparar o próprio rascunho com a revisão ajuda a identificar o efeito do Self-RAG.

## Recuperação e entrega de evidência

| Indicador por pergunta | Adaptive | Self-RAG |
| --- | ---: | ---: |
| Perguntas examinadas | 20 | 20 |
| Com pelo menos uma busca adicional | 19 | 17 |
| Com informação nova relevante nos hits adicionais | 10 | 10 |
| Com pelo menos algum complemento útil entregue ao gerador | 5 | 6 |
| Critérios com algum complemento novo recuperado | 13 | 13 |
| Critérios com algum complemento novo entregue | 5 | 7 |

As dez perguntas com complementos recuperados são Q02, Q06, Q08, Q10, Q11,
Q14, Q16, Q17, Q18 e Q19. A Q08 e a Q16 incluem informação de limitação,
útil para justificar ausência de medição ou de isolamento causal.

O Adaptive entrega complementos em Q06, Q10, Q14, Q17 e Q18. O Self-RAG,
nessas cinco mais Q02. Em Q14, entrega o cabeçalho que desambigua a tabela
do ScreenSpot, mas descarta as taxas do OSWorld e a análise de trajetórias.
Na Q17, entrega a descrição das macros com um artefato de extração.

Nas cinco perguntas rotuladas `two_step`, ambos recuperam ao menos um
complemento relevante em 5/5. O Adaptive entrega algum complemento em 4/5;
o Self-RAG, em 5/5. Contexto final suficiente para TODOS os critérios dessas
perguntas foi anotado em apenas 1/5 para Adaptive (Q18) e 3/5 para Self-RAG
(Q02, Q06 e Q18). Esses números descrevem a evidência enviada, não acertos finais.

Exemplos de descarte:

- **Q02/Adaptive:** a primeira busca contém a página 26, mas a seleção do motivo
  da Drive API conserva o trecho sobre compartilhamento da planilha.
- **Q11/ambos:** a busca recupera a indisponibilidade temporária do modelo;
  o contexto final contém apenas a tabela de categorias de teste.
- **Q14/ambos:** a recuperação inclui as taxas reais do OSWorld e a trajetória
  que reabre menus. O contexto final fica restrito ao ScreenSpot.
- **Q16/ambos:** a passagem de nove fatores simultâneos é recuperada, mas não
  chega à geração; permanece a recusa genérica.

Portanto, a ausência de ganho final não deve ser atribuída automaticamente à
incapacidade de recuperar. Em vários casos, o gargalo observado é a seleção
e preservação de evidências entre a busca e a geração.

## O que o Self-RAG efetivamente mudou

A revisão qualitativa identificou algum benefício local frente ao próprio
rascunho em nove perguntas: Q02, Q03, Q06, Q07, Q08, Q10, Q14, Q17 e Q18.
Cinco desses casos têm efeito misto: Q06, Q10, Q14, Q17 e Q18. Mantêm erros,
perdem requisitos ou sofrem com extração. Isso não representa nove vitórias
frente ao baseline.

Há uma regressão inequívoca do próprio rascunho em Q04: uma recusa apropriada
vira valor inventado de latência. Em outras dez perguntas não se identificou
benefício local da revisão. Na Q11, o mecanismo detecta um problema inicial,
mas termina com uma nova causa falsa; a sinalização correta não virou reparo útil.

Os efeitos categorizados por questão estão anotados em `control_by_question.csv`.
Eles são julgamentos qualitativos, não uma nova métrica de acurácia.

### Q02: ganho de controle com cadeia demonstrável

O contexto inicial descreve conta de serviço e compartilhamento, sem justificar
a Drive API. O rascunho atribui à Drive API a função de compartilhar a planilha.
O crítico marca esse motivo como sem apoio, a busca encontra a página 26 e a
revisão explica a localização da planilha pelo nome antes do acesso pela Sheets API.

Esse caso demonstra detecção de insuficiência, recuperação complementar e
correção factual. A autenticação final continua incompleta segundo a rubrica
integral. Além disso, um candidato da revisão afirma erroneamente compartilhar
o arquivo JSON com a planilha; o crítico o aprova, mas a regra de preservação
mantém a resposta anterior. O resultado favorável coexiste com uma falsa aprovação.

### Q07: complemento de cobertura com evidência já disponível

O baseline descreve a inadequação do servo e o reparo, mas omite nylon.
O Adaptive explicita o material a partir do contexto inicial, sem busca adicional.
O Self-RAG conserva nylon do próprio rascunho e completa o reparo com a origem
no servo reserva. O ganho aqui é de cobertura/organização, não de nova recuperação.
Não houve ablação para separar planejamento, seleção e geração.

### Q08: proteção frente ao próprio rascunho

O rascunho do Self-RAG apresenta temperaturas 41/35 que não estão sustentadas.
As verificações mantêm os itens como incertos, e a política final substitui os
valores por recusa. O baseline já recusava essa pergunta. Há ganho de proteção
interna, sem vantagem demonstrada sobre a resposta do baseline.

### Q18: busca útil e verificação que bloqueia parte do ganho

Ambos entregam no contexto a proposta de tasking. O Adaptive a menciona, mas
também produz uma descrição inadequada de single. O Self-RAG melhora a explicação
do swap e remove descrições de loop sem apoio, porém protege a estratégia falsa
de substituir single por diretivas de sincronização mais flexíveis, aprovada no
rascunho. A informação correta disponível não é usada para corrigir esse item.

### Q04: revisão prejudicial e confusão de métricas

O baseline e o rascunho Self-RAG recusam informar latência. O crítico trata a
recusa como sem apoio, desencadeia busca e revisão; a seleção isola o TTL de
120 segundos. A revisão passa a responder 120 ao pedido de milissegundos e
recebe aprovação. Há troca de grandeza e unidade. É uma regressão causada pela
cadeia de controle, não uma simples falha do primeiro contexto.

## Auditoria dos pareceres de apoio

| Avaliação da decisão de apoio | Ocorrências |
| --- | ---: |
| Aprovação de afirmação sustentada | 25 |
| Sinalização de afirmação sem apoio ou contraditória | 30 |
| Aprovação indevida | 10 |
| Falta de aprovação de afirmação sustentada | 16 |
| Indeterminado ou metarresposta | 28 |
| Apoio literal na extração, com erro de identificador | 2 |
| Total | 111 |

Essa tabela avalia apoio, separado de cobertura. Uma afirmação sustentada pode
estar incompleta e legitimamente precisar de complemento. Os 16 casos não são
automaticamente 16 revisões prejudiciais. Os 28 indeterminados não contam como
acertos/erros do crítico. Dois pareceres sobre epascal_stop são separados porque
o nome aparece literalmente no texto extraído, mas o identificador do PDF é
pascal_stop precedido da conjunção e.

As decisões incluem guardas e os recortes que chegam ao crítico; não são uma
estimativa isolada da qualidade intrínseca do LLM. Há dependência entre itens
repetidos e etapas da mesma pergunta. Não tratar 111 como 111 perguntas independentes.

## Planejamento e abstenção

Foram anotados requisitos não solicitados em oito perguntas: Q06, Q07, Q11,
Q13, Q14, Q15, Q17 e Q19. Há necessidades redundantes em seis: Q03, Q06,
Q10, Q11, Q14 e Q18. As listas se sobrepõem. São anotações semânticas, não
equivalência com duplicatas textuais detectadas pelo contrato JSON.

Na Q15, o plano pergunta sobre idade de participantes e método de treino,
mas omite a razão solicitada para a proporção maior de terminate. Na Q13,
o Self-RAG responde terminate corretamente, mas a recusa a uma descrição
de agente não pedida faz `abstained=True` na resposta completa.

As taxas declaradas de 40%/50%/65% (baseline/Adaptive/Self-RAG) indicam
**pelo menos um item recusado**, incluindo itens extras. Não medem risco,
segurança ou probabilidade de a pergunta ficar sem resposta.

Nas cinco não respondíveis, houve declaração de alguma abstenção em 5/5 no
baseline, 3/5 no Adaptive e 4/5 no Self-RAG. O conteúdo e a justificativa dessas
recusas ainda precisam ser considerados: recusa genérica e explicação de uma
medição não realizada têm coberturas diferentes.

## Custo observado

| Variante | Chamadas LLM por resposta | Buscas extras por resposta | Latência média |
| --- | ---: | ---: | ---: |
| LLM puro | 1,00 | 0,00 | 5,1 s |
| Baseline | 1,00 | 0,00 | 13,0 s |
| Adaptive | 7,05 | 1,90 | 70,2 s |
| Self-RAG | 20,40 | 1,85 | 159,8 s |

O contexto inicial é fornecido, por isso zero buscas do baseline é esperado
nesta condição. Não é uma medição do custo de busca natural do baseline.
Adaptive e Self-RAG custam cerca de 5,4 e 12,3 vezes sua latência de geração.
As médias são das tentativas registradas, não do tempo total de desenvolvimento:
há uma interrupção por truncamento e preparação/warmup fora dessas médias.

No modo controlado, Adaptive investiga mesmo com rota single. Não usar esta
rodada para demonstrar economia de esforço obtida pelo roteamento. Tampouco
atribuir a diferença de custo exclusivamente ao M1: pipelines fazem números
distintos de chamadas e há carregamentos alternados de modelos.

## Qualidade final complementar

| Variante | Acerto integral da rubrica | Fração média de critérios plenamente atendidos |
| --- | ---: | ---: |
| LLM puro | 2/20 | 12,5% |
| Baseline | 8/20 | 55,0% |
| Adaptive | 4/20 | 35,8% |
| Self-RAG | 7/20 | 56,7% |

São julgamentos conforme o procedimento de avaliação. Acerto integral exige todos os
critérios e ausência de erro material. A fração média dá o mesmo peso a cada
pergunta e não conta PARTIAL como MET. Esses números não são o desfecho principal,
mas impedem transformar ganho de uma etapa em alegação de resposta superior.
As explicações e os critérios individuais estão nos CSVs auxiliares.

## Síntese por pergunta

| Pergunta | Adaptive | Self-RAG |
| --- | --- | --- |
| Q01 | Perde TTL e responde 24 horas. | Preserva 120 segundos; custo de verificação. |
| Q02 | Recupera motivo correto, mas não o entrega. | Entrega p.26 e corrige motivo da Drive API. |
| Q03 | Contexto suficiente; geração perde detalhes. | Corrige remoção indevida de datas em itens redundantes. |
| Q04 | Confunde TTL com latência. | Revisão transforma recusa em latência inventada. |
| Q05 | Busca e seleção missing; fallback mantém Fusion 360. | Confirma Fusion 360 sem busca extra. |
| Q06 | Encontra inversão de sinal, mas mistura ajuste físico/código. | Corrige sinal, recusa causa disponível e mantém item genérico. |
| Q07 | Explicita nylon sem nova busca. | Completa reparo e preserva fatos; recusa item extra. |
| Q08 | Não entrega limitação térmica e inventa valores. | Elimina valores do próprio rascunho; baseline já recusava. |
| Q09 | Troca Streamlit por ADK. | Preserva Streamlit sem busca extra. |
| Q10 | Entrega URLs; resposta fica genérica. | Entrega URLs, mas mistura testes e conserva negação de detalhes. |
| Q11 | Descarta causa correta recuperada. | Detecta problema, mas aprova nova causa falsa. |
| Q12 | Mantém recusa. | Revisão apenas torna recusa mais genérica. |
| Q13 | Busca para descrição não solicitada; mantém terminate. | Mantém terminate; recusa extra infla taxa declarada. |
| Q14 | Entrega cabeçalho, descarta OSWorld e confunde colunas. | Corrige ScreenSpot em item, mas transfere seus valores ao OSWorld. |
| Q15 | Plano perde causalidade e inventa idade; resposta piora. | Trabalha em itens extras e não recupera razão pedida. |
| Q16 | Encontra limitação causal, mas não a entrega. | Mesma perda; revisão repete recusas. |
| Q17 | Recupera macros, conservando artefato de extração. | Recupera macros, conservando artefato de extração. |
| Q18 | Entrega tasking; resposta contém explicação extra inadequada. | Melhora swap, mas protege estratégia falsa já aprovada. |
| Q19 | Busca motivo de automação, não o entrega e piora referência. | Protege referência mal formulada e não entrega automação. |
| Q20 | Busca sem melhorar justificativa da recusa. | Busca/revisão sem benefício; caráter futuro já estava disponível. |

## Integridade, limitações e uso no artigo

Os arquivos atuais são internamente consistentes: 80 combinações únicas,
sementes/fingerprint alinhados, configuração e fontes do manifesto conferidas.
Entretanto, na inspeção anterior o fingerprint era
`81b2dd68bcba416cc55b028487eb1fe96cdc89ed8516d0e514c967f39048ad55`;
agora é `866680b14025c326dcaf1187ea539db986e120f5c1f0c98e74718c094d19650d`,
na mesma pasta. A história da atualização do manifesto e da retomada permanece
sem esclarecimento. Hashes atuais não comprovam congelamento histórico. A análise
registra a alteração, sem declarar que as respostas foram fabricadas ou que todas
foram produzidas com código diferente.

Também há caracterizações problemáticas de contexto e referências, registradas
nas anotações de Q02, Q08, Q11, Q14, Q16, Q17 e Q19. Não corrigimos as entradas
retroativamente nem excluímos casos. Uma única semente, corpus pequeno, casos
vistos no desenvolvimento e avaliação retrospectiva limitam a generalização. A condição
natural não foi avaliada aqui.

O artigo pode demonstrar: (a) buscas que localizam lacunas; (b) perda do ganho
na seleção; (c) correções do Self-RAG; (d) falsas aprovações e revisões nocivas;
(e) custo adicional. Deve apresentar efeitos mistos e casos mal caracterizados,
além dos exemplos favoráveis. Não há base para prometer superioridade geral,
segurança em aplicações críticas ou que uma API resolveria os problemas observados.

A exigência acadêmica de três execuções do baseline continua pendente na
configuração de uma repetição. Essa análise não inicia novas execuções.


### Esclarecimento da retomada na preparação da entrega

A inspeção adicional de eventos comprovou revisões de múltiplos alvos em lote
em Q02/Q03/Q06/Q07/Q08 e revisões por item em Q10/Q11/Q14/Q15/Q16/Q17/Q18/Q19.
Quatro casos com um alvo são indistinguíveis; três não tiveram revisão.
O código atual usa geração por item. Há uma tentativa truncada de Q10 registrada.
Portanto, a diferença não é apenas uma dúvida sobre hashes: há duas formas de
revisão nos dados. Os custos agregados são descritivos, não de uma política uniforme.
Os casos e anotações semânticas acima permanecem preservados. A operação completa
que atualizou os fingerprints não foi reconstruída. Veja INTEGRIDADE.md e
`self_revision_modes.csv`. Nenhum dado bruto foi alterado para corrigir a proveniência.

## Arquivos e reprodução offline

Na pasta da rodada:

- `review.json`: anotações explícitas, metodologia, hashes e ressalvas.
- `control_by_question.csv`: 40 cadeias anotadas, com testemunhas de evidência.
- `control_checks.csv`: 111 pareceres, texto julgado, recortes e anotação de apoio.
- `control_summary.csv`, `control_support_summary.csv`,
  `control_process.csv`: sínteses de mecanismos, apoio e custo.
- `quality_evaluation.csv`, `quality_criteria.csv`, `quality_summary.csv` e
  tabelas pareadas: avaliação final complementar.

```bash
.venv/bin/python scripts/analyze_control.py results/runs/20261018T182531677492Z_81b2dd68bc
.venv/bin/python scripts/analyze_quality.py results/runs/20261018T182531677492Z_81b2dd68bc
```

Esses comandos consolidam julgamentos já registrados; não geram novas respostas
nem usam o Ollama. Há verificações contra entradas alteradas, pares ausentes,
testemunhas inventadas e entrega de evidência inexistente no contexto.
`evaluation.csv` apresenta perguntas, respostas e referências. Os CSVs de entrega
omitem os campos administrativos de revisão; o procedimento permanece descrito
na metodologia e nos metadados de `review.json`.
