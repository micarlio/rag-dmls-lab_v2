# Mecanismos de controle em Adaptive RAG e Self-RAG

Projeto da DCA0305/UFRN. O `rag-control-lab` investiga quando planejamento,
busca complementar, verificação e revisão ajudam ou prejudicam a resposta,
usando como referência um baseline sem buscas adicionais. Cinco TCCs em
português constituem o corpus de teste; o objeto do estudo são os mecanismos.

## Integrantes

- Francisco Micarlos Teixeira Pinto
- Rodrigo de Menezes Souza
- Werbert Arles de Sousa Barradas

## Materiais

- [Notebook com análise e resultados salvos](notebook.ipynb).
- [Artigo em PDF](artigo.pdf).
- [Apresentação em PDF](apresentacao.pdf).

## O que foi medido

- 20 perguntas, quatro cenários por documento: direto, duas etapas, distrator
  e não respondível; uma semente (42), temperatura zero.
- Quatro variantes: LLM puro, baseline, Adaptive e Self-RAG.
- Avaliação controlada: mesmo pacote inicial construído e fornecido às variantes
  RAG; buscas adicionais usam o corpus comum. LLM puro permanece sem documentos.
  O desempenho da recuperação inicial natural não foi avaliado nesta condição.
- Gerador/controladores `qwen2.5:3b` e embeddings `embeddinggemma:300m`, Ollama
  local no Apple M1 de 8 GB. Recuperação híbrida e 679 chunks.

O foco principal é seguir **lacuna → decisão → evidência → efeito → custo**.
Correção integral e cobertura da resposta final são medidas complementares.
As políticas são adaptações didáticas por prompts, sem treinamento dos métodos originais.

## Resultados e limites

Nas cinco perguntas de duas etapas, ambos recuperam algum complemento relevante.
Algum complemento chega ao gerador em 4/5 casos no Adaptive e 5/5 no Self-RAG;
contexto suficiente para todos os critérios chega em 1/5 e 3/5, respectivamente.
Isso mede evidência, não acerto final. Q02 mostra reparo útil do Self-RAG; Q04
mostra revisão prejudicial a partir da confusão entre TTL e latência.

Qualidade final e custo médio por resposta:

| Variante | Chamadas LLM | Latência (s) | Acerto integral | Critérios atendidos |
| --- | ---: | ---: | ---: | ---: |
| LLM puro | 1,00 | 5,12 | 2/20 | 12,5% |
| Baseline | 1,00 | 13,04 | 8/20 | 55,0% |
| Adaptive | 7,05 | 70,19 | 4/20 | 35,8% |
| Self-RAG | 20,40 | 159,84 | 7/20 | 56,7% |

Acerto integral exige atender todos os critérios sem erro material.
“Critérios atendidos” é a fração média de critérios plenamente atendidos por
resposta. Encontrar complementos não garantiu superar o baseline na qualidade
final; os controladores também exigiram mais chamadas e tempo.

Nas cinco perguntas não respondíveis, houve recusa total ao pedido original em
5/5 no baseline, 4/5 no Self-RAG e 3/5 no Adaptive e no LLM puro. Recusa total
não equivale a acerto integral: a avaliação também considera a justificativa.
Recusas de requisitos extras criados pelo planejador não entram nessa contagem.

Avaliação retrospectiva de 40 cadeias de controle e 80 respostas finais.
O procedimento e a análise completa estão em
[ANALISE_CONTROLE.md](docs/ANALISE_CONTROLE.md).
A configuração e a implementação das variantes estão em
[DESENHO_EXPERIMENTAL.md](docs/DESENHO_EXPERIMENTAL.md).

**A rodada reúne revisões do Self-RAG em lote e por item.** As médias descrevem
o conjunto observado, sem isolar o efeito de uma política uniforme de revisão.
As formas de revisão por pergunta estão registradas em
[self_revision_modes.csv](results/runs/20261018T182531677492Z_81b2dd68bc/self_revision_modes.csv).

## Organização

```text
rag-control-lab/
├── artigo.pdf                 # artigo do projeto
├── apresentacao.pdf           # slides da apresentação
├── notebook.ipynb             # leitura e análise; inferência opcional
├── rag_lab.py                 # corpus, recuperação, geração e execução
├── rag_control.py             # políticas de controle
├── reporting.py               # apresentação offline e figuras
├── csv_output.py              # esquemas e escrita dos CSVs
├── configs/                   # experimento e seleção da rodada analisada
├── corpus/                    # manifesto, fontes e PDFs locais
├── prompts/                   # instruções dos modelos
├── questions.json             # perguntas, gabaritos e critérios da coleta
├── results/
│   ├── runs/                  # uma rodada analisada, dados brutos e tabelas
│   └── figures/               # figuras PNG/SVG regeneráveis
├── scripts/                   # executar, analisar, validar e empacotar
└── docs/                      # método, implementação, perguntas e análise
```
