"""Esquemas e escrita dos CSVs; metadados de origem permanecem nos JSONs."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path


EVALUATION_FIELDS = (
    "question_id", "scenario", "variant", "repetition", "question", "answer",
    "expected_answer", "rubric", "expected_evidence", "citations",
    "evaluation_mode", "note",
)


def validate_columns(columns):
    """Impede que colunas administrativas antigas retornem às tabelas."""
    administrative = {"human", "humano", "humana", "reviewer", "assisted", "assistido", "assistida", "ai", "ia"}
    invalid = [str(column) for column in columns
               if administrative.intersection(re.split(r"[\W_]+", str(column).lower()))]
    if invalid:
        raise ValueError("Colunas fora do esquema dos resultados: " + ", ".join(invalid))


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = list(fields) if fields is not None else (list(rows[0]) if rows else [])
    validate_columns(fields)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def write_dataframe(frame, path, *, index=False):
    columns = list(frame.columns)
    if index:
        columns = [name for name in frame.index.names if name is not None] + columns
    validate_columns(columns)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=index)
