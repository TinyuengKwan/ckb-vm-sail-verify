#!/usr/bin/env python3
"""Strict scoped-token correspondence of the two recorded Sail C++ outputs.

Read-only comparison, not a C++ parser, macro-expansion proof, ABI proof or
execution-equivalence claim. All bytes except bijective generated identifier
renames and their exact generated comments must agree, in the original order.
"""
from collections import Counter
from itertools import zip_longest
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_rebuilt_public_kernel as evidence

require, sha = evidence.require, evidence.sha
TOKEN = re.compile(
    r'(?P<raw>(?:u8|u|U|L)?R")|(?P<comment>//[^\n]*|/\*.*?\*/)|'
    r'(?P<string>"(?:\\[\s\S]|[^"\\\n])*")|'
    r"(?P<char>'(?:\\[\s\S]|[^'\\\n])*')|"
    r'(?P<space>\s+)|(?P<id>[A-Za-z_]\w*)|(?P<other>.)', re.S)
FIELD = re.compile(r'z0zE\d+\Z')
LOCAL = re.compile(r'(z[1-9]\d*zE|zuz)(\d+)\Z')
LABEL = re.compile(r'(case_|finish_match_|end_block_exception_|end_function_|cleanup_|end_cleanup_|'
                   r'fundef_body_|for_start_|for_end_|repeat_|until_|try_|post_exception_handlers_|while_|wend_)(\d+)\Z')
METHOD = re.compile(r'^(?:[A-Za-z_][\w:*&<> ]* )?Model::(~?[A-Za-z_]\w*)\([^\n]*\)[ \t]*(?:\{)?[ \t]*$', re.M)
DECL = re.compile(r'^  // register zz50zE(\d+)\n  ([^;\n]+) (z0zE\d+) = \{\};$', re.M)
COMMENT = re.compile(r'(?:/\* lifted zz50zE(\d+) \*/|// register zz50zE(\d+))\Z')


def tokens(text):
    pos = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        require(match is not None, 'unrecognized lexical input')
        kind, value = match.lastgroup, match[0]
        require(kind != 'raw', 'raw C++ strings not supported by this scoped scanner')
        require(not (kind == 'other' and (value in ('"', "'") or text.startswith('/*', pos))),
                'unterminated or unsupported literal/comment')
        yield kind, value
        pos = match.end()


def regions(text):
    """Only the actual generated single-line Model method format is admitted.

    Balanced lexical braces validate each span; unmatched text is still checked
    as a gap, never discarded. No declarations or functions are reordered.
    """
    result, last = [], 0
    matches = list(METHOD.finditer(text))
    for index, match in enumerate(matches):
        require(match.start() >= last, 'overlapping method regions')
        # Constructors use an indented closing brace. Find the lexical balance,
        # not a particular column or the next function's closing brace. The
        # remaining gap is retained and compared separately by analyze().
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():limit]
        depth, opened, closed, consumed = 0, False, False, 0
        for kind, value in tokens(body):
            consumed += len(value)
            if kind == 'other' and value == '{':
                depth += 1; opened = True
            elif kind == 'other' and value == '}':
                depth -= 1
                require(depth >= 0, 'unbalanced method braces')
                if depth == 0:
                    closed = True
                    break
        require(opened and closed and depth == 0, 'incomplete method body')
        end = match.start() + consumed
        result.append((match[1], match.start(), end))
        last = end
    require(result and len({name for name, _, _ in result}) == len(result), 'missing or duplicate method name')
    return result


class Bijection:
    def __init__(self):
        self.forward, self.backward = {}, {}
        self.occurrences = 0

    def bind(self, left, right):
        require(self.forward.get(left, right) == right and self.backward.get(right, left) == left,
                'inconsistent or non-injective generated-name correspondence: ' + left + ' -> ' + right)
        self.forward[left] = right; self.backward[right] = left; self.occurrences += 1

    def changed(self):
        return {left: right for left, right in self.forward.items() if left != right}


def labels(text):
    significant = (value for kind, value in tokens(text) if kind not in ('space', 'comment'))
    previous = []
    result = Counter()
    for value in significant:
        previous = (previous + [value])[-3:]
        if len(previous) == 3 and previous[1:] == [':', ';'] and LABEL.fullmatch(previous[0]):
            result[previous[0]] += 1
    require(all(count == 1 for count in result.values()), 'duplicate label declaration')
    return set(result)


def compare(left, right, fields, fixed, *, scoped=False):
    variables, jumps = Bijection(), Bijection()
    left_labels, right_labels = (labels(left), labels(right)) if scoped else (set(), set())
    for pair in zip_longest(tokens(left), tokens(right)):
        a, b = pair
        require(a is not None and b is not None and a[0] == b[0], 'lexical token kind/count differs')
        kind, x = a; y = b[1]
        if kind == 'id' and FIELD.fullmatch(x) and FIELD.fullmatch(y):
            fields.bind(x, y)
        elif kind == 'comment' and (ma := COMMENT.fullmatch(x)) and (mb := COMMENT.fullmatch(y)):
            require(x.startswith('/*') == y.startswith('/*'), 'generated comment category differs')
            fields.bind('z0zE' + (ma[1] or ma[2]), 'z0zE' + (mb[1] or mb[2]))
        elif scoped and kind == 'id' and (ma := LOCAL.fullmatch(x)) and (mb := LOCAL.fullmatch(y)):
            require(ma[1] == mb[1], 'generated variable family differs')
            require(x not in fixed and y not in fixed or x == y, 'renaming an externally visible generated name')
            variables.bind(x, y)
        elif scoped and kind == 'id' and (ma := LABEL.fullmatch(x)) and (mb := LABEL.fullmatch(y)):
            require(ma[1] == mb[1] and x in left_labels and y in right_labels, 'label not locally declared or family differs')
            jumps.bind(x, y)
        else:
            require(x == y, 'unaccounted token difference: ' + repr(x[:100]) + ' -> ' + repr(y[:100]))
    if scoped:
        require(set(jumps.forward) == left_labels and set(jumps.backward) == right_labels, 'label coverage incomplete')
    return {'variables': variables.changed(), 'labels': jumps.changed(),
            'variable_names_checked': len(variables.forward), 'label_names_checked': len(jumps.forward)}


def fields_in(header):
    found = list(DECL.finditer(header))
    require(found and len({m[3] for m in found}) == len(found), 'missing or duplicate generated field declarations')
    require(all(m[3] == 'z0zE' + m[1] for m in found), 'field comment/name mismatch')
    return {m[3]: m[2] for m in found}


def analyze(old_cpp, new_cpp, old_header, new_header):
    a, b = regions(old_cpp), regions(new_cpp)
    require([name for name, _, _ in a] == [name for name, _, _ in b], 'method set/order differs')
    old_fields, new_fields = fields_in(old_header), fields_in(new_header)
    gaps_a, gaps_b, cursor_a, cursor_b = [], [], 0, 0
    for (_, start_a, end_a), (_, start_b, end_b) in zip(a, b):
        gaps_a.append(old_cpp[cursor_a:start_a]); gaps_b.append(new_cpp[cursor_b:start_b])
        cursor_a, cursor_b = end_a, end_b
    gaps_a.append(old_cpp[cursor_a:]); gaps_b.append(new_cpp[cursor_b:])
    # A synthetic name declared or mentioned outside a method is conservatively
    # fixed inside methods too. This is not a full C++ declaration/name resolver.
    fixed = {value for text in [old_header, new_header, *gaps_a, *gaps_b]
             for kind, value in tokens(text) if kind == 'id' and LOCAL.fullmatch(value)}
    fields = Bijection(); methods = {}
    for (name, sa, ea), (_, sb, eb) in zip(a, b):
        methods[name] = compare(old_cpp[sa:ea], new_cpp[sb:eb], fields, fixed, scoped=True)
    for left, right in zip(gaps_a, gaps_b):
        compare(left, right, fields, fixed)
    require(set(fields.forward) == set(old_fields) and set(fields.backward) == set(new_fields),
            'C++ does not cover exactly all header generated fields')
    require(all(old_fields[x] == new_fields[y] for x, y in fields.forward.items()), 'corresponding field types differ')
    before = dict(fields.forward)
    compare(old_header, new_header, fields, fixed)
    require(fields.forward == before, 'header introduced a new correspondence')
    return {'method_count': len(methods), 'field_count': len(old_fields),
            'changed_field_count': len(fields.changed()), 'fixed_external_generated_names': sorted(fixed),
            'header_order_types_initializers_preserved': True, 'gaps_checked': len(gaps_a),
            'methods': methods, 'fields': fields.forward,
            'corresponding_field_types': {x: old_fields[x] for x in fields.forward}}


def run(out):
    report = {'status': 'running', 'started_at': evidence.chain.now(), 'policy_changed': False,
              'generated_sources_edited': False, 'tool_adopted': False, 'kernel_executed': False,
              'cpp_compiled': False, 'runtime_executed': False, 'semantic_equivalence_proved': False,
              'cpp_ast_or_macro_binding_proved': False, 'clean_room_claimed': False, 'release_claimed': False}
    try:
        source_report = evidence.pinned(evidence.SAIL / 'report.json', evidence.SAIL_SHA)
        require(source_report['status'] == 'failed' and source_report['error'] == 'raw candidate model differs', 'original disposition changed')
        base = ROOT / 'artifacts/boundary-check/sail-model-identity-v1weq3h5/baseline-build'
        candidate = evidence.SAIL / 'candidate-build'
        paths = {Path(__file__), evidence.SAIL / 'report.json', evidence.gate.POLICY, evidence.public_gate.POLICY,
                 evidence.lower.raw.POLICY, evidence.lower.fields.POLICY}
        files = []
        for name in ('sail_riscv_model.cpp', 'sail_riscv_model.h'):
            pair = []
            for directory, side in ((base, 'baseline'), (candidate, 'candidate')):
                path = directory / name
                require(sha(path) == source_report[side + '_outputs']['cpp'][name], 'original model hash drift')
                paths.add(path); pair.append(path.read_bytes().decode())
            files.extend(pair)
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}
        result = analyze(*files)
        evidence.gate.write_json(out / 'correspondence.json', result)
        report['correspondence_sha256'] = sha(out / 'correspondence.json')
        report['summary'] = {key: value for key, value in result.items() if key not in ('methods', 'fields', 'corresponding_field_types')}
        report['summary'].update(changed_variable_names=sum(len(row['variables']) for row in result['methods'].values()),
                                 changed_label_names=sum(len(row['labels']) for row in result['methods'].values()))
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift during audit')
        report['status'] = 'scoped_token_correspondence_checked_semantics_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = evidence.chain.now()
    evidence.gate.write_json(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='sail-cpp-correspondence-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
