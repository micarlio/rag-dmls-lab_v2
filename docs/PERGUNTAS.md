# Perguntas da Avaliação Controlada (Família 4)

> **Nota de auditoria:** este arquivo reproduz o conjunto congelado da coleta,
> inclusive redações/referências problemáticas. Na Q02, compartilha-se a planilha
> com a conta de serviço, não o JSON com a planilha. Q08, Q11, Q14, Q16, Q17 e Q19
> têm ressalvas de contexto/referência/extração documentadas em ANALISE_CONTROLE.md.
> Não interpretar rótulos planejados como adequação automaticamente comprovada.

20 perguntas congeladas em `questions.json`, cobrindo 5 TCCs × 4 cenários experimentais.

Cada documento possui exatamente 1 pergunta de cada situação:
- `direct`: resposta direta (fato localizado em um único trecho; baseline pode vencer em custo)
- `two_step`: busca em duas etapas (contexto inicial parcial; evidência complementar no corpus)
- `distractor`: trechos que podem confundir (distinção entre considerado vs adotado, presente vs futuro, métricas/condições)
- `unanswerable`: informação ausente (medição não realizada no TCC; mede recusa correta)

---

## Q01 — DOC01 — direct (direct)

No dashboard da Biblioteca Padre Jaime Diniz (DOC01), por quantos segundos o cache da função buscar_dados_brutos_da_planilha() reaproveita a chamada à API?

**Referência:** A chamada é reaproveitada por até 120 segundos, com @st.cache_data(ttl=120).

**Rubrica:**

- Informar 120 segundos (ou @st.cache_data(ttl=120)); não confundir TTL com latência de consulta.

**Páginas físicas:** 27

**Contexto inicial controlado:** `DOC01:P0027:C0002`

**Justificativa de seleção:** Situação 1 (resposta direta): fato localizado em um único trecho. Baseline competente deve vencer em custo.

---

## Q02 — DOC01 — two_step (synthesis)

No projeto da Biblioteca (DOC01), como o Gspread autentica o acesso à planilha e por que a Google Drive API precisou ser ativada junto à Google Sheets API?

**Referência:** A autenticação é realizada por conta de serviço com chave JSON compartilhada com a planilha com permissão de leitura. A Google Drive API é necessária porque o Gspread a utiliza para localizar a planilha pelo nome antes de acessá-la pela Sheets API.

**Rubrica:**

- Identificar autenticação via conta de serviço com chave JSON e compartilhamento da planilha com permissão de leitura.
- Explicar que a Google Drive API é usada pelo Gspread para localizar a planilha pelo nome antes do acesso pela Sheets API.

**Páginas físicas:** 27, 26

**Contexto inicial controlado:** `DOC01:P0027:C0001`

**Justificativa de seleção:** Situação 2 (busca em duas etapas): o contexto inicial traz a conta de serviço e a chave, mas a justificativa da Drive API exige busca complementar.

---

## Q03 — DOC01 — distractor (synthesis)

No dashboard da biblioteca (DOC01), como o carregamento trata datas inválidas da planilha e como a interface reage a um intervalo de consulta inválido? Distinga o tratamento dos dados do tratamento dos filtros.

**Referência:** No carregamento, pd.to_datetime com errors="coerce" converte datas inválidas em NaT. Na interface, se a data inicial for maior que a final ou anterior à doação mais antiga, o sistema rejeita o intervalo e mantém o último estado válido.

**Rubrica:**

- Identificar conversão de datas inválidas/ausentes para NaT por pd.to_datetime com errors="coerce" na carga dos dados.
- Identificar que na interface intervalo inválido (início > fim ou anterior à primeira doação) é rejeitado e mantém o último estado válido.
- Distinguir a limpeza das células na carga da validação do intervalo nos filtros da interface.

**Páginas físicas:** 28, 36

**Contexto inicial controlado:** `DOC01:P0028:C0002, DOC01:P0036:C0002`

**Justificativa de seleção:** Situação 3 (trechos que podem confundir): exige separar tratamento das células na carga e tratamento do intervalo nos controles visuais.

---

## Q04 — DOC01 — unanswerable (unanswerable)

No sistema da Biblioteca Padre Jaime Diniz (DOC01), qual foi a latência mediana de consulta ao dashboard, em milissegundos, medida em um teste de desempenho?

**Referência:** O documento não informa uma medição de latência mediana em milissegundos. Não é possível fornecer esse valor.

**Rubrica:**

- Declarar que a medição solicitada não é informada no documento.
- Não apresentar o TTL do cache (120 s) ou prazos do fluxo patrimonial como latência de consulta.

**Páginas físicas:** 27, 53

**Contexto inicial controlado:** `DOC01:P0027:C0002, DOC01:P0053:C0001`

**Justificativa de seleção:** Situação 4 (informação ausente): pedido plausível; o contexto tem o TTL de 120s que pode induzir falsa resposta se o modelo não abstiver.

---

## Q05 — DOC02 — direct (direct)

No projeto do forno solar (DOC02), qual software foi usado para projetar o par de engrenagens cilíndricas de dentes retos?

**Referência:** Autodesk Fusion 360.

**Rubrica:**

- Identificar Autodesk Fusion 360.

**Páginas físicas:** 29

**Contexto inicial controlado:** `DOC02:P0029:C0001`

**Justificativa de seleção:** Situação 1 (resposta direta): identificação direta de software em trecho único.

---

## Q06 — DOC02 — two_step (synthesis)

No forno solar (DOC02), qual particularidade mecânica do sistema de transmissão por engrenagens exigiu compensação e como ela foi corrigida no código do algoritmo?

**Referência:** O par de engrenagens inverte o sentido de rotação entre o servomotor e a câmara giratória. A correção no código consistiu em inverter o sinal da variável de correção do servomotor horizontal.

**Rubrica:**

- Identificar que o par de engrenagens inverte o sentido de rotação (a câmara gira no sentido oposto ao servomotor).
- Identificar que a correção no código consistiu em inverter o sinal da variável de correção do servo horizontal.

**Páginas físicas:** 29, 33

**Contexto inicial controlado:** `DOC02:P0029:C0001`

**Justificativa de seleção:** Situação 2 (busca em duas etapas): o contexto inicial menciona as engrenagens, mas a inversão e o ajuste de sinal no código estão na Seção 3.3.

---

## Q07 — DOC02 — distractor (synthesis)

No forno solar (DOC02), por que a variante de rotação contínua do servomotor MG996R não é adequada ao rastreamento e como foi reparada a falha interna do servomotor horizontal observada na bancada?

**Referência:** A variante de rotação contínua não realiza posicionamento angular. Na bancada, rompeu-se uma engrenagem interna de nylon, substituída por uma engrenagem metálica de um servo reserva compatível.

**Rubrica:**

- Distinguir rotação contínua de posicionamento angular.
- Identificar rompimento da engrenagem interna de nylon do servomotor.
- Identificar substituição por engrenagem metálica de servo reserva; não confundir com as engrenagens externas de PLA.

**Páginas físicas:** 25, 30

**Contexto inicial controlado:** `DOC02:P0025:C0002, DOC02:P0030:C0001`

**Justificativa de seleção:** Situação 3 (trechos que podem confundir): distingue características de atuadores e causas de falha interna (nylon) vs engrenagens externas (PLA).

---

## Q08 — DOC02 — unanswerable (unanswerable)

No protótipo de forno solar (DOC02), qual temperatura interna máxima, em graus Celsius, foi medida com rastreamento ativo em comparação com o forno fixo?

**Referência:** O trabalho não apresenta medição de temperaturas máximas comparativas entre forno fixo e com rastreamento. Essa comparação térmica é proposta para trabalhos futuros.

**Rubrica:**

- Reconhecer a ausência de temperaturas máximas comparativas medidas.
- Não apresentar projeções ou valores estimados como medição experimental.

**Páginas físicas:** 34, 37

**Contexto inicial controlado:** `DOC02:P0034:C0001, DOC02:P0037:C0001`

**Justificativa de seleção:** Situação 4 (informação ausente): ensaio térmico plausível, mas explicitamente deixado para trabalhos futuros.

---

## Q09 — DOC03 — direct (direct)

No Organiz.ai (DOC03), qual framework implementa a camada de apresentação e sua interface conversacional?

**Referência:** Streamlit.

**Rubrica:**

- Identificar Streamlit.

**Páginas físicas:** 25

**Contexto inicial controlado:** `DOC03:P0025:C0001`

**Justificativa de seleção:** Situação 1 (resposta direta): identificação pontual da camada visual.

---

## Q10 — DOC03 — two_step (synthesis)

No Organiz.ai (DOC03), qual é o papel do orquestrador no fluxo de mensagens e quais verificações nos testes automatizados confirmaram sua capacidade de localizar os agentes especializados?

**Referência:** O orquestrador coordena a comunicação interpretando intenções e direcionando requisições aos agentes especializados sem executar regras de negócio. Nos testes, verificou-se o endpoint /agents com a lista dos agentes e confirmou-se que as URLs registradas eram alcançáveis.

**Rubrica:**

- Identificar que o orquestrador interpreta intenções e encaminha requisições ao especialista adequado sem executar diretamente regras de negócio.
- Identificar que os testes confirmaram o registro dos agentes no endpoint /agents (com URL e descrição) e a alcançabilidade das URLs registradas.

**Páginas físicas:** 25, 31

**Contexto inicial controlado:** `DOC03:P0025:C0002`

**Justificativa de seleção:** Situação 2 (busca em duas etapas): o contexto inicial descreve o papel conceitual do orquestrador; os testes empíricos de alcançabilidade de URLs estão na Seção 4.1.

---

## Q11 — DOC03 — distractor (synthesis)

Na avaliação do Organiz.ai (DOC03), qual critério determinava a aprovação de um teste automatizado e qual foi a causa atribuída à única falha observada na suíte?

**Referência:** A aprovação exigia satisfazer todas as asserções (status HTTP esperado, campos obrigatórios e tipos de dados). A única falha decorreu de indisponibilidade temporária da API do provedor (Groq/LLM), e não de falha na arquitetura interna.

**Rubrica:**

- Identificar que a aprovação exige cumprimento de todas as asserções: status HTTP, campos obrigatórios e tipos de dados.
- Identificar que a única falha ocorreu por indisponibilidade temporária da API/provedor externo (Groq), distinguindo-a de defeito na arquitetura interna.

**Páginas físicas:** 30, 41

**Contexto inicial controlado:** `DOC03:P0030:C0001, DOC03:P0041:C0003`

**Justificativa de seleção:** Situação 3 (trechos que podem confundir): exige distinguir critérios da suíte de teste de limitações externas de infraestrutura.

---

## Q12 — DOC03 — unanswerable (unanswerable)

No Organiz.ai (DOC03), qual percentual de redução dos esquecimentos foi medido em participantes diagnosticados com TDAH após usar o protótipo?

**Referência:** Esse percentual não foi medido: a avaliação foi puramente técnica e automatizada sobre a infraestrutura, sem testes clínicos ou medição com participantes reais diagnosticados com TDAH.

**Rubrica:**

- Declarar a ausência da medição com participantes diagnosticados.
- Não utilizar a taxa de aprovação dos testes de software como percentual de redução de esquecimentos.

**Páginas físicas:** 31, 41

**Contexto inicial controlado:** `DOC03:P0031:C0002, DOC03:P0041:C0003`

**Justificativa de seleção:** Situação 4 (informação ausente): contrasta validação técnica funcional com eficácia assistiva clínica não medida.

---

## Q13 — DOC04 — direct (direct)

No agente de interfaces gráficas estudado no DOC04, qual ação sinaliza o encerramento de uma tarefa?

**Referência:** A ação terminate.

**Rubrica:**

- Identificar a ação terminate.

**Páginas físicas:** 61

**Contexto inicial controlado:** `DOC04:P0061:C0002`

**Justificativa de seleção:** Situação 1 (resposta direta): identificação unívoca de ação final do agente.

---

## Q14 — DOC04 — two_step (synthesis)

No estudo de navegação (DOC04), como variaram as taxas gerais no ScreenSpot-Pro e no OSWorld-Verified entre o modelo base e o treinado, e qual comportamento nas trajetórias explica o resultado do OSWorld?

**Referência:** No ScreenSpot-Pro a taxa geral subiu de 33,70% para 38,70%. No OSWorld-Verified caiu de 15,10% para 11,31%. Essa regressão decorreu da falha em reconhecer a conclusão da tarefa: o modelo treinado atinge o objetivo mas prossegue reabrindo menus e repetindo ações.

**Rubrica:**

- ScreenSpot-Pro: subiu de 33,70% para 38,70%.
- OSWorld-Verified: caiu de 15,10% para 11,31%.
- Explicar a regressão por falha de terminação (continuar agindo após atingir o objetivo), e não por perda de ancoramento/localização.

**Páginas físicas:** 59, 61

**Contexto inicial controlado:** `DOC04:P0059:C0002`

**Justificativa de seleção:** Situação 2 (busca em duas etapas): o contexto inicial traz a Tabela 4 do ScreenSpot-Pro; a análise das trajetórias do OSWorld requer busca adicional.

---

## Q15 — DOC04 — distractor (synthesis)

No DOC04, que diferença na proporção dos alvos da ação terminate existe entre os treinos principal e preliminar, e por que essa proporção é maior no preliminar?

**Referência:** A ação terminate representa cerca de 5% dos alvos no treino principal e cerca de 30% no preliminar. A proporção é maior no preliminar pela exclusão das ações de ancoramento dos alvos, o que reduz o denominador de ações.

**Rubrica:**

- Identificar aproximadamente 5% no treino principal e cerca de 30% no preliminar.
- Explicar que a maior proporção no preliminar decorre da exclusão das ações de ancoramento (reduzindo o denominador de ações).

**Páginas físicas:** 64

**Contexto inicial controlado:** `DOC04:P0064:C0002`

**Justificativa de seleção:** Situação 3 (trechos que podem confundir): exige interpretar contraste estrutural de dados e evitar falsa correlação causal.

---

## Q16 — DOC04 — unanswerable (unanswerable)

No estudo do DOC04, qual foi o efeito isolado do aumento do batch size, em pontos percentuais no OSWorld-Verified, medido por uma ablação controlada?

**Referência:** Não há efeito numérico isolado medido por ablação controlada: múltiplos fatores variaram simultaneamente entre as duas configurações, e estudos de ablação foram apenas propostos para trabalhos futuros.

**Rubrica:**

- Não apresentar um efeito numérico isolado para o batch size.
- Declarar que não houve ablação controlada para isolar esse fator e que múltiplos parâmetros variaram simultaneamente.

**Páginas físicas:** 59, 66

**Contexto inicial controlado:** `DOC04:P0059:C0002, DOC04:P0066:C0002`

**Justificativa de seleção:** Situação 4 (informação ausente): investiga capacidade de recusa diante de deltas agregados não atribuíveis a uma variável isolada.

---

## Q17 — DOC05 — direct (direct)

No perfilamento do RTM (DOC05), quais macros delimitam o início e o fim de uma região instrumentada manualmente?

**Referência:** pascal_start marca o início e pascal_stop marca o fim.

**Rubrica:**

- Identificar pascal_start para início e pascal_stop para fim.

**Páginas físicas:** 37

**Contexto inicial controlado:** `DOC05:P0037:C0001`

**Justificativa de seleção:** Situação 1 (resposta direta): identificação pontual de sintaxe de instrumentação.

---

## Q18 — DOC05 — two_step (synthesis)

No RTM (DOC05), como a diretiva single contribui para gargalos na propagação e no swap, e qual estratégia foi proposta para reduzir a ociosidade das threads?

**Referência:** A diretiva single serializa a inserção da fonte e o swap de ponteiros com barreiras de sincronização. Para reduzir a ociosidade das threads, foi proposta como trabalho futuro a refatoração com o modelo de tarefas (tasking) do OpenMP.

**Rubrica:**

- Identificar que a diretiva single torna a inserção da fonte e/ou o swap sequenciais com barreiras implícitas de sincronização.
- Identificar a proposta de refatoração com o modelo de tarefas (tasking) do OpenMP para mitigar a ociosidade.

**Páginas físicas:** 43, 47

**Contexto inicial controlado:** `DOC05:P0043:C0002`

**Justificativa de seleção:** Situação 2 (busca em duas etapas): o contexto inicial detalha o gargalo de single; a proposta de tasking está na conclusão (Capítulo 7).

---

## Q19 — DOC05 — distractor (synthesis)

Na análise do RTM (DOC05), como a eficiência paralela é definida e qual ressalva metodológica existe sobre a execução de referência adotada nos experimentos?

**Referência:** A eficiência é definida como o speedup dividido pelo número de núcleos (E_p = S_p / p). A ressalva é que a referência experimental foi a execução do próprio código paralelo com 1 thread (embutindo overhead do OpenMP) e não uma versão puramente sequencial, escolha feita para viabilizar a automação com o PaScal Analyzer.

**Rubrica:**

- Eficiência igual a speedup dividido pelo número de núcleos/recursos (E_p = S_p / p).
- Referência adotada: código paralelo com 1 thread (embutindo overhead do OpenMP), e não código puramente sequencial.
- Relacionar essa escolha à automação dos experimentos pelo PaScal Analyzer.

**Páginas físicas:** 23, 37

**Contexto inicial controlado:** `DOC05:P0023:C0003, DOC05:P0037:C0001`

**Justificativa de seleção:** Situação 3 (trechos que podem confundir): exige associar definição matemática à decisão metodológica de referência experimental.

---

## Q20 — DOC05 — unanswerable (unanswerable)

No RTM (DOC05), qual speedup foi medido após a refatoração com o modelo de tarefas (tasking) do OpenMP?

**Referência:** Nenhum speedup foi medido após essa refatoração: o uso de tasking é apenas uma proposta de trabalho futuro, cuja implementação e comparação de desempenho ainda seriam realizadas.

**Rubrica:**

- Declarar ausência de resultado medido após a refatoração com tasking.
- Reconhecer que tasking é apenas uma proposta de trabalho futuro.

**Páginas físicas:** 47

**Contexto inicial controlado:** `DOC05:P0047:C0002`

**Justificativa de seleção:** Situação 4 (informação ausente): distingue proposta metodológica futura de medição já realizada.

---

