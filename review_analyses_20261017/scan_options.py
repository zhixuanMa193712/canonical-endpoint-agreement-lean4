#!/usr/bin/env python3
"""Options in scope at each root (static scan of the SHA-verified source files; no Lean).

For every case-series and strict-frame root, find `set_option` commands that apply to the
root's declaration: file- or section-level commands before the declaration (honoring
`section`/`namespace` ... `end` scoping) and `set_option ... in` prefixes of the declaration.
Options set inside the proof are ignored.  The heartbeat-failure roots are identified from
the archived diagnostics (case series: candidate error text; strict frame: theorem ids
passed in HB_STRICT, read from the Exp64 content store).

Usage: python scan_options.py <work dir with data/, src/ and root_positions.json>
"""
import collections
import json
import re
import sys
from pathlib import Path

W = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
HB_STRICT = {  # theorem ids whose candidates hit the 200,000-heartbeat limit (Exp64 diagnostics)
    '339e08c2d35c9a255bbb93396c81f8900304cd0307bed28fda55787980767fe7',
    '5b19f7e3fed10f66213d321c79c22a5fce313a8a5e04e121395e4e76c58d0bb0',
    'aedae86b3611470b2fcf3da9e5fda3dab1dd282242a867c6bd6ee853562f9673',
    '7c2a7d38baa84ac4da292c99a427290a93cff66b9a65cab799afedcb166cb016',
    '43fe5ba2f8ac551265d39dbaf433a87a9cf367c450db7fcd5b67ffd432a27454',
    '66e3f821656808fd4b7b41fe5a1116b80cd4e94b9cf6281042d0e6a321ea2b00',
}
DECL = re.compile(rb'^[ \t]*(?:@\[[^\n]*?\][ \t]*\n?[ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial|scoped|local)[ \t]+)*(theorem|lemma|def|instance|example|abbrev|opaque)\b', re.M)
SETOPT = re.compile(rb'^[ \t]*set_option[ \t]+([\w.]+)[ \t]+(\S+)([ \t]+in\b)?', re.M)
SCOPE = re.compile(rb'^[ \t]*(section|namespace|end|noncomputable section)\b[^\n]*', re.M)


def strip_comments(b):
    b = re.sub(rb'/-.*?-/', lambda m: b' ' * len(m.group(0)), b, flags=re.S)
    return re.sub(rb'--[^\n]*', lambda m: b' ' * len(m.group(0)), b)


def options_for(b, pos):
    b = strip_comments(b)
    decls = [m for m in DECL.finditer(b) if m.start() <= pos]
    if not decls:
        return {}
    ds = decls[-1].start()
    # scoped commands before the declaration
    events = sorted([(m.start(), 'opt', m) for m in SETOPT.finditer(b, 0, ds)] +
                    [(m.start(), 'scope', m) for m in SCOPE.finditer(b, 0, ds)], key=lambda x: x[0])
    stack = [{}]
    prefix = {}
    for start, kind, m in events:
        if kind == 'scope':
            word = m.group(1)
            if word in (b'section', b'namespace', b'noncomputable section'):
                stack.append(dict(stack[-1]))
            elif word == b'end' and len(stack) > 1:
                stack.pop()
            prefix = {}
        else:
            name, val, is_in = m.group(1).decode(), m.group(2).decode(), m.group(3)
            if is_in:
                # an `in` prefix applies to the next command; keep it only if nothing but
                # further prefixes, attributes, or doc comments lie between it and the declaration
                between = b[m.end():ds]
                if not re.sub(rb'set_option[^\n]*\bin\b|@\[[^\]]*\]|\s', b'', between):
                    prefix[name] = val
            else:
                stack[-1][name] = val
                prefix = {}
    out = dict(stack[-1])
    out.update(prefix)
    return out


def raised(opts):
    v = opts.get('maxHeartbeats')
    if v is None:
        return False
    try:
        n = int(v)
    except ValueError:
        return True
    return n == 0 or n > 200000


def main():
    res = {}
    for fname, study in (('case_series_rows.jsonl', 'case_series'), ('strict_rows.jsonl', 'strict')):
        rows = [json.loads(l) for l in open(W / 'data' / fname)]
        cnt = collections.Counter()
        names = collections.Counter()
        hb_roots = []
        for r in rows:
            p = W / 'src' / r['slug'].replace('/', '__') / r['file_path']
            opts = options_for(p.read_bytes(), r['target_pos'])
            cnt['roots'] += 1
            cnt['any_option'] += bool(opts)
            cnt['raised_heartbeats'] += raised(opts)
            for k in opts:
                names[k] += 1
            if study == 'case_series':
                hb = any('heartbeat' in (c.get('error') or '') for c in r['candidates'])
            else:
                hb = r['theorem_id'] in HB_STRICT
            if hb:
                hb_roots.append({'slug': r['slug'], 'full_name': r['full_name'], 'options': opts,
                                 'raised_heartbeats': raised(opts)})
        res[study] = {'counts': dict(cnt), 'option_names': names.most_common(), 'heartbeat_failure_roots': hb_roots}
    json.dump(res, open(W / 'options_in_scope.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
