# Desenho experimental

## Objetivo

Investigar em quais situações mecanismos de busca adaptativa e verificação/revisão
tratam limitações de um RAG com recuperação única e qual esforço adicional exigem.
O objeto são os mecanismos; os TCCs são os documentos de teste.

A análise segue lacuna, decisão, evidência recuperada, evidência entregue,
alteração da resposta e custo. A correção final complementa o diagnóstico.
Ativar controle ou aumentar chamadas não demonstra benefício automaticamente.
O foco em mecanismos foi explicitado durante/depois da coleta: análise retrospectiva,
não pré-registrada. Todos os casos foram mantidos, inclusive os desfavoráveis.

## Corpus e casos

Cinco PDFs, 286 páginas físicas (269 com texto), 679 chunks. Documentos e fontes
em `corpus/manifest.csv`; extração via pypdf, chunks de 900 caracteres com
sobreposição de 150, sem cruzar documento/página. Há artefatos de extração em
identificadores e tabelas; referências não dispensam inspeção do conteúdo.

20 perguntas congeladas: uma de cada cenário por documento.

| Cenário planejado | Perguntas | Mecanismo investigado |
| --- | --- | --- |
| Direto | 5 | Preservar resposta/evidência suficientes e evitar esforço desnecessário. |
| Duas etapas | 5 | Identificar lacuna e buscar complemento no corpus comum. |
| Distrator | 5 | Distinguir condições, entidades, métricas e estágios de um trabalho. |
| Não respondível | 5 | Recusar medição/resultado não apresentado, sem inventar valor. |

Os rótulos refletem o planejamento, não adequação automaticamente comprovada.
As falhas de caracterização estão identificadas em `ANALISE_CONTROLE.md`,
sem alteração retroativa de `questions.json`.

## Variantes e condições

LLM puro, baseline, Adaptive e Self-RAG. Qwen 2.5 3B em geração e controle;
embeddinggemma:300m; recuperação híbrida TF-IDF/embeddings com RRF.
Top-k 4, conjunto candidato 20, expansão em páginas vizinhas, contexto final
de até 6.500 caracteres e janela do modelo de 4.096 tokens.

**Condição A, avaliada:** todas as variantes RAG recebem o mesmo pacote inicial
construído a partir de `controlled_initial_chunks`. O baseline gera com esse
pacote; controles podem buscar no mesmo índice normal. Gabaritos, cenário,
rubricas e páginas esperadas não entram nos prompts dos controladores.

O Adaptive executa seleção/investigação no modo controlado mesmo com rota single.
A Condição A não avalia economia obtida pela escolha entre busca única e iterativa.

**Condição B, implementada e não avaliada aqui:** recuperação inicial natural,
sem pacote injetado. Um diagnóstico de top-k foi explorado, mas mediu truncamento,
não ganho ou perda de qualidade. Não é comparação de acurácia com baseline ampliado.

**Revisões observadas:** os registros do Self-RAG incluem revisão em lote e por
item; o código atual revisa cada alvo separadamente. As formas observadas por
pergunta estão em
[self_revision_modes.csv](../results/runs/20261018T182531677492Z_81b2dd68bc/self_revision_modes.csv).
As médias de custo descrevem o conjunto da coleta, sem isolar uma política uniforme.

## Implementação dos mecanismos

`rag_lab.py` concentra ingestão, recuperação, geração e execução;
`rag_control.py` implementa a política `evidence_needs`. A apresentação offline
dos registros fica em `reporting.py`, sem importar o cliente dos modelos.

### Componentes comuns

As variantes RAG compartilham o recuperador e o orçamento de contexto. Os IDs
identificam documento e página; as unidades selecionadas preservam texto literal
e posição na passagem. As respostas são estruturadas por item, com resposta,
indicação de recusa e citações. Uma citação válida permite rastrear a origem,
mas não comprova que a fonte sustenta a afirmação.

O LLM puro recebe apenas a pergunta. O baseline gera a resposta a partir de
uma recuperação inicial no modo `full` ou do pacote fornecido no modo
`controlled`, sem realizar novas buscas.

### Adaptive

O planejador propõe até cinco necessidades e consultas a partir da pergunta,
sem acesso ao gabarito, aos cenários ou às rubricas. Documentos explicitamente
solicitados delimitam o escopo. Necessidades textualmente iguais são
deduplicadas; redundâncias semânticas e requisitos adicionais ainda podem ocorrer.

No modo `full`, a rota `single` utiliza o contexto inicial, enquanto a rota
`iterative` seleciona evidências por necessidade e busca complementos antes da
geração. No modo `controlled`, a investigação também ocorre com a rota `single`.

O seletor retorna IDs de unidades existentes. A política reúne as passagens
por necessidade e as entrega ao gerador. Uma seleção inteiramente vazia aciona
o pacote inicial como alternativa; uma seleção não vazia pode deixar de fora
informações importantes. Portanto, encontrar evidência não garante sua entrega.

### Self-RAG

O Self-RAG planeja a resposta, gera um rascunho e verifica apoio factual e
cobertura por item. Itens reprovados ou incompletos motivam busca e revisão.
O código atual gera e verifica um candidato por item selecionado para revisão.
Verificações auxiliares de números e citações também podem rejeitar candidatos,
mas são falíveis.

| Resultado da verificação | Ação |
| --- | --- |
| Sustentado e completo | Preservar a resposta. |
| Sustentado e parcial | Buscar complemento; conservar o original se o candidato não for aceito. |
| Contradito ou incerto | Investigar; aceitar um candidato sustentado ou recusar a parte sem apoio. |

As fontes de itens sustentados ficam protegidas durante a revisão. Um candidato
que altera informações preservadas pode ser rejeitado. Essa proteção também
pode conservar um erro que tenha recebido aprovação indevida.

Há até três buscas por execução. No modo `full`, a busca inicial consome uma;
no modo `controlled`, as três são adicionais ao pacote fornecido. Há um rascunho
e uma etapa de revisão, que pode envolver uma geração por alvo. Todas as chamadas
de planejamento, seleção, verificação e geração entram na contagem de custo.
