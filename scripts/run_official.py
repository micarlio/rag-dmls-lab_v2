"""Execução do conjunto atual; perguntas, variantes e repetições vêm da configuração."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag_lab import (
    Experiment,
    Ollama,
    Retriever,
    ingest,
    read_json,
    run_experiment,
    validate_questions,
    file_sha,
)


def main():
    parser = argparse.ArgumentParser(description="Executa o benchmark configurado (atualmente 80 respostas).")
    parser.add_argument("--resume", help="Caminho da pasta da run para retomar execução interrompida.", default=None)
    parser.add_argument("--mode", choices=["controlled", "full", "diagnostic"], default="controlled",
                        help="Modo da avaliação: controlled (condição controlada), full (pipeline completo) ou diagnostic (análise de top_k do baseline).")
    parser.add_argument("--dry-run", action="store_true", help="Valida corpus/perguntas e mostra o escopo sem inferência.")
    args = parser.parse_args()

    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.is_absolute():
            resume_path = ROOT / resume_path
        manifest = read_json(resume_path / 'run_manifest.json')
        if manifest.get('evaluation_mode') != args.mode:
            raise ValueError('Retomada exige o mesmo modo de avaliação registrado no manifesto.')
        if manifest.get('status') == 'complete':
            print('A rodada já está concluída. Use scripts/summarize_results.py para consultar a análise.')
            return

    config = read_json(ROOT / "configs/experiment.json")
    dataset = read_json(ROOT / "questions.json")
    corpus = ingest(ROOT, config)
    validate_questions(dataset, corpus, config)

    print(f"Corpus validado: {len(corpus['documents'])} documentos, {len(corpus['chunks'])} chunks.", flush=True)
    print(f"Perguntas oficiais validadas: {len(dataset['questions'])} perguntas.", flush=True)
    print(f"Modo de avaliação: {args.mode}", flush=True)
    print(f"Variantes: {config['variants']}", flush=True)
    print(f"Sementes: {config['seeds']} ({len(config['seeds'])} repetições)", flush=True)
    print(f"Total de respostas planejadas: {len(dataset['questions']) * len(config['variants']) * len(config['seeds'])}", flush=True)

    if args.dry_run:
        return
    client = Ollama(config)
    retriever = Retriever(ROOT, corpus, config, client)
    experiment = Experiment(ROOT, config, retriever, client)

    if args.mode == "diagnostic":
        from rag_lab import run_baseline_diagnostic, write_json
        diag_results = run_baseline_diagnostic(experiment, corpus, dataset, top_k_list=[4, 8, 12])
        out_file = ROOT / "results/pilot/diagnostic_baseline.json"
        write_json(out_file, {"diagnostic_baseline": diag_results, "policy": "top_k_truncation_analysis"})
        print(f"\nDIAGNÓSTICO BASELINE CONCLUÍDO: salvo em {out_file}", flush=True)
        import pandas as pd
        df = pd.DataFrame(diag_results)
        print(df.groupby("top_k")[["raw_text_chars", "provided_context_chars", "truncated", "discarded_windows_count"]].mean(), flush=True)
        return

    # Não misturar prompts/código/gabaritos alterados durante uma execução.
    frozen_files = [ROOT / 'rag_lab.py', ROOT / 'csv_output.py', ROOT / 'configs/experiment.json',
                    ROOT / 'questions.json', *sorted((ROOT / 'prompts').glob('*.txt'))]
    if config.get('control_policy') == 'evidence_needs':
        frozen_files.append(ROOT / 'rag_control.py')
    frozen_hashes = {p: file_sha(p) for p in frozen_files}
    execute = experiment.execute

    def frozen_execute(variant, question, seed, initial_hits=None, mode="full"):
        if any(file_sha(p) != sha for p, sha in frozen_hashes.items()):
            raise ValueError('Arquivos do experimento mudaram durante a execução; dados anteriores preservados.')
        return execute(variant, question, seed, initial_hits=initial_hits, mode=mode)

    experiment.execute = frozen_execute

    run_dir = run_experiment(experiment, corpus, dataset, resume_dir=args.resume, mode=args.mode)
    print(f"\n=======================================================", flush=True)
    print(f"EXECUÇÃO OFICIAL CONCLUÍDA COM SUCESSO!", flush=True)
    print(f"Diretório dos resultados: {run_dir}", flush=True)
    print(f"=======================================================", flush=True)


if __name__ == "__main__":
    main()
