"""Experimentos locais de RAG. O notebook conduz as etapas; este módulo as implementa.

Origem e adaptações: docs/ORIGEM.md. Nenhuma resposta de teste é um resultado oficial.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import time
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fingerprint(data):
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def chunk_pages(doc_id, filename, pages, size, overlap):
    """Chunks não cruzam páginas nem documentos; páginas físicas começam em 1."""
    if not 0 <= overlap < size:
        raise ValueError("Exige-se 0 <= overlap < chunk_size.")
    chunks = []
    for page_number, text in pages:
        text = re.sub(r"\s+", " ", text).strip()
        for number, start in enumerate(range(0, len(text), size - overlap), 1):
            raw_piece = text[start:start + size]
            piece = raw_piece.strip()
            actual_start = start + len(raw_piece) - len(raw_piece.lstrip())
            if piece:
                chunks.append({"id": f"{doc_id}:P{page_number:04d}:C{number:04d}",
                               "doc_id": doc_id, "filename": filename,
                               "page": page_number, "text": piece,
                               "start_char": actual_start, "end_char": actual_start + len(piece)})
            if start + size >= len(text):
                break
    return chunks


def ingest(root, config):
    root = Path(root)
    files = sorted(p for p in (root / "corpus/documentos").iterdir()
                   if p.is_file() and p.suffix.lower() == ".pdf")
    if not files:
        raise FileNotFoundError("Coloque os cinco PDFs em corpus/documentos/.")
    manifest_path = root / "corpus/manifest.csv"
    previous = {}
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as stream:
            previous = {r["sha256"]: r for r in csv.DictReader(stream)}
    docs, chunks, seen = [], [], set()
    for n, file in enumerate(files, 1):
        sha = file_sha(file)
        if sha in seen:
            raise ValueError(f"PDF duplicado por conteúdo: {file.name}")
        seen.add(sha)
        reader = PdfReader(file)
        pages = [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
        text_pages = sum(bool(text.strip()) for _, text in pages)
        if not text_pages:
            raise ValueError(f"{file.name}: sem texto extraível; precisa de OCR antes da ingestão.")
        old = previous.get(sha, {})
        doc = {"doc_id": f"DOC{n:02d}", "filename": file.name, "sha256": sha,
               "title": old.get("title", file.stem),
               "pages": len(pages), "text_pages": text_pages,
               "extracted_chars": sum(len(text) for _, text in pages),
               "source_url": old.get("source_url", ""),
               "redistribution_note": old.get("redistribution_note", "A conferir; cópia local")}
        docs.append(doc)
        document_chunks = chunk_pages(doc["doc_id"], file.name, pages,
                                      config["chunk_size_chars"], config["chunk_overlap_chars"])
        for c in document_chunks:
            c["title"] = doc["title"]
        chunks.extend(document_chunks)
    corpus_id = fingerprint([{k: d[k] for k in ("doc_id", "filename", "sha256")} for d in docs])
    cache = root / ".cache" / corpus_id
    cache.mkdir(parents=True, exist_ok=True)
    write_json(cache / "chunks.json", chunks)
    write_csv(manifest_path, docs)
    return {"documents": docs, "chunks": chunks, "fingerprint": corpus_id}


def schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


ANSWER_SCHEMA = schema({"answer": {"type": "string"}, "abstained": {"type": "boolean"},
                        "citations": {"type": "array", "items": {"type": "string"}}})
ROUTER_SCHEMA = schema({"route": {"type": "string", "enum": ["direct", "single", "iterative"]},
                        "reason": {"type": "string"}})
JUDGE_SCHEMA = schema({"verdict": {"type": "string", "enum": ["CORRECT", "INCORRECT", "UNCERTAIN"]},
                       "reason": {"type": "string"}})


def retrieval_focus(question):
    """Separa o pedido factual de um preâmbulo; a busca densa conserva o enunciado."""
    return re.split(r"[,;:]\s*(?=(?:qual|quais|como|quant[oa]s?|por que)\b)",
                    question, maxsplit=1, flags=re.I)[-1].strip()


def query_key(query):
    return re.sub(r"\W+", " ", query.casefold()).strip()


def evidence_units(passages, size=480):
    """Trechos literais com IDs curtos. Nenhum modelo gera o texto da fonte."""
    units = []
    for passage in passages:
        text, start = passage["text"], 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + size // 2, end)
                if boundary > start:
                    end = boundary
            raw = text[start:end]
            offset = start + len(raw) - len(raw.lstrip())
            piece = raw.strip()
            if piece:
                units.append({"id": f"E{len(units) + 1}", "source_id": passage["id"],
                              "doc_id": passage["doc_id"], "page": passage["page"], "text": piece,
                              "start_char": passage.get("start_char", 0) + offset,
                              "end_char": passage.get("start_char", 0) + offset + len(piece)})
            start = end
    return units


def numeric_atoms(text):
    """Valores citados, sem usar gabaritos. Não prova relação causal ou unidades."""
    values = set()
    for value in re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)", text):
        try:
            values.add(format(Decimal(value.replace(",", ".")).normalize(), "f"))
        except InvalidOperation:
            values.add(value)
    words = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3,
             "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
             "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
             "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16,
             "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20}
    values.update(str(words[word]) for word in re.findall(r"\w+", text.casefold()) if word in words)
    return values


def focus_evidence(units, item, answer, limit=6):
    """Candidatos literais para um item, sem páginas esperadas ou gabaritos.

    Inclui continuidade dos dois melhores trechos para não cortar valores ou
    relações na divisão de uma frase. A seleção não é prova de sustentação.
    """
    if len(units) <= limit:
        return units
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode")
    matrix = vectorizer.fit_transform(u["text"] for u in units)
    scores = (2 * cosine_similarity(vectorizer.transform([item]), matrix).ravel()
              + cosine_similarity(vectorizer.transform([answer]), matrix).ravel())
    ranked = list(np.argsort(-scores, kind="stable"))
    indices = set(ranked[:2])
    for i in ranked[:2]:
        for neighbor in (i - 1, i + 1):
            if 0 <= neighbor < len(units) and units[neighbor]["source_id"] == units[i]["source_id"]:
                indices.add(neighbor)
    for i in ranked:
        if len(indices) >= limit:
            break
        indices.add(i)
    return [units[i] for i in sorted(indices)]


def grounding_units(passages):
    """Sentenças literais, com offsets; preserva relações cortadas por blocos fixos."""
    units = []
    for passage in passages:
        text = passage["text"]
        boundaries = [0, *[m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9])", text)], len(text)]
        for start, end in zip(boundaries, boundaries[1:]):
            raw = text[start:end]
            offset = start + len(raw) - len(raw.lstrip())
            piece = raw.strip()
            if not piece:
                continue
            base = {**passage, "text": piece, "start_char": passage.get("start_char", 0) + offset}
            for unit in evidence_units([base], size=1200):
                unit["id"] = f"E{len(units) + 1}"
                units.append(unit)
    return units


def claim_evidence(units, item, answer, limit=6):
    """Seleciona frases candidatas por afirmação, sem rubricas ou páginas esperadas."""
    if not units:
        return []
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode")
    matrix = vectorizer.fit_transform(u["text"] for u in units)
    clauses = [part for part in re.split(r"(?<=[.!?])\s+|[;\n]+", answer) if part.strip()]
    scores = []
    for clause in clauses or [answer]:
        values = (cosine_similarity(vectorizer.transform([clause]), matrix).ravel()
                  + 0.5 * cosine_similarity(vectorizer.transform([item]), matrix).ravel())
        scores.append(values)
    selected = set()
    for values in scores:
        selected.update(np.argsort(-values, kind="stable")[:2])
    aggregate = np.max(np.vstack(scores), axis=0)
    indices = sorted(selected, key=lambda i: (-aggregate[i], i))[:limit]
    return [units[i] for i in sorted(indices)]


def atomic_identification(item, answer, source):
    """Cobertura estrutural de um nome/código literal; suporte é julgado à parte.

    Não se aplica a pedidos compostos, explicações, listas ou respostas de recusa.
    A presença do valor não prova que ele pertence à entidade pedida.
    """
    words = set(re.findall(r"\w+", item.casefold()))
    if not words & {"nome", "modelo", "software", "framework", "formato"}:
        return False
    if (words & {"e", "ou", "cada", "ambos", "ambas", "quais", "nomes", "modelos", "como", "explique", "justifique", "quando", "onde", "função", "motivo"}
            or "por que" in item.casefold() or re.search(r"[,;:]", item)):
        return False
    tokens = re.findall(r"\w+", answer)
    if not 1 <= len(tokens) <= 6 or any(t.casefold() in {"não", "desconhecido", "ausente", "indisponível"} for t in tokens):
        return False
    named = any(t[0].isupper() and t.casefold() not in words and len(t) > 1 for t in tokens)
    normalize = lambda text: re.sub(r"\W+", "", text.casefold())
    return named and normalize(answer) in normalize(source)


class Ollama:
    def __init__(self, config):
        self.config = config
        self.url = config["ollama_url"].rstrip("/")
        self.events = []

    def models(self):
        r = requests.get(self.url + "/api/tags", timeout=10)
        r.raise_for_status()
        return {m["name"]: {k: m.get(k) for k in ("digest", "size", "details")}
                for m in r.json()["models"]}

    def unload(self, model):
        r = requests.post(self.url + "/api/generate",
                          json={"model": model, "keep_alive": 0, "stream": False}, timeout=60)
        r.raise_for_status()

    def generate(self, prompt, output_schema, seed, role="generator"):
        cfg = self.config
        payload = {"model": cfg["generator_model"], "prompt": prompt, "stream": False,
                   "format": output_schema, "keep_alive": cfg["generation_keep_alive"],
                   "options": {"num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"],
                               "seed": seed, "num_predict": cfg.get("planner_num_predict", 768) if role == "planner"
                               else cfg["num_predict"] if role == "generator"
                               else cfg.get("verifier_num_predict", cfg["control_num_predict"])
                               if role == "verifier" else cfg["control_num_predict"]}}
        event = {"role": role, "model": payload["model"], "seed": seed}
        start = time.perf_counter()
        try:
            r = requests.post(self.url + "/api/generate", json=payload, timeout=cfg["timeout_seconds"])
            r.raise_for_status()
            body = r.json()
            event.update({k: body.get(k) for k in ("prompt_eval_count", "eval_count", "load_duration", "done_reason")})
            event["raw"] = body.get("response", "")
            if body.get("done_reason") == "length":
                raise ValueError("Resposta truncada pelo limite de tokens; ajuste e crie outra run.")
            result = json.loads(event["raw"])
            for key, spec in output_schema["properties"].items():
                if key not in result:
                    raise ValueError(f"Saída estruturada sem {key}.")
                expected = {"boolean": bool, "string": str, "array": list, "object": dict}[spec["type"]]
                if not isinstance(result[key], expected):
                    raise ValueError(f"Tipo inválido em {key}.")
                if "enum" in spec and result[key] not in spec["enum"]:
                    raise ValueError(f"Valor inválido em {key}.")
            return result
        except (Exception, KeyboardInterrupt) as exc:
            event["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            event["seconds"] = time.perf_counter() - start
            self.events.append(event)

    def generate_text(self, prompt, seed, role="claim_support"):
        """Parecer textual curto, sem gramática JSON; nunca usado como fonte."""
        cfg = self.config
        event = {"role": role, "model": cfg["generator_model"], "seed": seed}
        started = time.perf_counter()
        try:
            r = requests.post(self.url + "/api/generate", json={
                "model": cfg["generator_model"], "prompt": prompt, "stream": False,
                "keep_alive": cfg["generation_keep_alive"], "options": {
                    "num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"], "seed": seed,
                    "num_predict": cfg.get("verifier_num_predict", cfg["control_num_predict"]) }},
                timeout=cfg["timeout_seconds"])
            r.raise_for_status()
            body = r.json()
            event.update({k: body.get(k) for k in ("prompt_eval_count", "eval_count", "load_duration", "done_reason")})
            event["raw"] = body.get("response", "")
            if body.get("done_reason") == "length":
                raise ValueError("Parecer textual truncado.")
            return event["raw"]
        except (Exception, KeyboardInterrupt) as exc:
            event["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            event["seconds"] = time.perf_counter() - started
            self.events.append(event)

    def embed(self, texts, keep_alive=0):
        cfg = self.config
        # Um modelo por vez no M1; nenhuma alteração nas outras aplicações.
        self.unload(cfg["generator_model"])
        event = {"role": "embedding", "model": cfg["embedding_model"], "inputs": len(texts)}
        start = time.perf_counter()
        try:
            r = requests.post(self.url + "/api/embed", json={
                "model": cfg["embedding_model"], "input": texts, "truncate": False,
                "keep_alive": keep_alive}, timeout=cfg["timeout_seconds"])
            r.raise_for_status()
            body = r.json()
            event["prompt_eval_count"] = body.get("prompt_eval_count")
            event["load_duration"] = body.get("load_duration")
            vectors = np.asarray(body["embeddings"], dtype=np.float32)
            if len(vectors) != len(texts) or not np.isfinite(vectors).all():
                raise ValueError("Embeddings inválidos.")
            return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        finally:
            event["seconds"] = time.perf_counter() - start
            self.events.append(event)


def rrf(rankings, k, constant=60):
    scores, chunks = {}, {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, 1):
            key = chunk["id"]
            scores[key] = scores.get(key, 0) + 1 / (constant + rank)
            chunks[key] = chunk
    return [chunks[key] for key in sorted(scores, key=scores.get, reverse=True)[:k]]


class Retriever:
    def __init__(self, root, corpus, config, client):
        self.chunks, self.config, self.client = corpus["chunks"], config, client
        self.vectorizer = TfidfVectorizer(
            analyzer=config.get("lexical_analyzer", "word"),
            ngram_range=tuple(config.get("lexical_ngram_range", [1, 2])),
            strip_accents="unicode", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(c["text"] for c in self.chunks)
        self.page_chunks = {}
        for chunk in self.chunks:
            self.page_chunks.setdefault((chunk["doc_id"], chunk["page"]), []).append(chunk)
        self.frontmatter_pages = set()
        for key, parts in self.page_chunks.items():
            heading = re.sub(r"[^a-záàâãéêíóôõúç]", "", parts[0]["text"][:100].casefold())
            if heading.startswith(("sumário", "sumario", "listadefiguras", "listadeilustrações",
                                   "listadetabelas", "listadequadros", "listadesímbolos",
                                   "listadeabreviaturas", "listadealgoritmos")):
                self.frontmatter_pages.add(key)
        self.vectors = None
        self.fixed_queries, self.dynamic_queries = {}, {}
        if config["retriever"] not in ("tfidf", "hybrid", "dense"):
            raise ValueError("retriever deve ser tfidf, dense ou hybrid.")
        if config["retriever"] != "tfidf":
            models = client.models()
            name = config["embedding_model"]
            if name not in models:
                raise ValueError(f"Modelo ausente: ollama pull {name}")
            # Offsets são metadados de composição; não mudam os textos já embutidos.
            embedding_chunks = [{k: c[k] for k in ("id", "doc_id", "filename", "page", "text", "title")
                                 if k in c} for c in self.chunks]
            cache_id = fingerprint({"chunks": embedding_chunks, "model": models[name],
                                    "prefix": "title: document title | text: chunk"})
            cache = Path(root) / ".cache" / (cache_id + ".npy")
            cache.parent.mkdir(parents=True, exist_ok=True)
            if cache.exists():
                self.vectors = np.load(cache, allow_pickle=False)
            else:
                batches = []
                size = config["embedding_batch_size"]
                try:
                    for start in range(0, len(self.chunks), size):
                        part = self.chunks[start:start + size]
                        inputs = [f'title: {c.get("title", c["filename"])} | text: {c["text"]}' for c in part]
                        batches.append(client.embed(inputs, keep_alive="2m"))
                        if start % (size * 10) == 0 or start + size >= len(self.chunks):
                            print(f"Embeddings: {min(start + size, len(self.chunks))}/{len(self.chunks)} chunks", flush=True)
                    self.vectors = np.vstack(batches)
                    np.save(cache, self.vectors, allow_pickle=False)
                finally:
                    client.unload(name)
            if self.vectors.shape[0] != len(self.chunks):
                raise ValueError("Cache de embeddings não corresponde aos chunks.")

    def prefetch(self, questions):
        """Pré-computa a mesma consulta inicial para todas as variantes, fora da latência."""
        if self.vectors is not None:
            for question in questions:
                self.fixed_queries[question] = self.client.embed(
                    [f"task: search result | query: {question}"])[0]

    def reset_dynamic(self):
        self.dynamic_queries.clear()

    def search(self, query, k=None):
        k = self.config["top_k"] if k is None else k
        pool = max(k, self.config.get("retrieval_candidate_pool", k))
        if pool < k:
            raise ValueError("retrieval_candidate_pool precisa ser >= top_k.")
        # IDs vêm do enunciado, nunca de doc_id/páginas do gabarito.
        requested_docs = set(re.findall(r"\bDOC\d{2}\b", query.upper()))
        eligible = [i for i, chunk in enumerate(self.chunks)
                    if (not self.config.get("restrict_explicit_documents") or not requested_docs
                        or chunk["doc_id"] in requested_docs)
                    and (not self.config.get("exclude_frontmatter")
                         or (chunk["doc_id"], chunk["page"]) not in self.frontmatter_pages)]
        lexical = cosine_similarity(self.vectorizer.transform([retrieval_focus(query)]), self.matrix).ravel()
        sparse = [self.chunks[i] for i in sorted(eligible, key=lambda i: (-lexical[i], i))
                  if lexical[i] > 0][:pool]
        if self.vectors is None:
            ranked = sparse
        else:
            vector = self.fixed_queries.get(query)
            if vector is None:
                vector = self.dynamic_queries.get(query)
            if vector is None:
                vector = self.client.embed([f"task: search result | query: {query}"])[0]
                self.dynamic_queries[query] = vector
            dense_scores = self.vectors @ vector
            dense = [self.chunks[i] for i in sorted(eligible, key=lambda i: (-dense_scores[i], i))[:pool]]
            ranked = dense if self.config["retriever"] == "dense" else rrf([sparse, dense], pool)
        if self.config.get("reference_lookup"):
            # Busca literal de figura/tabela solicitada; sumários já excluídos.
            references = re.findall(r"\b(figura|tabela)\s+(\d+(?:\.\d+)*)", query, re.I)
            captions = [self.chunks[i] for i in eligible if any(re.search(
                rf"\b{kind}\s+{re.escape(number)}(?![\d.])\s*[–—:\-]",
                self.chunks[i]["text"], re.I) for kind, number in references)]
            priority = {c["id"] for c in captions}
            ranked = captions + [c for c in ranked if c["id"] not in priority]
        return ranked[:k]

    def expand(self, anchors):
        """Janelas contínuas de uma página, com IDs próprios e chunks de origem."""
        radius = self.config.get("neighbor_window", 0)
        if radius < 0:
            raise ValueError("neighbor_window não pode ser negativo.")
        selected = {}
        adjacent = self.config.get("page_neighbor_chunks", 0)
        if adjacent < 0:
            raise ValueError("page_neighbor_chunks não pode ser negativo.")
        for anchor in anchors:
            key = (anchor["doc_id"], anchor["page"])
            siblings = self.page_chunks[key]
            position = next(i for i, c in enumerate(siblings) if c["id"] == anchor["id"])
            selected.setdefault(key, set()).update(range(max(0, position - radius),
                                                         min(len(siblings), position + radius + 1)))
            # Continuação em página vizinha, mantendo janelas e IDs separados.
            for page, edge in [(key[1] - 1, "end"), (key[1] + 1, "start")]:
                near_edge = position <= radius if edge == "end" else position >= len(siblings) - 1 - radius
                neighbor_key = (key[0], page)
                neighbors = self.page_chunks.get(neighbor_key, [])
                if (not adjacent or not near_edge or not neighbors
                        or neighbor_key in self.frontmatter_pages):
                    continue
                indices = (range(max(0, len(neighbors) - adjacent), len(neighbors)) if edge == "end"
                           else range(min(adjacent, len(neighbors))))
                selected.setdefault(neighbor_key, set()).update(indices)
        expanded = []
        for key, indices in selected.items():
            groups = []
            for index in sorted(indices):
                if not groups or index != groups[-1][-1] + 1:
                    groups.append([])
                groups[-1].append(index)
            for group in groups:
                chunks = [self.page_chunks[key][i] for i in group]
                text = chunks[0]["text"]
                end = chunks[0]["end_char"]
                for chunk in chunks[1:]:
                    gap = max(0, chunk["start_char"] - end)
                    overlap = max(0, end - chunk["start_char"])
                    text += " " * gap + chunk["text"][overlap:]
                    end = chunk["end_char"]
                first, last = chunks[0]["id"].rsplit(":C", 1)[1], chunks[-1]["id"].rsplit(":C", 1)[1]
                expanded.append({**chunks[0], "id": f"{key[0]}:P{key[1]:04d}:W{first}-{last}",
                                 "text": text, "retrieval_kind": "page_window",
                                 "end_char": end,
                                 "source_chunk_ids": [c["id"] for c in chunks]})
        return expanded


class Experiment:
    def __init__(self, root, config, retriever, client):
        self.root, self.config = Path(root), config
        self.retriever, self.client = retriever, client

    def prompt(self, name, **fields):
        return (self.root / "prompts" / (name + ".txt")).read_text(encoding="utf-8").format(**fields)

    def context(self, hits):
        cap, parts, used, titled = self.config["context_char_cap"], [], [], set()
        for chunk in hits:
            title = chunk.get("title", chunk["filename"])
            prefix = f'[{chunk["id"]}] página PDF {chunk["page"]}'
            if chunk["doc_id"] not in titled:
                prefix += f'; {title}'
            prefix += "\n"
            remaining = cap - sum(len(s) for s in parts) - 2 * len(parts)
            if remaining <= len(prefix) + 30:
                break
            text = chunk["text"][:remaining - len(prefix)]
            parts.append(prefix + text)
            used.append({**chunk, "text": text})
            titled.add(chunk["doc_id"])
        return "\n\n".join(parts), used

    def answer(self, question, hits, seed, pure=False, feedback="", required_items=None):
        context, used = self.context(hits)
        name = "pure_llm" if pure else "generator"
        allowed = {c["id"] for c in used}
        citation_spec = {"type": "array", "items": {"type": "string"}}
        if allowed and not pure:
            citation_spec["items"]["enum"] = sorted(allowed)
            citation_spec["maxItems"] = len(allowed)
        else:
            citation_spec["maxItems"] = 0
        # A gramática limita os IDs ao contexto efetivamente enviado, sem decidir
        # se a fonte citada sustenta a afirmação. Essa conferência continua separada.
        item_schema = schema({"item": {"type": "string", "minLength": 1,
                                      "maxLength": max(map(len, required_items)) if required_items else 120},
                              **ANSWER_SCHEMA["properties"], "citations": citation_spec})
        if required_items:
            item_schema["properties"]["item"]["enum"] = required_items
        output_schema = schema({"items": {"type": "array", "minItems": len(required_items) if required_items else 1,
                                          "maxItems": len(required_items) if required_items else 8,
                                          "items": item_schema}})
        raw = self.client.generate(self.prompt(name, question=question, context=context, feedback=feedback,
                                              scope=json.dumps(required_items, ensure_ascii=False) if required_items else "todos os pedidos da pergunta"),
                                   output_schema, seed)
        if not isinstance(raw.get("items"), list) or not 1 <= len(raw["items"]) <= 8:
            raise ValueError("Resposta sem itens solicitados.")
        for item in raw["items"]:
            if (not isinstance(item, dict) or set(item) != {"item", "answer", "abstained", "citations"}
                    or not isinstance(item["item"], str) or not item["item"].strip()
                    or not isinstance(item["answer"], str) or not item["answer"].strip()
                    or type(item["abstained"]) is not bool or not isinstance(item["citations"], list)
                    or any(not isinstance(x, str) for x in item["citations"])):
                raise ValueError("Resposta por item fora do contrato.")
        if not required_items:
            seen_counts = {}
            for item in raw["items"]:
                name = item["item"]
                seen_counts[name] = seen_counts.get(name, 0) + 1
                if seen_counts[name] > 1:
                    item["item"] = f"{name} ({seen_counts[name]})"
        names = [item["item"] for item in raw["items"]]
        if len(set(names)) != len(names) or (required_items and set(names) != set(required_items)):
            raise ValueError("Resposta deve cobrir uma vez cada item solicitado.")
        if required_items:
            raw["items"] = sorted(raw["items"], key=lambda item: required_items.index(item["item"]))
        return self.compose(raw["items"], allowed, pure=pure), used

    def compose(self, items, allowed, pure=False):
        result = {"requested_items": [item["item"] for item in items], "item_answers": items,
                  "answer": "\n".join(f'{item["item"]}: {item["answer"].strip()}' for item in items),
                  "abstained": any(item["abstained"] for item in items),
                  "raw_citations": [key for item in items for key in item["citations"]]}
        result["citations"] = list(dict.fromkeys(result["raw_citations"]))
        result["invalid_citations"] = [x for x in result["citations"] if x not in allowed]
        result["citation_contract_ok"] = (not result["invalid_citations"] and
                                          (pure or result["abstained"] or bool(result["citations"])))
        return result

    def verify(self, question, result, hits, preserved_items=()):
        _, used = self.context(hits)
        units = grounding_units(used)
        requested = result["requested_items"]
        item_answers = result["item_answers"]
        if [item["item"] for item in item_answers] != requested:
            raise ValueError("Checklist diverge das respostas por item.")
        if not units:
            return {"reason": "Não há trechos para validar os itens.", "query": " ".join(requested),
                    "supported": False, "answers_question": False, "items": [],
                    "missing_items": requested, "raw_assessment": []}
        support_schema = schema({"supported": {"type": "boolean"}})
        coverage_schema = schema({"complete": {"type": "boolean"}})
        checked, assessments = [], []
        for item in item_answers:
            request, span = item["item"], item["answer"]
            cited_units = [u for u in units if u["source_id"] in item["citations"]]
            candidates = claim_evidence(cited_units, request, span)
            unknown_citations = [key for key in item["citations"] if key not in {u["source_id"] for u in units}]
            context = "\n\n".join(f'[{u["id"]} {u["doc_id"]} p.{u["page"]}] {u["text"]}' for u in candidates)
            support = self.client.generate(self.prompt(
                "verifier", current_item=request, context=context or "Nenhuma passagem citada disponível.", draft=span,
                preserved=json.dumps(list(preserved_items), ensure_ascii=False)), support_schema,
                self.config["control_seed"], role="verifier")
            if set(support) != {"supported"} or type(support["supported"]) is not bool:
                raise ValueError("Verificador sem parecer completo de suporte.")
            quote = "\n".join(u["text"] for u in candidates)
            direct = atomic_identification(request, span, quote) and not item["abstained"]
            if direct:
                coverage = {"complete": True}
            else:
                coverage = self.client.generate(self.prompt(
                    "verifier_coverage", current_item=request, draft=span), coverage_schema,
                    self.config["control_seed"], role="verifier")
                if set(coverage) != {"complete"} or type(coverage["complete"]) is not bool:
                    raise ValueError("Verificador sem parecer completo de cobertura.")
            raw = {**support, **coverage}
            status = "unsupported" if not raw["supported"] else "missing" if not raw["complete"] else "supported"
            quote = "\n".join(u["text"] for u in candidates)
            factual_span = re.sub(r"DOC\d{2}:P\d{4}:[CW][\d-]+", "", span)
            factual_span = re.sub(r"\bpágina\s+(?:PDF\s+)?\d+\b|\bDOC\d{2}\b", "", factual_span, flags=re.I)
            identifiers = set(re.findall(r"[A-Z]{2,}[A-Z0-9_-]*", factual_span))
            flat_quote = re.sub(r"\W+", "", quote.casefold())
            absent_identifiers = sorted(token for token in identifiers
                                        if re.sub(r"\W+", "", token.casefold()) not in flat_quote)
            absent_numbers = sorted(numeric_atoms(factual_span) - numeric_atoms(quote))
            validated = (status == "supported" and not item["abstained"]
                         and bool(candidates) and not unknown_citations and not absent_identifiers and not absent_numbers)
            checked.append({"item": request, "status": status, "factual_support": raw["supported"], "item_complete": raw["complete"], "answer_span": span,
                            "source_units": candidates, "quote": quote, "unknown_citations": unknown_citations,
                            "evidence_ids": [u["id"] for u in candidates],
                            "selection_method": "cited_sentences_by_claim",
                            "coverage_method": "literal_atomic_identification" if direct else "llm_item_coverage",
                            "absent_identifiers": absent_identifiers, "absent_numbers": absent_numbers,
                            "validated": bool(validated)})
            assessments.append(raw)
        missing_items = list(dict.fromkeys(c["item"] for c in checked if not c["validated"]))
        supported = all(c["status"] == "missing" or c["validated"] for c in checked)
        complete = not missing_items
        reason = ("Todos os itens foram aprovados pelo controle."
                  if complete else "Reconferir itens sem resposta e apoio completos: " + "; ".join(missing_items))
        return {"reason": reason, "query": " ".join(missing_items), "supported": supported,
                "answers_question": complete, "items": checked,
                "missing_items": missing_items, "raw_assessment": assessments}

    def execute(self, variant, question, seed, initial_hits=None, mode="full"):
        if variant in {"adaptive", "self_rag"} and self.config.get("control_policy") == "evidence_needs":
            from rag_control import ControlPipeline
            return ControlPipeline(self, question, seed, initial_hits=initial_hits, mode=mode).run(variant)
        if variant not in {"pure_llm", "baseline", "adaptive", "self_rag", "baseline_topk"}:
            raise ValueError(f"Variante desconhecida: {variant}")
        self.client.events.clear()
        self.retriever.reset_dynamic()
        start = time.perf_counter()
        route, rounds, checks, searches, stages, revisions = None, 0, [], [], [], []

        def expand(anchors):
            method = getattr(self.retriever, "expand", None)
            return method(anchors) if method else anchors

        def search(query, top_k=None):
            anchors = self.retriever.search(query, k=top_k) if top_k else self.retriever.search(query)
            hits = expand(anchors)
            searches.append({"query": query, "anchors": anchors, "hits": hits})
            return anchors, hits

        pure = variant == "pure_llm"
        if pure:
            anchors, hits = [], []
            rounds = 0
        elif variant == "baseline_topk":
            diag_k = self.config.get("diagnostic_top_k", 8)
            anchors, hits = search(question, top_k=diag_k)
            rounds = 1
        elif initial_hits is not None and variant == "baseline":
            anchors, hits = [], list(initial_hits)
            rounds = 1
        else:
            if variant == "adaptive":
                route = self.client.generate(self.prompt("router", question=question), ROUTER_SCHEMA,
                                             self.config["control_seed"], role="router")
            pure = route is not None and route["route"] == "direct"
            anchors, hits = ([], []) if pure else (search(question) if initial_hits is None else ([], list(initial_hits)))
            rounds = 0 if pure else 1

        result, used = self.answer(question, hits, seed, pure=pure)
        stages.append({"answer": result, "evidence": used})
        reflective = not pure and (variant == "self_rag" or
                                   (route is not None and route["route"] == "iterative"))
        if reflective:
            check = self.verify(question, result, hits)
            checks.append(check)
            needs_retry = bool(check["missing_items"]) or not result["citation_contract_ok"]
            if needs_retry and rounds < self.config["max_rounds"]:
                targets = check["missing_items"] or result["requested_items"]
                preserved = [item for item in result["item_answers"] if item["item"] not in targets]
                suggested = " ".join(targets)
                doc_ids = list(dict.fromkeys(re.findall(r"\bDOC\d{2}\b", question, flags=re.I)))
                query = " ".join(doc_ids + targets)
                previous_ids = {c["id"] for c in used}
                new_query = query_key(suggested) != query_key(question)
                if new_query and query_key(query) not in {query_key(s["query"]) for s in searches}:
                    _, new_hits = search(query)
                    protected = {key for item in preserved for key in item["citations"]}
                    merged = [c for c in used if c["id"] in protected]
                    seen = {c["id"] for c in merged}
                    for c in [*new_hits, *used]:
                        if c["id"] not in seen:
                            merged.append(c)
                            seen.add(c["id"])
                    hits = merged
                    rounds += 1
                else:
                    new_query = False
                focus_units = evidence_units(self.context(hits)[1])
                focus = []
                for target in targets:
                    for unit in focus_evidence(focus_units, target, "", limit=6)[:2]:
                        if unit not in focus:
                            focus.append(unit)
                feedback_data = {"items_to_recheck": targets,
                                 "preserved_items": preserved,
                                 "source_excerpts": [{"source_id": u["source_id"], "text": u["text"]}
                                                     for u in focus[:4]]}
                revised, used = self.answer(question, hits, seed,
                                           feedback=json.dumps(feedback_data, ensure_ascii=False), required_items=targets)
                partial_check = self.verify(question, revised, hits, preserved_items=preserved)
                new_items = {item["item"]: item for item in revised["item_answers"]}
                result = self.compose([new_items.get(item["item"], item) for item in result["item_answers"]],
                                      {c["id"] for c in used})
                updated = {item["item"]: item for item in partial_check["items"]}
                previous = {item["item"]: item for item in check["items"]}
                merged_checks = [updated.get(name, previous.get(name, {"item": name, "status": "missing", "validated": False}))
                                 for name in result["requested_items"]]
                missing = [item["item"] for item in merged_checks if not item["validated"]]
                final_check = {**partial_check, "items": merged_checks, "missing_items": missing,
                               "answers_question": not missing,
                               "supported": all(item["status"] == "missing" or item["validated"] for item in merged_checks),
                               "query": " ".join(missing), "preserved_item_names": [item["item"] for item in preserved]}
                checks.append(final_check)
                revisions.append({"query_origin": "missing_items", "suggested_query": suggested,
                                  "new_search": new_query, "new_evidence_ids": sorted(
                                      {c["id"] for c in used} - previous_ids),
                                  "preserved_item_names": [item["item"] for item in preserved],
                                  "revised_item_names": targets,
                                  "action": "retrieve_and_revise_items" if new_query else "revise_items_existing_context",
                                  "feedback": feedback_data})
                stages.append({"answer": result, "evidence": used})
            missing = set(checks[-1]["missing_items"])
            if missing:
                final_items = [{**item, "answer": "Não encontrei evidências suficientes nos documentos para responder a este item.",
                                "abstained": True, "citations": []} if item["item"] in missing else item
                               for item in result["item_answers"]]
                result = self.compose(final_items, {c["id"] for c in used})
                result["control_abstention"] = True
        events = list(self.client.events)
        llm = [e for e in events if e["role"] != "embedding"]
        return {"variant": variant, "seed": seed, "question": question,
                "answer": result["answer"], "abstained": result["abstained"],
                "citations": result["citations"], "citation_contract_ok": result["citation_contract_ok"],
                "route": route, "retrieval_rounds": rounds, "retrieval_calls": len(searches),
                "llm_calls": len(llm), "embedding_calls": len(events) - len(llm),
                "prompt_tokens": sum(e.get("prompt_eval_count") or 0 for e in llm),
                "output_tokens": sum(e.get("eval_count") or 0 for e in llm),
                "latency_seconds": time.perf_counter() - start,
                "checks": checks, "searches": searches, "stages": stages, "revisions": revisions, "events": events,
                "final_evidence": used, "control_abstention": result.get("control_abstention", False),
                "initial_context_constructed": (initial_hits is not None),
                "evaluation_mode": mode}


def validate_questions(dataset, corpus, config):
    questions = dataset["questions"]
    if len(corpus["documents"]) != config["expected_documents"]:
        raise ValueError(f'A avaliação oficial exige {config["expected_documents"]} PDFs distintos.')
    if len(questions) != config["expected_questions"]:
        raise ValueError(f'A avaliação oficial exige {config["expected_questions"]} perguntas revisadas.')
    if dataset.get("corpus_fingerprint") != corpus["fingerprint"]:
        raise ValueError("Fixe corpus_fingerprint em questions.json após conferir o corpus.")
    ids, docs = set(), {d["doc_id"]: d for d in corpus["documents"]}
    chunk_ids = {c["id"] for c in corpus.get("chunks", [])}
    for q in questions:
        required = {"id", "question", "difficulty", "kind", "answerable", "expected_answer", "rubric", "evidence"}
        if required - q.keys() or q["id"] in ids:
            raise ValueError(f"Pergunta incompleta ou ID duplicado: {q.get('id')}")
        ids.add(q["id"])
        if type(q["answerable"]) is not bool or not q["rubric"] or not q["expected_answer"].strip():
            raise ValueError(f"Gabarito inválido: {q['id']}")
        if q["answerable"] and not q["evidence"]:
            raise ValueError(f"Faltam evidências verificadas: {q['id']}")
        if "scenario" in q and q["scenario"] not in {"direct", "two_step", "distractor", "unanswerable"}:
            raise ValueError(f"Cenário experimental inválido: {q['id']} ({q.get('scenario')})")
        if "controlled_initial_chunks" in q and chunk_ids:
            for cid in q["controlled_initial_chunks"]:
                if cid not in chunk_ids:
                    raise ValueError(f"Chunk controlado inexistente no corpus: {cid} em {q['id']}")
        for ev in q["evidence"]:
            if ev["doc_id"] not in docs or not 1 <= ev["page"] <= docs[ev["doc_id"]]["pages"]:
                raise ValueError(f"Referência de página inválida: {q['id']}")
            if not ev.get("note", "").strip():
                raise ValueError(f"Explique a evidência em note: {q['id']}")


def runtime_signature(root, config, dataset, corpus, models):
    root = Path(root)
    files = [root / "rag_lab.py", root / "configs/experiment.json", *sorted((root / "prompts").glob("*.txt"))]
    if config.get("control_policy") == "evidence_needs":
        files.append(root / "rag_control.py")
    packages = {p: importlib.metadata.version(p) for p in
                ["numpy", "scikit-learn", "pypdf", "requests", "pandas"]}
    used_models = [config["generator_model"]]
    if config["retriever"] != "tfidf":
        used_models.append(config["embedding_model"])
    return {"config": config, "questions": dataset, "corpus": corpus["documents"],
            "source_hashes": {str(p.relative_to(root)): file_sha(p) for p in files},
            "models": {name: models[name] for name in used_models}, "packages": packages}


def run_experiment(experiment, corpus, dataset, resume_dir=None, mode="controlled"):
    cfg, root = experiment.config, experiment.root
    validate_questions(dataset, corpus, cfg)
    models = experiment.client.models()
    signature = runtime_signature(root, cfg, dataset, corpus, models)
    signature_hash = fingerprint(signature)
    now = datetime.now(timezone.utc)
    if resume_dir:
        folder = Path(resume_dir).resolve()
        manifest = read_json(folder / "run_manifest.json")
        if manifest["fingerprint"] != signature_hash:
            raise ValueError("Configuração, corpus, modelos, perguntas ou código mudaram: crie outra run.")
    else:
        folder = root / cfg["results_dir"] / (now.strftime("%Y%m%dT%H%M%S%fZ_") + signature_hash[:10])
        folder.mkdir(parents=True, exist_ok=False)
        manifest = {"fingerprint": signature_hash, "created_at_utc": now.isoformat(),
                    "signature": signature, "platform": platform.platform(),
                    "machine": platform.machine(), "status": "running",
                    "evaluation_mode": mode,
                    "measurement_policy": f"Modo {mode}. Consulta inicial pré-computada em modo controlado; consultas adicionais contadas. Warmup fora da latência; geração e controle reais contados. Sem cache de roteamento."}
        write_json(folder / "run_manifest.json", manifest)
    trace_path = folder / "traces.jsonl"
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()] if trace_path.exists() else []
    keys = {(r["question_id"], r["variant"], r["repetition"]) for r in records}
    if len(keys) != len(records):
        raise ValueError("Trace tem chaves duplicadas; conferir antes de retomar.")
    expected = {(q["id"], variant, rep) for q in dataset["questions"]
                for variant in cfg["variants"] for rep in range(1, len(cfg["seeds"]) + 1)}
    if not keys <= expected or any(r["run_fingerprint"] != signature_hash or
                                  r["seed"] != cfg["seeds"][r["repetition"] - 1] for r in records):
        raise ValueError("Trace não corresponde ao manifesto e às entradas da run.")
    if records:
        export_results(folder, records)
    experiment.client.events.clear()
    experiment.retriever.prefetch([q["question"] for q in dataset["questions"]])
    experiment.client.generate("Responda JSON: answer=OK, abstained=false, citations=[].", ANSWER_SCHEMA,
                               cfg["control_seed"])
    setup_file = folder / "setup_events.json"
    sessions = read_json(setup_file) if setup_file.exists() else []
    sessions.append({"at_utc": now.isoformat(), "events": experiment.client.events})
    write_json(setup_file, sessions)
    chunk_map = {c["id"]: c for c in corpus["chunks"]}
    try:
        for variant in cfg["variants"]:
            for repetition, seed in enumerate(cfg["seeds"], 1):
                for q in dataset["questions"]:
                    key = (q["id"], variant, repetition)
                    if key in keys:
                        continue
                    if mode == "controlled":
                        initial_chunks = q.get("controlled_initial_chunks", [])
                        initial_hits = [{**chunk_map[cid], "retrieval_kind": "controlled_initial_chunk"}
                                        for cid in initial_chunks if cid in chunk_map]
                    else:
                        initial_hits = None
                    record = experiment.execute(variant, q["question"], seed, initial_hits=initial_hits, mode=mode)
                    record.update(question_id=q["id"], repetition=repetition,
                                  difficulty=q["difficulty"], kind=q["kind"],
                                  scenario=q.get("scenario", q["kind"]),
                                  evaluation_mode=mode,
                                  initial_context_constructed=(mode == "controlled"),
                                  controlled_initial_chunks=q.get("controlled_initial_chunks", []),
                                  run_fingerprint=signature_hash)
                    with trace_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    records.append(record)
                    keys.add(key)
                    export_results(folder, records)
                    print(f'{variant} r{repetition} {q["id"]}: {record["latency_seconds"]:.1f}s, {record["llm_calls"]} chamadas')
        manifest["status"] = "complete"
    except (Exception, KeyboardInterrupt) as exc:
        manifest["status"] = "interrupted"
        write_json(folder / "interruption.json", {"error": f"{type(exc).__name__}: {exc}",
                                                  "events": experiment.client.events})
        raise
    finally:
        manifest["completed_answers"] = len(records)
        write_json(folder / "run_manifest.json", manifest)
        experiment.client.unload(cfg["generator_model"])
    return folder


def export_results(folder, records):
    import pandas as pd
    folder = Path(folder)
    fields = ["question_id", "scenario", "variant", "repetition", "seed", "difficulty", "kind", "question", "answer",
              "abstained", "citations", "citation_contract_ok", "evaluation_mode", "initial_context_constructed",
              "retrieval_rounds", "retrieval_calls", "llm_calls", "embedding_calls", "prompt_tokens", "output_tokens", "latency_seconds"]
    write_csv(folder / "answers.csv", records, fields)
    frame = pd.DataFrame(records)
    for (variant, rep), group in frame.groupby(["variant", "repetition"]):
        write_csv(folder / f"{variant}_r{rep}.csv", group.to_dict("records"), fields)
    summary = frame.groupby("variant").agg(
        answers=("answer", "size"), declared_abstention_rate=("abstained", "mean"),
        llm_calls_mean=("llm_calls", "mean"), retrieval_calls_mean=("retrieval_calls", "mean"),
        latency_mean_seconds=("latency_seconds", "mean"), latency_median_seconds=("latency_seconds", "median"))
    summary.to_csv(folder / "summary_process.csv")
    evaluation_path = folder / "evaluation.csv"
    old = {}
    if evaluation_path.exists():
        with evaluation_path.open(newline="", encoding="utf-8") as stream:
            reviews = list(csv.DictReader(stream))
            old = {(r["question_id"], r["variant"], int(r["repetition"])): r for r in reviews}
            if len(old) != len(reviews):
                raise ValueError("evaluation.csv contém chaves duplicadas; revisão preservada para conferência.")
    manifest_file = folder / "run_manifest.json"
    question_map = {}
    if manifest_file.exists():
        question_map = {q["id"]: q for q in read_json(manifest_file)["signature"]["questions"]["questions"]}
    rows = []
    for r in records:
        key = (r["question_id"], r["variant"], r["repetition"])
        q = question_map.get(r["question_id"], {})
        row = {"question_id": key[0], "scenario": r.get("scenario", q.get("scenario", "")),
               "variant": key[1], "repetition": key[2],
               "question": r.get("question", ""), "answer": r["answer"],
               "expected_answer": q.get("expected_answer", ""), "rubric": q.get("rubric", []),
               "expected_evidence": q.get("evidence", []), "citations": r.get("citations", []),
               "evaluation_mode": r.get("evaluation_mode", ""),
               "human_verdict": "", "human_supported": "", "human_abstained": "", "reviewer": "", "note": ""}
        prior = old.get(key, {})
        row.update({k: prior.get(k, "") for k in ["human_verdict", "human_supported", "human_abstained", "reviewer", "note"]})
        rows.append(row)
    write_csv(evaluation_path, rows)


def run_baseline_diagnostic(experiment, corpus, dataset, top_k_list=(4, 8, 12)):
    """Avaliação diagnóstica do baseline com diferentes valores de top_k."""
    cap = experiment.config.get("context_char_cap", 6500)
    results = []
    for k in top_k_list:
        for q in dataset["questions"]:
            anchors = experiment.retriever.search(q["question"], k=k)
            expand = getattr(experiment.retriever, "expand", lambda x: x)
            hits = expand(anchors)
            raw_chars = sum(len(h.get("text", "")) for h in hits)
            prompt_context, used = experiment.context(hits)
            provided_chars = len(prompt_context)
            truncated = len(used) < len(hits) or raw_chars > cap
            results.append({
                "question_id": q["id"],
                "scenario": q.get("scenario", q.get("kind")),
                "top_k": k,
                "anchors_count": len(anchors),
                "expanded_windows_count": len(hits),
                "used_windows_count": len(used),
                "raw_text_chars": raw_chars,
                "context_char_cap": cap,
                "provided_context_chars": provided_chars,
                "truncated": truncated,
                "discarded_windows_count": len(hits) - len(used),
                "retrieved_chunk_ids": [a["id"] for a in anchors],
                "used_passage_ids": [u["id"] for u in used]
            })
    return results


def summarize_human(folder):
    import pandas as pd
    folder = Path(folder)
    answers = pd.read_csv(folder / "answers.csv")
    reviews = pd.read_csv(folder / "evaluation.csv", keep_default_na=False)
    keys = ["question_id", "variant", "repetition"]
    review_fields = keys + ["human_verdict", "human_supported", "human_abstained", "reviewer", "note"]
    merged = answers.merge(reviews[review_fields], on=keys, how="left", validate="one_to_one")
    if len(reviews) != len(answers) or not merged.human_verdict.isin(["CORRECT", "INCORRECT"]).all():
        raise ValueError("Complete a revisão humana de todas as respostas antes de calcular acurácia.")
    if not merged.human_supported.isin(["YES", "NO", "NA"]).all() or not merged.reviewer.fillna("").str.strip().all():
        raise ValueError("Preencha human_supported (YES/NO/NA) e reviewer.")
    if not merged.human_abstained.isin(["YES", "NO"]).all():
        raise ValueError("Preencha human_abstained (YES/NO); a declaração do modelo pode estar errada.")
    merged["correct"] = merged.human_verdict.eq("CORRECT")
    rows = []
    for variant, frame in merged.groupby("variant"):
        answered = frame.human_abstained.eq("NO")
        rows.append({"variant": variant, "n": len(frame), "accuracy_human": frame.correct.mean(),
                     "coverage_human": answered.mean(), "coverage_declared": (~frame.abstained).mean(),
                     "precision_answered_human": frame.loc[answered, "correct"].mean() if answered.any() else None})
    summary = pd.DataFrame(rows)
    summary.to_csv(folder / "summary_quality.csv", index=False)
    merged.to_csv(folder / "evaluated_answers.csv", index=False)
    return summary


def automatic_review(experiment, folder, dataset):
    """Parecer auxiliar do mesmo modelo pequeno; não alimenta a acurácia humana."""
    folder = Path(folder)
    frozen = read_json(folder / "run_manifest.json")["signature"]["questions"]
    if fingerprint(frozen) != fingerprint(dataset):
        raise ValueError("Rubricas mudaram após a run; use o conjunto congelado no manifesto.")
    records = [json.loads(line) for line in (folder / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    questions = {q["id"]: q for q in dataset["questions"]}
    rows, cache = [], {}
    for r in records:
        key = (r["question_id"], r["answer"])
        if key not in cache:
            q = questions[key[0]]
            before = len(experiment.client.events)
            result = experiment.client.generate(experiment.prompt(
                "judge", question=q["question"], answerable=q["answerable"],
                rubric=json.dumps(q["rubric"], ensure_ascii=False), answer=r["answer"]),
                JUDGE_SCHEMA, experiment.config["control_seed"], role="judge")
            cache[key] = {**result, "events": experiment.client.events[before:]}
        rows.append({"question_id": r["question_id"], "variant": r["variant"], "repetition": r["repetition"],
                     "model": experiment.config["generator_model"], **cache[key]})
    write_csv(folder / "automatic_evaluation.csv", rows)
    return rows
