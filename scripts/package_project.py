"""Empacota a pasta de entrega, excluindo PDFs, Git, ambientes e histórico local."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
FILES=['.gitignore','README.md','notebook.ipynb','requirements.txt','requirements-analysis.txt',
       'rag_lab.py','rag_control.py','reporting.py','csv_output.py','questions.json']
DIRECTORIES=['configs','docs','prompts','scripts','tests','corpus','results']


def delivery_files(root=ROOT):
    root=Path(root)
    found={root/p for p in FILES}
    for dirname in DIRECTORIES:
        for p in (root/dirname).rglob('*'):
            rel=p.relative_to(root)
            if (not p.is_file() or p.suffix.lower() in {'.pdf','.pyc'} or
                    any(part.startswith('.') and part not in {'.gitkeep'} for part in rel.parts) or
                    '__pycache__' in rel.parts or 'pilot' in rel.parts):
                continue
            found.add(p)
    if any(not p.is_file() for p in found):
        raise ValueError('A estrutura de entrega está incompleta.')
    return sorted(found)


def package(destination=None):
    from validate_project import validate
    validate(ROOT)
    target=Path(destination) if destination else ROOT/'dist/rag-control-lab.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(target,'w',compression=ZIP_DEFLATED) as archive:
        for path in delivery_files():
            archive.write(path,Path('rag-control-lab')/path.relative_to(ROOT))
    print('Pacote local:',target)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    package(args.output)
