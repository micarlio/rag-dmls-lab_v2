"""Compara as avaliações registradas e exporta as tabelas pareadas de qualidade."""
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from csv_output import write_dataframe


def paired_tables(frame):
    required={'question_id','repetition','variant','verdict','criteria_met','material_error',
              'llm_calls','latency_seconds','note'}
    missing=required-set(frame.columns)
    if missing:
        raise ValueError('Faltam colunas na avaliação: '+', '.join(sorted(missing)))
    if not frame.verdict.isin(['CORRECT','INCORRECT']).all():
        raise ValueError('Complete a avaliação antes da comparação pareada.')
    if not frame.material_error.isin([True,False]).all():
        raise ValueError('material_error deve conter valores booleanos.')
    keys=['question_id','repetition']
    fields=keys+['verdict','criteria_met','material_error','llm_calls','latency_seconds','note']
    baseline=frame.loc[frame.variant.eq('baseline'),fields]
    if baseline.empty:
        raise ValueError('Falta baseline para comparação.')
    rows=[]
    for variant in ['adaptive','self_rag']:
        control=frame.loc[frame.variant.eq(variant),fields]
        if control.empty:
            raise ValueError('Falta a variante para comparação: '+variant)
        pairs=baseline.merge(control,on=keys,how='outer',suffixes=('_baseline','_control'),validate='one_to_one',indicator=True)
        if not pairs['_merge'].eq('both').all():
            raise ValueError('Comparação exige os mesmos pares de pergunta/repetição em cada variante.')
        for row in pairs.to_dict('records'):
            before=row['verdict_baseline']=='CORRECT'
            after=row['verdict_control']=='CORRECT'
            outcome=('improved' if after else 'tied_incorrect') if not before else ('tied_correct' if after else 'regressed')
            rows.append({**{k:row[k] for k in keys},'variant':variant,'outcome':outcome,
                         'criteria_met_delta':row['criteria_met_control']-row['criteria_met_baseline'],
                         'material_error_removed':row['material_error_baseline'] and not row['material_error_control'],
                         'llm_calls_delta':row['llm_calls_control']-row['llm_calls_baseline'],
                         'latency_delta_seconds':row['latency_seconds_control']-row['latency_seconds_baseline'],
                         'baseline_note':row['note_baseline'],'control_note':row['note_control']})
    paired=pd.DataFrame(rows)
    summaries=[]
    if not paired.empty:
        for variant,group in paired.groupby('variant'):
            counts=group.outcome.value_counts()
            improved=int(counts.get('improved',0));regressed=int(counts.get('regressed',0))
            summaries.append({'variant':variant,'n':len(group),'improved':improved,'regressed':regressed,
                              'tied_correct':int(counts.get('tied_correct',0)),
                              'tied_incorrect':int(counts.get('tied_incorrect',0)),
                              'accuracy_delta':(improved-regressed)/len(group)})
    return paired,pd.DataFrame(summaries)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    frame=pd.read_csv(args.folder/'quality_evaluation.csv',keep_default_na=False)
    paired,summary=paired_tables(frame)
    write_dataframe(paired,args.folder/'quality_paired.csv')
    write_dataframe(summary,args.folder/'quality_paired_summary.csv')
    print(summary.to_string(index=False))

if __name__=='__main__':main()
