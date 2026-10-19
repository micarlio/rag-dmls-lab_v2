"""Consolida a avaliação dos mecanismos, sem inferência ou edição dos rastros.

Uso: .venv/bin/python scripts/analyze_control.py results/runs/<run>
As decisões semânticas estão em review.json, não são inferidas por palavras-chave.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def load_review(folder):
    folder = Path(folder)
    review = json.loads((folder / "review.json").read_text())
    manifest = json.loads((folder / "run_manifest.json").read_text())
    if manifest.get("status") != "complete" or canonical(manifest["signature"]) != manifest["fingerprint"]:
        raise ValueError("Manifesto incompleto ou fingerprint inconsistente.")
    for name, expected in review["input_sha256"].items():
        path = (folder / name).resolve()
        if path.parent != folder.resolve() or digest(path) != expected:
            raise ValueError("Entrada alterada ou caminho inválido: " + name)
    traces = [json.loads(line) for line in (folder / "traces.jsonl").read_text().splitlines()]
    qs = {q["id"]: q for q in manifest["signature"]["questions"]["questions"]}
    cfg = manifest["signature"]["config"]
    if len(cfg["seeds"]) != 1:
        raise ValueError("Esta revisão semântica corresponde a uma única repetição.")
    expected = {(qid, v, rep) for qid in qs for v in cfg["variants"]
                for rep in range(1, len(cfg["seeds"]) + 1)}
    keyed = {(r["question_id"], r["variant"], r["repetition"]): r for r in traces}
    if set(keyed) != expected or len(keyed) != len(traces):
        raise ValueError("Rastros ausentes, duplicados ou fora do conjunto esperado.")
    if any(r["run_fingerprint"] != manifest["fingerprint"] or
           r["seed"] != cfg["seeds"][r["repetition"] - 1] for r in traces):
        raise ValueError("Rastros e manifesto não correspondem.")
    cases = review["control_cases"]
    if {c["question_id"] for c in cases} != set(qs) or len(cases) != len(qs):
        raise ValueError("É necessário anotar todas as perguntas uma única vez.")
    for case in cases:
        q = qs[case["question_id"]]
        n = len(q["rubric"])
        if len(case["initial_criteria"]) != n or not set(case["initial_criteria"]) <= {"FULL", "PARTIAL", "ABSENT", "NA"}:
            raise ValueError("Anotação inicial incompatível com a rubrica.")
        for variant in ["adaptive", "self_rag"]:
            decision = case[variant]
            for field in ["new_retrieved_criteria", "new_delivered_criteria"]:
                indices = decision[field]
                if len(set(indices)) != len(indices) or any(i < 1 or i > n for i in indices):
                    raise ValueError("Critério inexistente ou duplicado.")
            if not set(decision["new_delivered_criteria"]) <= set(decision["new_retrieved_criteria"]):
                raise ValueError("Entrega de evidência sem recuperação correspondente.")
            if len(decision['final_context_criteria']) != n or not set(decision['final_context_criteria']) <= {'FULL','PARTIAL','ABSENT','NA'}:
                raise ValueError('Cobertura do contexto final incompatível com a rubrica.')
            for rep in range(1, len(cfg["seeds"]) + 1):
                trace = keyed[(case["question_id"], variant, rep)]
                witnesses = decision["witnesses"]
                covered = {w["criterion"] for w in witnesses}
                if not set(decision["new_retrieved_criteria"]) <= covered:
                    raise ValueError("Recuperação útil sem trecho testemunha.")
                for witness in witnesses:
                    if witness["criterion"] not in decision["new_retrieved_criteria"]:
                        raise ValueError("Testemunha fora dos critérios anotados.")
                    matches = [s for search in trace["searches"] for s in search["hits"]
                               if s["doc_id"] == witness["doc_id"] and s["page"] == witness["page"]
                               and witness["quote"] in s["text"]]
                    if not matches:
                        raise ValueError("Trecho testemunha não consta da recuperação real.")
                for criterion in decision['new_delivered_criteria']:
                    if not any(w['criterion'] == criterion and any(
                            w['quote'] in source['text'] for source in trace['final_evidence'])
                            for w in witnesses):
                        raise ValueError('Evidência entregue sem testemunha no contexto real.')
    checks = {(r["question_id"], r["repetition"], stage, index): check
              for r in traces if r["variant"] == "self_rag"
              for stage, group in enumerate(r["checks"], 1)
              for index, check in enumerate(group["items"], 1)}
    annotations = review["support_judgments"]
    refs = {(a["question_id"], a["repetition"], a["check_round"], a["item_index"]): a for a in annotations}
    if set(checks) != set(refs) or len(refs) != len(annotations):
        raise ValueError("Julgamentos de apoio ausentes ou duplicados.")
    allowed = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNDETERMINED", "TEXT_EXTRACTION_ONLY", "NA"}
    for key, ref in refs.items():
        if ref["reference_support"] not in allowed or ref["check_sha256"] != canonical(checks[key]):
            raise ValueError("Julgamento incompatível ou verificação original alterada.")
    return review, manifest, traces, keyed, checks, refs


def write_csv(path, rows):
    if not rows:
        raise ValueError("Tabela vazia: " + str(path))
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def analyze(folder, check_only=False, quiet=False):
    folder = Path(folder)
    review, manifest, traces, keyed, checks, refs = load_review(folder)
    qs = {q["id"]: q for q in manifest["signature"]["questions"]["questions"]}
    cases, check_rows, process = [], [], []
    for case in review["control_cases"]:
        q = qs[case["question_id"]]
        for variant in ["adaptive", "self_rag"]:
            a = case[variant]
            # Anotações semânticas desta revisão se referem à única repetição registrada.
            t = keyed[(case["question_id"], variant, 1)]
            cases.append({"question_id": q["id"], "variant": variant, "scenario": q["scenario"],
                "answerable": q["answerable"], "initial_criteria": case["initial_criteria"],
                "final_context_criteria": a['final_context_criteria'],
                "all_requested_evidence_delivered": q['answerable'] and all(c == 'FULL' for c in a['final_context_criteria']),
                "scenario_issue": case["scenario_issue"], "unrequested_needs": case["unrequested_needs"],
                "redundant_needs": case["redundant_needs"],
                "new_retrieved_criteria": a["new_retrieved_criteria"],
                "new_delivered_criteria": a["new_delivered_criteria"],
                "useful_retrieval": bool(a["new_retrieved_criteria"]),
                "useful_delivery": bool(a["new_delivered_criteria"]),
                "effect": a["effect"], "own_draft_benefit": a["own_draft_benefit"],
                "own_draft_regression": a["own_draft_regression"], "note": a["note"],
                "witnesses": a["witnesses"], "llm_calls": t["llm_calls"],
                "extra_searches": t["retrieval_calls"], "latency_seconds": t["latency_seconds"],
                })
    for key, check in checks.items():
        ref = refs[key]
        truth = ref["reference_support"]
        positive = check["support"] == "supported"
        if truth in {"UNDETERMINED", "NA"}:
            classification = "undetermined"
        elif truth == "TEXT_EXTRACTION_ONLY":
            classification = "text_supported_extraction_error"
        elif positive:
            classification = "correct_approval" if truth == "SUPPORTED" else "false_approval"
        else:
            classification = "false_rejection" if truth == "SUPPORTED" else "appropriate_flag"
        check_rows.append({"question_id": key[0], "repetition": key[1], "check_round": key[2],
            "item_index": key[3], "item": check["item"], "answer_span": check["answer_span"],
            "model_support": check["support"], "model_coverage": check["coverage"],
            "reference_support": truth, "support_classification": classification,
            "source_ids": check["source_ids"], "quote": check["quote"], "note": ref["note"],
            })
    for variant in manifest["signature"]["config"]["variants"]:
        groups = [("all", [r for r in traces if r["variant"] == variant])]
        groups += [(scenario, [r for r in traces if r["variant"] == variant and r["scenario"] == scenario])
                   for scenario in ["direct", "two_step", "distractor", "unanswerable"]]
        for scenario, group in groups:
            n = len(group)
            process.append({"variant": variant, "scenario": scenario, "n": n,
                "llm_calls_mean": sum(r["llm_calls"] for r in group)/n,
                "extra_searches_mean": sum(r["retrieval_calls"] for r in group)/n,
                "latency_mean_seconds": sum(r["latency_seconds"] for r in group)/n,
                "declared_any_item_abstentions": sum(r["abstained"] for r in group)})
    summary = []
    for variant in ["adaptive", "self_rag"]:
        group = [r for r in cases if r["variant"] == variant]
        summary.append({"variant": variant, "questions": len(group),
            "questions_with_extra_search": sum(r["extra_searches"] > 0 for r in group),
            "questions_with_useful_retrieval": sum(r["useful_retrieval"] for r in group),
            "questions_with_useful_delivery": sum(r["useful_delivery"] for r in group),
            "retrieved_new_criteria": sum(len(r["new_retrieved_criteria"]) for r in group),
            "delivered_new_criteria": sum(len(r["new_delivered_criteria"]) for r in group),
            "effect_counts": dict(Counter(r["effect"] for r in group)),
            "own_draft_benefit_questions": sum(r["own_draft_benefit"] for r in group),
            "own_draft_regression_questions": sum(r["own_draft_regression"] for r in group)})
    if not check_only:
        write_csv(folder/"control_by_question.csv", cases)
        write_csv(folder/"control_checks.csv", check_rows)
        write_csv(folder/"control_summary.csv", summary)
        write_csv(folder/"control_process.csv", process)
        write_csv(folder/"control_support_summary.csv", [
            {"support_classification": k, "count": v} for k,v in sorted(
                Counter(r["support_classification"] for r in check_rows).items())])
    if not quiet:
        print(json.dumps({"control_cases": len(cases), "support_checks": len(check_rows),
                      "summary": summary, "support_counts": dict(Counter(
                          r["support_classification"] for r in check_rows))}, ensure_ascii=False, indent=2))
    return cases, check_rows, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    analyze(args.folder, args.check_only)
