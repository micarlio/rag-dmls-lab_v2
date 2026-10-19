# Reprodução

## 1. Consultar a análise sem gerar respostas

O notebook contém saídas salvas que podem ser consultadas sem executar células.
Para refazer a análise a partir dos registros existentes, use a pasta completa
do projeto e Python 3.12. O arquivo `configs/analysis.json` seleciona a rodada
que contém os dados e as avaliações registradas. Não precisa dos PDFs,
embeddings, Ollama, credenciais ou acesso a APIs para esta etapa.

```bash
python -m pip install -r requirements-analysis.txt
python scripts/validate_project.py
python scripts/summarize_results.py --figures
```

Os comandos validam entradas e pares, regeneram tabelas derivadas e exportam
figuras PNG/SVG. Não alteram `traces.jsonl`, `answers.csv`, manifesto ou
`review.json`. Não reavaliam semanticamente os resultados: consolidam as
anotações explícitas já feitas em `review.json`.

Para refazer a análise pelo caderno, abra `notebook.ipynb` em um kernel Python
com essas dependências e execute as células em ordem. O fluxo padrão apresenta
dados, mecanismos, caso selecionável, custos, qualidade complementar e limitações.
As cinco chaves de inferência/preparação/exportação começam em False.

## 2. Usar a análise no Colab

1. Gere ou obtenha `dist/rag-control-lab.zip` e envie o ZIP para a área de arquivos
   de uma sessão Colab. Não envie `.venv`, `.models`, `.runtime` ou `.git`.
2. Extraia em `/content`, preservando a pasta `rag-control-lab`:

```python
from zipfile import ZipFile
with ZipFile('/content/rag-control-lab.zip') as package:
    package.extractall('/content')
```

3. Em uma célula de preparação:

```python
%cd /content/rag-control-lab
!python -m pip install -r requirements-analysis.txt
```

4. Abra o notebook fornecido. Para refazer a análise, execute suas células com a
   pasta extraída disponível. A detecção inclui `/content/rag-control-lab`.
   Mantenha inferência desligada.

A preparação valida execução local e em cópia limpa sem PDFs/modelos; isso não
substitui a confirmação em uma sessão Colab real. A versão Python/dependências
efetivamente usada deve ser registrada nessa confirmação.

Para inferência no Colab, o Ollama teria de estar acessível ao kernel remoto.
`127.0.0.1:11434` no Colab não aponta para o Mac. Essa inferência remota não foi
validada e não é necessária para reproduzir as tabelas salvas.

## 3. Gerar novas respostas localmente (opcional)

Essa etapa requer os PDFs correspondentes ao manifesto e o ambiente completo.
Obtenha-os pelas fontes institucionais, preserve nomes/ordem e confira hashes.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Em um terminal, inicie o servidor com a configuração local de memória:

```bash
./scripts/start_ollama.sh
```

Em outro terminal, instale os modelos no servidor, se necessário:

```bash
ollama pull qwen2.5:3b
ollama pull embeddinggemma:300m
python scripts/run_official.py --mode controlled --dry-run
```

`--dry-run` extrai/valida o corpus e escreve seu cache/manifesto, sem chamar o
modelo. Para executar uma nova rodada explicitamente:

```bash
python scripts/run_official.py --mode controlled
```

`--mode full` seleciona recuperação natural. Não misturar as duas condições.
Novas respostas vão para outra pasta; não substitua os metadados da rodada antiga.
Retomadas exigem entradas/código/modelos compatíveis e o mesmo modo:

```bash
python scripts/run_official.py --mode controlled --resume results/runs/PASTA
```

Uma rodada concluída não é reexecutada por esse comando. A história da rodada
analisada tem uma mudança de política; leia `INTEGRIDADE.md` antes de tentar
reproduzir os números por nova inferência com o código atual.

## 4. Conferir as tabelas

`evaluation.csv` reúne perguntas, respostas e referências. As tabelas
`quality_*.csv` e `control_*.csv` apresentam os julgamentos e as métricas
registrados, sem colunas administrativas de revisão. O procedimento de avaliação
está descrito em [DESENHO_EXPERIMENTAL.md](DESENHO_EXPERIMENTAL.md).

Uma avaliação humana adicional deve ser registrada em uma planilha própria.
O script opcional `analyze_paired.py` exige essa planilha preenchida no formato
esperado por `summarize_human`; não utiliza os CSVs simplificados como se fossem
uma avaliação humana concluída.

## 5. Pacote local

```bash
python scripts/package_project.py
```

O ZIP inclui código, perguntas, fontes do corpus, notebook, resultados e figuras.
Exclui PDFs, modelos, ambiente virtual, Git, caches e histórico privado. O artigo
e a apresentação são distribuídos separadamente, em pacotes próprios de fontes
para o Overleaf. A apresentação também possui PDF e roteiro de fala.
