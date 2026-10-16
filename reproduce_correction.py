"""Run unchanged final correction in a temporary workspace, without Lean."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from importlib import metadata

def same_except_numpy_version(a,b):
    """True when two JSON objects differ at most in their top-level numpy_version field."""
    if a.suffix!='.json': return False
    x=json.loads(a.read_text());y=json.loads(b.read_text())
    if not isinstance(x,dict) or not isinstance(y,dict): return False
    x.pop('numpy_version',None);y.pop('numpy_version',None)
    return x==y

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,default=Path('reproduction_receipt.json'))
    args=parser.parse_args();root=Path(__file__).resolve().parent
    expected={
      'experiment51_external_repository_replication_fix3_results.zip':'f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b',
      'experiment64_strict_v427_external_replication_results.zip':'2aaebc31501b5946a6dcfb7a279d2dda0cdd4cf20160f7e49ec63674e5411130',
      'experiment62_multistep_solvable_search_fix1_results.zip':'b2960650f01811d333f0ed4beea422c00d9149eb1f5eac7c55f1333a75230f57'}
    for n,h in expected.items():
        if hashlib.sha256((args.artifacts/n).read_bytes()).hexdigest()!=h: raise SystemExit('Input hash mismatch: '+n)
    with tempfile.TemporaryDirectory(prefix='endpoint-reproduce-') as temp:
        work=Path(temp);(work/'paper_v1.21').mkdir()
        for n in expected: shutil.copy2(args.artifacts/n,work/n)
        shutil.copy2(root/'paper_v1.21/reanalyze_heads.py',work/'paper_v1.21/reanalyze_heads.py')
        shutil.copytree(root/'experiment51_external_repository_replication',work/'experiment51_external_repository_replication')
        result=subprocess.run([sys.executable,str(work/'paper_v1.21/reanalyze_heads.py')],capture_output=True,text=True)
        if result.returncode: raise SystemExit(result.stderr)
        checks={};byte_identical={}
        for n in ['exp51_correction.json','exp64_correction.json','exp51_corrected_rows.jsonl','exp64_corrected_rows.jsonl','multistep_file_cluster.json']:
            a=work/'paper_v1.21/analysis'/n;b=root/'paper_v1.21/analysis'/n
            byte_identical[n]=a.read_bytes()==b.read_bytes()
            checks[n]=byte_identical[n] or same_except_numpy_version(a,b)
        try: numpy_version=metadata.version('numpy')
        except metadata.PackageNotFoundError: numpy_version=None
        receipt=dict(checks=checks,byte_identical=byte_identical,passed=all(checks.values()),numpy_version=numpy_version,
                     comparison='byte-identical, or identical except the recorded numpy_version field',
                     new_lean_executions=0,input_sha256=expected,scope='post-outcome correction and cluster sensitivity, not every historical audit')
        args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
        if not receipt['passed']: raise SystemExit('Reconstruction differs; check NumPy version before publishing')

if __name__=='__main__': main()
