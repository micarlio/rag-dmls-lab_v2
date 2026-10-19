"""Controle por necessidades do pedido e passagens literais; sem gabaritos."""
from __future__ import annotations

import re
import time

from rag_lab import grounding_units, focus_evidence, query_key, schema


PLAN_SCHEMA = schema({
    'route': {'type': 'string', 'enum': ['direct', 'single', 'iterative']},
    'reason': {'type': 'string'},
    'needs': {'type': 'array', 'minItems': 1, 'maxItems': 5, 'items': schema({
        'request': {'type': 'string', 'minLength': 1, 'maxLength': 240},
        'query': {'type': 'string', 'minLength': 1, 'maxLength': 160}})}})
def read_label(text, prefix, allowed, default):
    labels = re.findall(r'(?im)^\s*' + re.escape(prefix) + r'\s*:\s*([A-Z_]+)\s*[.!]?\s*$', text)
    return labels[0] if len(labels) == 1 and labels[0] in allowed else default


def literal_numbers(text):
    # Artigos como 'uma' não são o número 1; ausência de numeral é apenas um
    # guard auxiliar, nunca prova de relação causal ou associação de valores.
    from decimal import Decimal
    return {str(Decimal(n.replace(',', '.')).normalize())
            for n in re.findall(r'(?<!\w)\d+(?:[.,]\d+)?(?!\w)', text)}


def is_structural_coverage_complete(request, answer, support, context):
    """Identificações simples sustentadas não devem ser rebaixadas a parcial pelo 3B."""
    if support != 'supported':
        return False
    ans_clean = answer.strip()
    if not ans_clean or len(ans_clean) > 160 or ans_clean.lower().startswith('não'):
        return False
    req_lower = f" {request.lower()} "
    if re.search(r'\b(e|bem como|versus)\b', req_lower):
        return False
    words = [w for w in re.findall(r'\b\w+\b', ans_clean)
             if (len(w) >= 2 or any(c.isdigit() for c in w)) and w.lower() not in {'para', 'com', 'por', 'uma', 'que', 'dos', 'das', 'foi', 'são', 'de', 'do', 'da'}]
    return bool(words and any(w.lower() in context.lower() for w in words))


def verify_evidence_found(need, chosen):
    """Verifica se os trechos selecionados contêm termos específicos solicitados na necessidade."""
    if not chosen:
        return 'missing'
    text = ' '.join(u['text'] for u in chosen).lower()
    raw = f"{need.get('request', '')} {need.get('query', '')}"
    stopwords = {
        'projeto', 'sistema', 'documento', 'tcc', 'doc01', 'doc02', 'doc03', 'doc04', 'doc05',
        'sobre', 'para', 'como', 'qual', 'quais', 'onde', 'quando', 'quem', 'porque', 'descrição',
        'motivo', 'necessidade', 'atividade', 'junto', 'função', 'código', 'dados', 'arquivo'
    }
    specific = {w.lower() for w in re.findall(r'\b[A-Za-z0-9_]{3,}\b', raw)
                if (w[0].isupper() or any(c.isdigit() for c in w) or '_' in w) and w.lower() not in stopwords}
    if specific and not any(s in text for s in specific):
        return 'partial'
    return 'found'


def source_passage(unit):
    """O texto é copiado da fonte, nunca composto por um modelo."""
    return {'id': f"{unit['doc_id']}:P{unit['page']:04d}:L{unit['start_char']}-{unit['end_char']}",
            'doc_id': unit['doc_id'], 'page': unit['page'], 'text': unit['text'],
            'start_char': unit['start_char'], 'end_char': unit['end_char'],
            'filename': unit.get('filename', unit['doc_id']+'.pdf'),
            'title': unit.get('title', unit.get('filename', unit['doc_id'])),
            'origin_source_id': unit['source_id'], 'retrieval_kind': 'literal_sentence'}


def choose_revision(original, old_check, candidate, new_check):
    """Incompletude isolada nunca apaga uma afirmação já sustentada."""
    old_supported = old_check['support'] == 'supported'
    new_supported = new_check['support'] == 'supported'
    if new_supported and (not old_supported or new_check['preserves_previous']):
        return candidate, 'revised'
    if old_supported:
        return original, 'kept_supported_original'
    return {**original, 'answer': 'Não localizei evidência suficiente para responder a esta parte.',
            'abstained': True, 'citations': []}, 'abstained_unsupported_part'


class ControlPipeline:
    def __init__(self, experiment, question, seed, initial_hits=None, mode="full"):
        self.exp, self.question, self.seed = experiment, question, seed
        self.cfg, self.client = experiment.config, experiment.client
        self.initial_hits = list(initial_hits) if initial_hits is not None else None
        self.mode = mode
        self.searches, self.stages, self.checks, self.revisions = [], [], [], []
        self.ledger, self.plan = {}, None
        self.docs = list(dict.fromkeys(re.findall(r'\bDOC\d{2}\b', question.upper())))
        self.max_searches = self.cfg.get('max_control_searches', 3)

    def plan_question(self):
        value = self.client.generate(self.exp.prompt('planner', question=self.question),
                                     PLAN_SCHEMA, self.cfg['control_seed'], role='planner')
        needs = value.get('needs')
        if not isinstance(needs, list) or not 1 <= len(needs) <= 5:
            raise ValueError('Plano sem necessidades válidas.')
        for need in needs:
            if (set(need) != {'request', 'query'} or
                    any(not isinstance(need[k], str) or not need[k].strip() for k in need)):
                raise ValueError('Necessidade fora do contrato.')
        unique_needs, seen_names = [], set()
        for need in needs:
            name = need['request'].strip()
            if name not in seen_names:
                unique_needs.append(need)
                seen_names.add(name)
        value['needs'] = unique_needs
        if not unique_needs:
            raise ValueError('Plano sem necessidades válidas.')
        # Uma decisão direct equivocada não dispensa fonte de um TCC explícito.
        if self.docs and value['route'] == 'direct':
            value = {**value, 'route': 'single', 'direct_overridden_for_document': True}
        self.plan = value
        return value

    def search(self, query):
        if len(self.searches) >= self.max_searches:
            return []
        anchors = self.exp.retriever.search(query)
        expand = getattr(self.exp.retriever, 'expand', lambda x: x)
        hits = expand(anchors)
        self.searches.append({'query': query, 'anchors': anchors, 'hits': hits})
        return hits

    def targeted_query(self, need):
        # O controlador não pode escolher outro TCC fora do escopo do usuário.
        text = re.sub(r'\bDOC\d{2}\b', '', need['query'], flags=re.I).strip()
        return ' '.join([*self.docs, text])

    def gather(self, need, hits):
        units = grounding_units(hits)
        candidates = focus_evidence(units, need['request'], need['query'], limit=6)
        # Um pacote limitado por chamada, com trechos literais e seus offsets.
        selected, size = [], 0
        for unit in candidates:
            if size + len(unit['text']) > self.cfg.get('evidence_char_cap', 5500):
                continue
            selected.append(unit); size += len(unit['text'])
        if not selected:
            entry = {'status': 'missing', 'units': []}
        else:
            ids = [u['id'] for u in selected]
            output = schema({'status': {'type': 'string', 'enum': ['found', 'partial', 'missing']},
                'unit_ids': {'type': 'array', 'maxItems': 4,
                             'items': {'type': 'string', 'enum': ids}}})
            context = '\n\n'.join(f"[{u['id']}] {u['text']}" for u in selected)
            value = self.client.generate(self.exp.prompt('evidence_select', question=self.question,
                request=need['request'], context=context), output, self.cfg['control_seed'], role='evidence')
            if value['status'] not in {'found', 'partial', 'missing'} or any(i not in ids for i in value['unit_ids']):
                raise ValueError('Seleção aponta para trecho inexistente.')
            chosen = [u for u in selected if u['id'] in value['unit_ids']]
            status = value['status']
            if chosen and status == 'missing':
                status = 'partial'
            elif not chosen and status != 'missing':
                status = 'missing'
            if status == 'found' and chosen:
                status = verify_evidence_found(need, chosen)
            entry = {'status': status, 'units': chosen}
        old = self.ledger.get(need['request'])
        # Uma busca ruim não substitui evidência já obtida. Conserva trechos
        # complementares, sem alegar que a união automaticamente cobre o pedido.
        if old:
            rank = {'missing': 0, 'partial': 1, 'found': 2}
            if rank[old['status']] > rank[entry['status']]:
                entry['status'] = old['status']
            existing = {(u['source_id'], u['start_char'], u['end_char']) for u in entry['units']}
            entry['units'] += [u for u in old['units'] if
                (u['source_id'], u['start_char'], u['end_char']) not in existing]
        self.ledger[need['request']] = entry
        return entry

    def pack(self, pinned=()):
        # Rodízio entre necessidades; uma página longa não ocupa o orçamento
        # antes que outras necessidades possam receber ao menos uma passagem.
        passages, seen = [], set()
        for passage in pinned:
            if passage['id'] not in seen:
                passages.append(passage); seen.add(passage['id'])
        groups = [self.ledger.get(n['request'], {}).get('units', []) for n in self.plan['needs']]
        for index in range(max((len(g) for g in groups), default=0)):
            for group in groups:
                if index < len(group):
                    passage = source_passage(group[index])
                    if passage['id'] not in seen:
                        passages.append(passage); seen.add(passage['id'])
        # context() é o mesmo empacotador/limite usado pelo baseline.
        return self.exp.context(passages)[1]

    def feedback(self, preserved=()):
        import json
        return json.dumps({'requirements_from_original_question': self.plan['needs'],
            'preserved_items': list(preserved),
            'evidence_map': [{'request': n['request'], 'status': self.ledger.get(n['request'], {}).get('status', 'not_checked'),
                'source_ids': [source_passage(u)['id'] for u in self.ledger.get(n['request'], {}).get('units', [])]}
                for n in self.plan['needs']]}, ensure_ascii=False)

    def assess(self, item, hits, previous=''):
        allowed = {p['id']: p for p in hits}
        cited = [allowed[i] for i in item['citations'] if i in allowed]
        # Recusa também é conferida: ausência em top-k não prova inexistência.
        sources = cited or (hits if item['abstained'] else [])
        units = focus_evidence(grounding_units(sources), item['item'], item['answer'], limit=6)
        context = '\n\n'.join(u['text'] for u in units)[:self.cfg.get('evidence_char_cap', 5500)]
        support_text = self.client.generate_text(self.exp.prompt('claim_support',
            request=item['item'], answer=item['answer'], context=context or 'Nenhuma fonte de apoio.'),
            self.cfg['control_seed'], role='claim_support')
        coverage_text = self.client.generate_text(self.exp.prompt('claim_coverage',
            request=item['item'], answer=item['answer']), self.cfg['control_seed'], role='claim_coverage')
        support = read_label(support_text, 'VEREDITO', {'CORRETA','INCORRETA','SEM_APOIO'}, 'SEM_APOIO')
        coverage = read_label(coverage_text, 'COBERTURA', {'COMPLETA','PARCIAL'}, 'PARCIAL')
        preservation_text = ''
        if previous:
            preservation_text = self.client.generate_text(self.exp.prompt('claim_preservation',
                request=item['item'], answer=item['answer'], previous=previous),
                self.cfg['control_seed'], role='claim_preservation')
        preserves = not previous or read_label(preservation_text, 'PRESERVA', {'SIM','NAO'}, 'NAO') == 'SIM'
        supp_label = {'CORRETA':'supported', 'INCORRETA':'contradicted', 'SEM_APOIO':'uncertain'}[support]
        cov_label = {'COMPLETA':'complete', 'PARCIAL':'partial'}[coverage]
        if cov_label == 'partial' and is_structural_coverage_complete(item['item'], item['answer'], supp_label, context):
            cov_label = 'complete'
        value = {'support': supp_label,
                 'coverage': cov_label,
                 'preserves_previous': preserves,
                 'raw_assessment': {'support':support_text,'coverage':coverage_text,'preservation':preservation_text}}
        # Só afirmações positivas exigem citação e conferência literal auxiliar.
        absent_numbers = literal_numbers(item['answer']) - literal_numbers(context)
        if not item['abstained'] and (not cited or absent_numbers or len(cited) != len(item['citations'])):
            value = {**value, 'support': 'uncertain', 'literal_guard_failed': True}
        if item['abstained'] and not context:
            value = {**value, 'support': 'uncertain'}
        return {**value, 'item': item['item'], 'answer_span': item['answer'],
                'quote': context, 'source_ids': [p['id'] for p in cited]}

    def run(self, variant):
        self.client.events.clear(); self.exp.retriever.reset_dynamic()
        started = time.perf_counter()
        plan = self.plan_question()
        names = [n['request'] for n in plan['needs']]
        if self.initial_hits is not None:
            pure = False
            hits = list(self.initial_hits)
            _, initial_used = self.exp.context(hits)
        else:
            pure = plan['route'] == 'direct' and not self.docs and variant == 'adaptive'
            hits = [] if pure else self.search(self.question)
            _, initial_used = self.exp.context(hits)

        if variant == 'adaptive' and (plan['route'] == 'iterative' or self.mode == 'controlled'):
            for need in plan['needs']:
                self.gather(need, initial_used)
            for need in plan['needs']:
                if self.ledger[need['request']]['status'] != 'found' and len(self.searches) < self.max_searches:
                    query = self.targeted_query(need)
                    if query_key(query) not in {query_key(s['query']) for s in self.searches}:
                        self.gather(need, self.search(query))
            packed = self.pack()
            # Falha de seleção não remove o contexto inicial de um baseline competente.
            hits = packed or initial_used
        result, used = self.exp.answer(self.question, hits, self.seed, pure=pure,
            required_items=names, feedback=self.feedback())
        self.stages.append({'answer': result, 'evidence': used})
        if variant == 'self_rag':
            for need in plan['needs']:
                self.gather(need, initial_used)
            before = [self.assess(item, used) for item in result['item_answers']]
            self.checks.append({'items': before})
            by_name = {c['item']: c for c in before}
            targets = [item['item'] for item in result['item_answers'] if
                by_name[item['item']]['support'] != 'supported' or
                by_name[item['item']]['coverage'] == 'partial']
            if targets:
                original = {i['item']: i for i in result['item_answers']}
                preserved = [i for i in result['item_answers'] if i['item'] not in targets]
                prior_ids = {p['id'] for p in used}
                for need in plan['needs']:
                    if need['request'] in targets and len(self.searches) < self.max_searches:
                        query = self.targeted_query(need)
                        if query_key(query) not in {query_key(s['query']) for s in self.searches}:
                            self.gather(need, self.search(query))
                # Mantém também fontes de respostas sustentadas porém parciais,
                # para que uma revisão pior possa ser revertida literalmente.
                protected = {c for i in result['item_answers'] if by_name[i['item']]['support'] == 'supported'
                             for c in i['citations']}
                pinned = [p for p in used if p['id'] in protected]
                packed = self.pack(pinned) or used
                revised_candidates = []
                revision_used = packed
                for target in targets:
                    rev_part, rev_used = self.exp.answer(self.question, packed, self.seed,
                        required_items=[target], feedback=self.feedback(preserved))
                    revised_candidates.extend(rev_part['item_answers'])
                    revision_used = rev_used
                # Assegura que todas as passagens empacotadas estejam acessíveis às citações
                used_by_id = {p['id']: p for p in packed}
                for p in revision_used:
                    used_by_id[p['id']] = p
                revision_used = list(used_by_id.values())
                revised = {'item_answers': revised_candidates}
                after, items, actions = [], dict(original), []
                for candidate in revised['item_answers']:
                    name = candidate['item']; old = original[name]
                    check = self.assess(candidate, revision_used,
                        previous=old['answer'] if by_name[name]['support'] == 'supported' else '')
                    item, action = choose_revision(old, by_name[name], candidate, check)
                    # Uma fonte preservada tem que estar no contexto final real.
                    if any(c not in {p['id'] for p in revision_used} for c in item['citations']):
                        raise ValueError('Revisão perdeu fonte preservada.')
                    items[name] = item; after.append(check); actions.append({'item': name, 'action': action})
                used = revision_used
                result = self.exp.compose([items[n] for n in names], {p['id'] for p in used})
                self.checks.append({'items': after})
                self.revisions.append({'revised_item_names': targets,
                    'preserved_item_names': [i['item'] for i in preserved], 'actions': actions,
                    'new_evidence_ids': sorted({p['id'] for p in used}-prior_ids)})
                self.stages.append({'answer': result, 'evidence': used})
        events = list(self.client.events)
        llm = [e for e in events if e['role'] != 'embedding']
        return {'variant': variant, 'seed': self.seed, 'question': self.question,
            **{k: result[k] for k in ['answer', 'abstained', 'citations', 'citation_contract_ok']},
            'route': plan if variant == 'adaptive' else None, 'plan': plan, 'evidence_ledger': self.ledger,
            'control_policy': 'evidence_needs', 'retrieval_rounds': len(self.searches),
            'retrieval_calls': len(self.searches), 'llm_calls': len(llm), 'embedding_calls': len(events)-len(llm),
            'prompt_tokens': sum(e.get('prompt_eval_count') or 0 for e in llm),
            'output_tokens': sum(e.get('eval_count') or 0 for e in llm),
            'latency_seconds': time.perf_counter()-started, 'checks': self.checks,
            'searches': self.searches, 'stages': self.stages, 'revisions': self.revisions,
            'events': events, 'final_evidence': used,
            'initial_context_constructed': (self.initial_hits is not None),
            'evaluation_mode': self.mode,
            'control_abstention': any(a['action']=='abstained_unsupported_part' for r in self.revisions for a in r['actions'])}
