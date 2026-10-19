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


def validate(root=ROOT):
    root=Path(root)
    required=['README.md','notebook.ipynb','rag_lab.py','rag_control.py','reporting.py',
              'requirements.txt','requirements-analysis.txt','configs/analysis.json','configs/experiment.json',
              'questions.json','corpus/manifest.csv','docs/ANALISE_CONTROLE.md','docs/INTEGRIDADE.md',
              'docs/REPRODUCAO.md','docs/DESENHO_EXPERIMENTAL.md']
    missing=[p for p in required if not (root/p).is_file()]
    if missing:
        raise ValueError('Arquivos ausentes: '+', '.join(missing))
    report=load_analysis(root)
    signature=report['manifest']['signature']
    for relative,sha in signature['source_hashes'].items():
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=sha:
            raise ValueError('Fonte do experimento mudou: '+relative)
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
    evaluation=list(csv.DictReader((report['run_dir']/'evaluation.csv').open()))
    human_count=sum(r.get('human_verdict', '') in {'CORRECT','INCORRECT'} for r in evaluation)
    modes=report['revision_modes'].revision_mode_observed.value_counts().to_dict()
    return {'status':'ok','answers':len(report['answers']),'questions':len(report['questions']),
            'control_cases':len(report['control_cases']),'support_checks':len(report['checks']),
            'human_reviews_completed':human_count,'default_inference':False,
            'self_revision_modes_observed':modes,
            'limitations':['Avaliação retrospectiva sem confirmação humana independente.',
                           'Self-RAG reúne revisão em lote e por item.',
                           'Três execuções do baseline e entregas acadêmicas ainda pendentes.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(validate(),ensure_ascii=False,indent=2))
