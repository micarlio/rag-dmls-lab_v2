# Integridade e proveniência da execução

## O que foi preservado

A organização da entrega não alterou `rag_lab.py`, `rag_control.py`, prompts,
`configs/experiment.json`, `questions.json`, manifesto do corpus, dados brutos
ou revisão humana. O registro de preparação e hashes está no histórico local
`.runtime/final_preparation/`. Dados anteriores e scripts exploratórios foram
movidos para seu arquivo local, conferidos byte a byte.

A rodada ativa tem 80 combinações únicas, 20 por variante. Perguntas, corpus e
fontes atuais conferem com o manifesto final. A análise valida também hashes dos
dados brutos e das respostas. A análise não preenche os campos de revisão humana.

## Mudança que os hashes finais não explicam sozinhos

O fingerprint observado antes da retomada era `81b2dd68bc...`; o manifesto final
registra `866680b140...`, na mesma pasta. As linhas finais compartilham o novo
fingerprint. Isso demonstra consistência atual dos metadados, não congelamento
histórico nem que todas as respostas foram produzidas pela política atual.

A inspeção de eventos esclarece uma mudança concreta: alguns candidatos de
revisão geram vários itens em uma chamada, enquanto outros geram uma chamada
por item. O código atual em `rag_control.py` usa geração por item.

| Forma comprovada pelos eventos | Perguntas Self-RAG |
| --- | --- |
| Revisão conjunta de múltiplos alvos | Q02, Q03, Q06, Q07, Q08 |
| Revisão com uma chamada por alvo | Q10, Q11, Q14, Q15, Q16, Q17, Q18, Q19 |
| Um alvo: políticas indistinguíveis pelos eventos | Q04, Q12, Q13, Q20 |
| Sem revisão | Q01, Q05, Q09 |

Exemplo: Q02 tem dois itens-alvo e uma geração de revisão com dois itens.
Q10 tem cinco alvos e cinco gerações de revisão com um item cada. O arquivo
`interruption.json` conserva uma tentativa de Q10 truncada ao gerar itens juntos.
O desenho dos eventos é compatível com a mudança para evitar esse truncamento.
Não há registro suficiente para reconstruir toda a operação que atualizou
fingerprints ou certificar equivalência do código entre todas as tentativas.

`self_revision_modes.csv` é derivado dos eventos, não de suposições sobre a ordem
das perguntas. A classificação também é mostrada no notebook.

## Consequências para o artigo

- Tratar a coleta como exploratória, com a alteração de revisão explicitada.
- Usar rastros por pergunta para demonstrar mecanismos observados.
- Não apresentar custos agregados do Self-RAG como custo de política uniforme.
- Não atribuir diferenças ao hardware, ao modelo ou ao controle isoladamente
  sem um desenho que separe esses fatores.
- Não modificar retrospectivamente fontes, respostas, hashes ou entradas para
  esconder a alteração. A organização atual preserva os registros existentes.

Essa ressalva não apaga casos observáveis como o reparo da Q02 ou a regressão
da Q04. Ela limita comparações globais e a reprodução por nova inferência do
conjunto inteiro sob o código atual. A consolidação offline dos dados é reproduzível.

## Verificação

```bash
python scripts/validate_project.py
python scripts/summarize_results.py
```

Os testes incluem rejeição de rastros alterados, pares ausentes, testemunhas
inventadas e alegação de entrega sem fonte no contexto. Os hashes brutos
continuam os mesmos após preparar as tabelas, figuras e notebook.
