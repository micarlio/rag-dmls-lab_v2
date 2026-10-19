"""Leitura e apresentação offline da rodada analisada; não importa o cliente LLM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.analyze_control import analyze, load_review

VARIANTS = ['pure_llm', 'baseline', 'adaptive', 'self_rag']
LABELS = {'pure_llm': 'LLM puro', 'baseline': 'Baseline', 'adaptive': 'Adaptive', 'self_rag': 'Self-RAG'}


def revision_modes(traces):
    """Classifica a forma de revisão comprovada pelos eventos, sem inferir pelo ID."""
    rows = []
    for t in traces:
        if t['variant'] != 'self_rag':
            continue
        generators = [e for e in t['events'] if e['role'] == 'generator']
        sizes = [len(json.loads(e['raw'])['items']) for e in generators]
        targets = sum(len(r['revised_item_names']) for r in t['revisions'])
        if targets == 0:
            mode = 'no_revision'
        elif targets == 1:
            mode = 'single_target_ambiguous'
        elif len(generators) == 2 and sizes[1] == targets:
            mode = 'joint_revision'
        elif len(generators) == targets + 1 and all(n == 1 for n in sizes[1:]):
            mode = 'per_item_revision'
        else:
            mode = 'unclassified'
        rows.append({'question_id': t['question_id'], 'revision_mode_observed': mode,
                     'revision_targets': targets, 'generator_calls': len(generators),
                     'items_per_generator_call': sizes, 'llm_calls': t['llm_calls'],
                     'latency_seconds': t['latency_seconds']})
    return pd.DataFrame(rows)


def load_analysis(root, run=None):
    root = Path(root).resolve()
    selection = json.loads((root/'configs/analysis.json').read_text())
    folder = Path(run) if run else Path(selection['active_run'])
    folder = folder.resolve() if folder.is_absolute() else (root/folder).resolve()
    review, manifest, traces, keyed, _, _ = load_review(folder)
    cases, checks, summary = analyze(folder, check_only=True, quiet=True)
    decisions = {(d['question_id'], d['variant'], d['repetition']): d for d in review['decisions']}
    if len(decisions) != len(review['decisions']) or set(decisions) != set(keyed):
        raise ValueError('A avaliação final não cobre exatamente as respostas registradas.')
    qs = {q['id']: q for q in manifest['signature']['questions']['questions']}
    quality = []
    for key,t in keyed.items():
        d = decisions[key]
        if hashlib.sha256(t['answer'].encode()).hexdigest() != d['answer_sha256']:
            raise ValueError('Resposta alterada após a anotação.')
        statuses = d['rubric_statuses']
        if len(statuses) != len(qs[key[0]]['rubric']) or not set(statuses) <= {'MET','PARTIAL','MISSING','WRONG'}:
            raise ValueError('Rubrica auxiliar incompatível.')
        quality.append({'question_id': key[0], 'variant': key[1],
            'correct_integral': all(s == 'MET' for s in statuses) and not d['material_error'],
            'criteria_met_fraction': statuses.count('MET')/len(statuses),
            'material_error': d['material_error'], 'abstention_requested_scope': d['abstention'],
            'note': d['note']})
    frame = pd.DataFrame(traces)
    process = frame.groupby('variant').agg(
        answers=('question_id','size'), llm_calls_mean=('llm_calls','mean'),
        extra_searches_mean=('retrieval_calls','mean'), latency_mean_seconds=('latency_seconds','mean'),
        declared_any_item_abstentions=('abstained','sum')).reindex(VARIANTS).reset_index()
    cframe = pd.DataFrame(cases)
    twostep = cframe[cframe.scenario.eq('two_step')].groupby('variant').agg(
        questions=('question_id','size'), useful_retrieval=('useful_retrieval','sum'),
        useful_delivery=('useful_delivery','sum'), complete_context=('all_requested_evidence_delivered','sum')).reset_index()
    return {'root': root, 'run_dir': folder, 'manifest': manifest, 'review': review,
            'questions': pd.DataFrame(qs.values()), 'traces': traces, 'answers': frame,
            'control_cases': cframe, 'checks': pd.DataFrame(checks),
            'control_summary': pd.DataFrame(summary), 'two_step': twostep, 'process': process,
            'quality': pd.DataFrame(quality), 'revision_modes': revision_modes(traces)}


def example(report, question_id='Q02'):
    q = report['questions'].set_index('id').loc[question_id]
    answers = report['answers'][report['answers'].question_id.eq(question_id)]
    evidence = []
    stages = []
    for t in report['traces']:
        if t['question_id'] != question_id or t['variant'] not in {'adaptive','self_rag'}:
            continue
        for n,stage in enumerate(t['stages'],1):
            stages.append({'variant': t['variant'], 'stage': n, 'answer': stage['answer']['answer']})
        for source in t['final_evidence']:
            evidence.append({'variant': t['variant'], 'source_id': source['id'],
                             'page': source['page'], 'text': source['text']})
    return q['question'], answers[['variant','answer','abstained']], pd.DataFrame(stages), pd.DataFrame(evidence)


def plot_results(report, output_dir=None):
    import matplotlib.pyplot as plt
    figures = {}
    with plt.rc_context({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False}):
        fig,ax = plt.subplots(figsize=(9,4.7))
        table = report['two_step'].set_index('variant').reindex(['adaptive','self_rag'])
        metrics = [('useful_retrieval','Complemento encontrado'),('useful_delivery','Algum complemento entregue'),
                   ('complete_context','Contexto completo')]
        colors = ['#2864A0','#DE8733']
        for index,v in enumerate(table.index):
            bars = ax.bar([i+(index-.5)*.34 for i in range(3)], [int(table.loc[v,k]) for k,_ in metrics],
                          width=.32,label=LABELS[v],color=colors[index])
            ax.bar_label(bars,padding=3)
        ax.set_xticks(range(3),[label for _,label in metrics]);ax.set_ylim(0,5.8)
        ax.set_yticks(range(6));ax.set_ylabel('Perguntas (de 5)')
        ax.set_title('Evidência nas perguntas de duas etapas',loc='left',fontweight='bold')
        ax.legend(loc='upper right',frameon=False)
        fig.text(.08,.025,'Entrega de evidência não equivale a resposta correta.',fontsize=9)
        fig.tight_layout(rect=(0,.055,1,1));figures['control_evidence']=fig

        process = report['process'].set_index('variant').reindex(VARIANTS)
        fig,axes = plt.subplots(1,2,figsize=(10,4.8))
        for ax,column,title in zip(axes,['latency_mean_seconds','llm_calls_mean'],
                                   ['Latência média (s)','Chamadas LLM por resposta']):
            bars=ax.bar([LABELS[v] for v in VARIANTS],process[column],color=['#929BA6','#667482',*colors])
            ax.bar_label(bars,fmt='%.1f',padding=3);ax.set_title(title,loc='left',fontweight='bold')
            ax.set_ylim(0,max(process[column])*1.23);ax.tick_params(axis='x',rotation=15)
        fig.text(.07,.025,'Custos observados; o Self-RAG reúne revisões em lote e por item. Contexto inicial fornecido.',fontsize=9)
        fig.tight_layout(rect=(0,.055,1,1));figures['process_cost']=fig
    if output_dir is not None:
        output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
        for name,fig in figures.items():
            fig.savefig(output_dir/(name+'.png'),dpi=180)
            fig.savefig(output_dir/(name+'.svg'))
    return figures
