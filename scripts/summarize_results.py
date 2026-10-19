"""Reproduz tabelas e figuras a partir dos registros, sem LLM ou PDFs."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reporting import load_analysis, plot_results
from csv_output import write_dataframe
from scripts.analyze_control import analyze as analyze_control
from scripts.analyze_quality import analyze as analyze_quality


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',help='Pasta de resultados; padrão em configs/analysis.json.')
    parser.add_argument('--figures',action='store_true',help='Exportar PNG/SVG em results/figures.')
    args=parser.parse_args()
    report=load_analysis(ROOT,args.run)
    analyze_control(report['run_dir'])
    analyze_quality(report['run_dir'])
    modes=report['revision_modes'].copy()
    modes['items_per_generator_call']=modes.items_per_generator_call.map(str)
    write_dataframe(modes,report['run_dir']/'self_revision_modes.csv')
    write_dataframe(report['two_step'],report['run_dir']/'control_two_step.csv')
    if args.figures:
        import matplotlib.pyplot as plt
        for fig in plot_results(report,ROOT/'results/figures').values():
            plt.close(fig)
    print('Análise offline concluída. Registros de execução e julgamentos preservados.')


if __name__=='__main__':main()
