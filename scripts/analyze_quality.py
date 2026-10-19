"""Consolida a avaliação por critérios, sem preencher os campos de revisão humana.

Uso: .venv/bin/python scripts/analyze_quality.py results/runs/<run>
Os julgamentos ficam em review.json; este script não chama modelos.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(folder):
    folder = Path(folder)
    review = json.loads((folder / "review.json").read_text())
    manifest = json.loads((folder / "run_manifest.json").read_text())
    if manifest["status"] != "complete":
        raise ValueError("A execução precisa estar concluída.")
    for name, expected in review["input_sha256"].items():
        if sha256(folder / name) != expected:
            raise ValueError(f"A entrada mudou após a revisão: {name}")
    questions = {q["id"]: q for q in manifest["signature"]["questions"]["questions"]}
    traces = [json.loads(line) for line in (folder / "traces.jsonl").read_text().splitlines()]
    keys = ["question_id", "variant", "repetition"]
    key = lambda r: tuple(r[k] for k in keys)
    decisions = {key(r): r for r in review["decisions"]}
    if len(decisions) != len(review["decisions"]) or len({key(r) for r in traces}) != len(traces):
        raise ValueError("Chaves duplicadas.")
    if set(decisions) != {key(r) for r in traces}:
        raise ValueError("Revisão e respostas precisam ter as mesmas chaves.")
    rows, criteria = [], []
    for trace in traces:
        decision = decisions[key(trace)]
        q = questions[trace["question_id"]]
        digest = hashlib.sha256(trace["answer"].encode()).hexdigest()
        if digest != decision["answer_sha256"]:
            raise ValueError("A resposta revisada foi alterada.")
        statuses = decision["rubric_statuses"]
        if len(statuses) != len(q["rubric"]) or not set(statuses) <= {"MET", "PARTIAL", "MISSING", "WRONG"}:
            raise ValueError("Julgamento incompatível com a rubrica congelada.")
        if decision["abstention"] not in {"NONE", "PARTIAL", "FULL"}:
            raise ValueError("Abstenção inválida.")
        correct = all(s == "MET" for s in statuses) and not decision["material_error"]
        row = {k: trace[k] for k in keys + ["difficulty", "kind", "question", "answer", "llm_calls", "latency_seconds"]}
        row.update(answerable=q["answerable"], expected_answer=q["expected_answer"],
                   verdict="CORRECT" if correct else "INCORRECT",
                   rubric_statuses=json.dumps(statuses), criteria_met=statuses.count("MET"),
                   criteria_count=len(statuses), criteria_met_fraction=statuses.count("MET") / len(statuses),
                   abstention=decision["abstention"], material_error=decision["material_error"],
                   citation_support=decision["citation_support"], citations=json.dumps(trace["citations"]),
                   note=decision["note"])
        rows.append(row)
        for i, (rubric, status) in enumerate(zip(q["rubric"], statuses), 1):
            criteria.append({**{k: trace[k] for k in keys}, "criterion": i, "rubric": rubric,
                             "status": status, "evidence_pages": json.dumps(q["evidence"], ensure_ascii=False),
                             "note": decision["note"]})
    frame = pd.DataFrame(rows)
    frame["correct"] = frame.verdict.eq("CORRECT")
    frame.to_csv(folder / "quality_evaluation.csv", index=False)
    pd.DataFrame(criteria).to_csv(folder / "quality_criteria.csv", index=False)
    summaries = []
    for variant, group in frame.groupby("variant"):
        answerable = group[group.answerable]
        absent = group[~group.answerable]
        summaries.append({"variant": variant, "n": len(group), "correct": int(group.correct.sum()),
                          "accuracy": group.correct.mean(),
                          "answerable_correct": int(answerable.correct.sum()), "answerable_n": len(answerable),
                          "unanswerable_correct": int(absent.correct.sum()), "unanswerable_n": len(absent),
                          "criteria_met_fraction_mean": group.criteria_met_fraction.mean(),
                          "responses_with_material_error": int(group.material_error.sum()),
                          "answerable_full_abstentions": int(answerable.abstention.eq("FULL").sum()),
                          "answerable_partial_abstentions": int(answerable.abstention.eq("PARTIAL").sum()),
                          "llm_calls_total": int(group.llm_calls.sum()), "llm_calls_mean": group.llm_calls.mean(),
                          "latency_mean_seconds": group.latency_seconds.mean()})
    summary = pd.DataFrame(summaries)
    summary.to_csv(folder / "quality_summary.csv", index=False)
    frame.groupby(["variant", "kind"]).agg(n=("correct", "size"), correct=("correct", "sum"),
        accuracy=("correct", "mean"), criteria_met_fraction_mean=("criteria_met_fraction", "mean"),
        llm_calls_mean=("llm_calls", "mean"), latency_mean_seconds=("latency_seconds", "mean")).to_csv(
            folder / "quality_by_kind.csv")
    paired = []
    pair_keys = ["question_id", "repetition"]
    baseline = frame[frame.variant.eq("baseline")]
    for variant in ["adaptive", "self_rag"]:
        pairs = baseline.merge(frame[frame.variant.eq(variant)], on=pair_keys, how="outer",
            suffixes=("_baseline", "_control"), validate="one_to_one", indicator=True)
        if pairs.empty or not pairs["_merge"].eq("both").all():
            raise ValueError("Faltam pares de pergunta/repetição.")
        for p in pairs.to_dict("records"):
            before, after = p["correct_baseline"], p["correct_control"]
            outcome = ("tied_correct" if after else "regressed") if before else ("improved" if after else "tied_incorrect")
            paired.append({**{k: p[k] for k in pair_keys}, "variant": variant, "outcome": outcome,
                           "criteria_met_delta": p["criteria_met_control"] - p["criteria_met_baseline"],
                           "material_error_removed": p["material_error_baseline"] and not p["material_error_control"],
                           "llm_calls_delta": p["llm_calls_control"] - p["llm_calls_baseline"],
                           "latency_delta_seconds": p["latency_seconds_control"] - p["latency_seconds_baseline"],
                           "baseline_note": p["note_baseline"], "control_note": p["note_control"]})
    paired_frame = pd.DataFrame(paired)
    paired_frame.to_csv(folder / "quality_paired.csv", index=False)
    paired_summary = []
    for variant, group in paired_frame.groupby("variant"):
        counts = group.outcome.value_counts()
        improved, regressed = int(counts.get("improved", 0)), int(counts.get("regressed", 0))
        paired_summary.append({"variant": variant, "n": len(group), "improved": improved, "regressed": regressed,
                               "tied_correct": int(counts.get("tied_correct", 0)),
                               "tied_incorrect": int(counts.get("tied_incorrect", 0)),
                               "accuracy_delta": (improved - regressed) / len(group)})
    pd.DataFrame(paired_summary).to_csv(folder / "quality_paired_summary.csv", index=False)
    print(summary.to_string(index=False))
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    analyze(parser.parse_args().folder)
