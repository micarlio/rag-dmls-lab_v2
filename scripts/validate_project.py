"""Verifica estrutura, dados e notebook da entrega sem modelos, PDFs ou escrita."""
import argparse
import ast
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reporting import load_analysis
from csv_output import EVALUATION_FIELDS, validate_columns


def validate(root=ROOT, *, strict_sources=False):
    root=Path(root)
    required=['README.md','notebook.ipynb','rag_lab.py','rag_control.py','reporting.py','csv_output.py',
              'requirements.txt','requirements-analysis.txt','configs/analysis.json','configs/experiment.json',
              'questions.json','corpus/manifest.csv','docs/README.md','docs/ANALISE_CONTROLE.md',
              'docs/PERGUNTAS.md','docs/DESENHO_EXPERIMENTAL.md']
    missing=[p for p in required if not (root/p).is_file()]
    if missing:
        raise ValueError('Arquivos ausentes: '+', '.join(missing))
    report=load_analysis(root)
    signature=report['manifest']['signature']
    source_differences=[relative for relative,sha in signature['source_hashes'].items()
                        if not (root/relative).is_file() or
                        hashlib.sha256((root/relative).read_bytes()).hexdigest()!=sha]
    if strict_sources and source_differences:
        raise ValueError('Fontes atuais diferem das registradas na coleta: '+', '.join(source_differences))
    current=json.loads((root/'questions.json').read_text())
    if current!=signature['questions']:
        raise ValueError('As perguntas divergem do manifesto analisado.')
    notebook=json.loads((root/'notebook.ipynb').read_text())
    flags={'ENABLE_INFERENCE','PREPARE_CORPUS','BUILD_INDEX','RUN_EXPERIMENT','EXPORT_FIGURES'}
    seen={}
    errors=[]
    for cell in notebook['cells']:
        if cell['cell_type']!='code':continue
        tree=ast.parse(''.join(cell['source']))
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and target.id in flags:
                        seen[target.id]=isinstance(node.value,ast.Constant) and node.value.value is False
        errors.extend(o for o in cell.get('outputs',[]) if o.get('output_type')=='error')
    if set(seen)!=flags or not all(seen.values()) or errors:
        raise ValueError('Notebook tem inferência/exportação ativa ou saída de erro.')
    for path in report['run_dir'].glob('*.csv'):
        with path.open(newline='',encoding='utf-8') as stream:
            header=next(csv.reader(stream))
        validate_columns(header)
        if path.name=='evaluation.csv' and header!=list(EVALUATION_FIELDS):
            raise ValueError('evaluation.csv não corresponde ao esquema de exportação.')
    with (report['run_dir']/'evaluation.csv').open(newline='',encoding='utf-8') as stream:
        evaluation=list(csv.DictReader(stream))
    keys=lambda rows:{(r['question_id'],r['variant'],int(r['repetition'])) for r in rows}
    if len(evaluation)!=len(report['answers']) or keys(evaluation)!=keys(report['answers'].to_dict('records')):
        raise ValueError('evaluation.csv não cobre exatamente as respostas registradas.')
    modes=report['revision_modes'].revision_mode_observed.value_counts().to_dict()
    return {'status':'ok','answers':len(report['answers']),'questions':len(report['questions']),
            'control_cases':len(report['control_cases']),'support_checks':len(report['checks']),
            'evaluations':len(report['quality']),'csv_headers_consistent':True,'default_inference':False,
            'source_code_matches_run':not source_differences,'source_files_different_from_run':source_differences,
            'self_revision_modes_observed':modes,
            'limitations':['Avaliação retrospectiva sem confirmação humana independente.',
                           'Self-RAG reúne revisão em lote e por item.',
                           'Três execuções do baseline e entregas acadêmicas ainda pendentes.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict-sources',action='store_true',
                        help='Exige que o código atual seja idêntico ao registrado na coleta.')
    args=parser.parse_args()
    print(json.dumps(validate(strict_sources=args.strict_sources),ensure_ascii=False,indent=2))
