"""Rebuild October 2026 figures in a temporary original-layout workspace.

Copyright 2026 Zhixuan Ma and Zhengwei Shen.
SPDX-License-Identifier: Apache-2.0
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path,help='New, non-existing output directory')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    out=args.output.resolve()
    if out.exists():raise SystemExit('Refusing to overwrite an existing output directory')
    expected={
        'experiment49_candidate_endpoint_robustness_results.zip':'f57f6938c5de6d32339f2ca9e8cb2789ceed1dd2263feb7155ee76b35caefdc2',
        'experiment50_independent_reexecution_fix1_results.zip':'111e3e2e9b0686dc18240120ee065953a3d28cf09f3dd39ac3515c5542a8f78f',
        'experiment52_continuation_probe_fix4_results.zip':'316fae4c4de34c249edbc06b7c25222e829154abb8c87ee7ad14215d8803ee73'}
    for name,h in expected.items():
        if sha(args.artifacts/name)!=h:raise SystemExit('Input hash mismatch: '+name)
    with tempfile.TemporaryDirectory(prefix='endpoint-figures-') as tmp:
        project=Path(tmp);base=project/'manuscript_polished_20261005'
        figs=base/'figures';figs.mkdir(parents=True)
        (base/'latex').mkdir();(base/'supplement').mkdir()
        for name in ['make_figures.py','reference_style.py','make_supplement_figure.py']:
            shutil.copy2(root/'figures_20261008'/name,figs/name)
        for name in expected:shutil.copy2(args.artifacts/name,project/name)
        correction=project/'publication_release/release_v1.22.2/github/paper_v1.21/analysis'
        correction.mkdir(parents=True)
        for name in ['exp64_corrected_rows.jsonl','exp64_correction.json']:
            shutil.copy2(root/'paper_v1.21/analysis'/name,correction/name)
        for script in ['make_figures.py','make_supplement_figure.py']:
            subprocess.run([sys.executable,str(figs/script)],check=True)
        checks={name:sha(figs/name)==sha(root/'figures_20261008'/name)
                for name in ['figure_source_data.json','external_source.csv']}
        if not all(checks.values()):raise SystemExit('Rebuilt numerical figure inputs differ: '+str(checks))
        out.mkdir(parents=True)
        for folder in [figs,base/'latex',base/'supplement']:
            for p in folder.iterdir():
                if p.is_file() and p.suffix in {'.pdf','.svg','.png','.eps','.tiff','.csv','.json'}:shutil.copy2(p,out/p.name)
        receipt={'passed':True,'checks':checks,'new_lean_executions':0,'input_sha256':expected,
                 'scope':'Numerical figure inputs match; binary graphics may differ with fonts, library versions and PDF timestamps.'}
        (out/'figure_reproduction_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
