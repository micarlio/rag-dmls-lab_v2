# Corpus de teste

Cinco TCCs fornecidos pelo estudante, identificados como DOC01 a DOC05.
São 286 páginas físicas, 269 com texto extraível e 679 chunks. O corpus serve
para experimentar mecanismos de controle; o estudo não é sobre aplicações acadêmicas.

`manifest.csv` registra nomes, fontes institucionais, títulos e SHA-256.
`documentos/LEIA-ME.txt` conserva os dados fornecidos com a coleção.
Os PDFs estão disponíveis localmente em `documentos/` e ignorados pelo Git/ZIP.
Use os links do manifesto para obtê-los e confira os hashes antes de nova inferência.
Analisar os resultados salvos não exige esses arquivos.

A ordem alfabética dos nomes determina DOC01 a DOC05. Renomear ou substituir
PDFs muda o fingerprint. Páginas são físicas, começando em 1. Chunks de 900
caracteres, sobreposição de 150, nunca cruzam documento/página; IDs incluem
documento, página e posição. O índice usa recuperação híbrida e janelas expandidas.

A extração foi conferida na análise, mas contém artefatos: colunas podem perder
estrutura e a conjunção e pode aparecer colada a pascal_stop. Os casos foram
preservados; não se fez correção retroativa do corpus da coleta.

Não há prova de ausência/presença desses documentos nos dados de treinamento
do modelo. O controle LLM puro mede respostas sem documentos, não contaminação.
As condições de redistribuição dos PDFs permanecem a conferir antes de eventual
publicação; esta preparação não publica nem redistribui os arquivos PDF.
