# Resultados da condição controlada

`configs/analysis.json` seleciona `runs/20261018T182531677492Z_81b2dd68bc`.
Há 80 respostas: 20 perguntas x quatro variantes x semente 42.

## Dados e avaliação

- `run_manifest.json`: configuração, corpus, perguntas e hashes finais.
- `traces.jsonl`: fonte primária, com decisões, consultas, passagens e eventos.
- `answers.csv` e `<variante>_r1.csv`: respostas e medidas por pergunta.
- `evaluation.csv`: perguntas, respostas e referências para avaliação.
- `review.json`: critérios, avaliações e metadados de origem.
- `control_*.csv`: mecanismos, apoio, contexto e custo.
- `quality_*.csv`: qualidade final e comparação com o baseline.
- `self_revision_modes.csv`: forma de revisão identificada pelos eventos.
- `figures/` (na pasta results): figuras PNG/SVG

O procedimento de avaliação está descrito em
[DESENHO_EXPERIMENTAL.md](../docs/DESENHO_EXPERIMENTAL.md).
Os CSVs apresentam os dados e as métricas; a identificação do procedimento
de avaliação fica na metodologia e nos metadados de `review.json`.

## Reproduzir

```bash
python scripts/validate_project.py
python scripts/summarize_results.py --figures
```
