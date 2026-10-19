"""Compara correções e regressões após revisão humana completa; sem chamadas LLM."""
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rag_lab import summarize_human


def paired_tables(frame):
    if not frame.human_verdict.isin(['CORRECT','INCORRECT']).all():
        raise ValueError('Complete a revisão antes da comparação pareada.')
    keys=['question_id','repetition']
    fields=keys+['human_verdict','llm_calls','latency_seconds','note']
    baseline=frame.loc[frame.variant.eq('baseline'),fields]
    if baseline.empty:
        raise ValueError('Falta baseline para comparação.')
    rows=[]
    for variant in ['adaptive','self_rag']:
        control=frame.loc[frame.variant.eq(variant),fields]
        if control.empty:
            continue
        pairs=baseline.merge(control,on=keys,how='outer',suffixes=('_baseline','_control'),validate='one_to_one',indicator=True)
        if not pairs['_merge'].eq('both').all():
            raise ValueError('Comparação exige os mesmos pares de pergunta/repetição em cada variante.')
        for row in pairs.to_dict('records'):
            before=row['human_verdict_baseline']=='CORRECT'
            after=row['human_verdict_control']=='CORRECT'
            outcome=('improved' if after else 'tied_incorrect') if not before else ('tied_correct' if after else 'regressed')
            rows.append({**{k:row[k] for k in keys},'variant':variant,'outcome':outcome,
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
                              'net_correct_change':improved-regressed,'accuracy_delta':(improved-regressed)/len(group),
                              'llm_calls_delta_mean':group.llm_calls_delta.mean(),
                              'latency_delta_mean_seconds':group.latency_delta_seconds.mean()})
    return paired,pd.DataFrame(summaries)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    summarize_human(args.folder)
    frame=pd.read_csv(args.folder/'evaluated_answers.csv',keep_default_na=False)
    paired,summary=paired_tables(frame)
    paired.to_csv(args.folder/'paired_comparison.csv',index=False)
    summary.to_csv(args.folder/'summary_paired.csv',index=False)
    frame['correct']=frame.human_verdict.eq('CORRECT')
    by_tier=frame.groupby(['variant','difficulty']).agg(n=('correct','size'),accuracy_human=('correct','mean'),
             llm_calls_mean=('llm_calls','mean'),latency_mean_seconds=('latency_seconds','mean'))
    by_tier.to_csv(args.folder/'quality_by_difficulty.csv')
    print(summary.to_string(index=False))

if __name__=='__main__':main()
