"""One offline readiness run: frozen journeys, full named suite and saved-data checks.

The suite list is frozen in the repository. No model or external-data requests
are intentionally made. Each subprocess has a timeout; failures remain in logs.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
from time import perf_counter

from .validate_journeys import evaluate,save_report

ROOT=Path(__file__).resolve().parent.parent


def run(output):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new output directory; previous evidence is preserved')
    output.mkdir(parents=True)
    suite=json.loads((ROOT/'fixtures/evaluation/readiness-suite.json').read_text())['modules']
    if not suite or any(not re.fullmatch(r'check_[a-z0-9_]+',module) for module in suite):
        raise ValueError('Invalid frozen regression-suite names')
    commands=[('regression',[sys.executable,'-B','-m','unittest',*suite,'-v']),
              ('traffic',[sys.executable,'-B','scripts/verify_traffic.py']),
              ('coverage',[sys.executable,'-B','scripts/verify_route_coverage.py']),
              ('bus-collection',[sys.executable,'-B','scripts/verify_bus_collection.py'])]
    checks=[]
    for name,command in commands:
        print('Checking '+name+'…',flush=True);started=perf_counter()
        with (output/(name+'.log')).open('w',encoding='utf-8') as log:
            try:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=420 if name=='regression' else 120)
                status='passed' if result.returncode==0 else 'failed';code=result.returncode
            except subprocess.TimeoutExpired:
                status='timed_out';code=None;log.write('\nReadiness runner stopped this command at its timeout.\n')
        checks.append({'name':name,'status':status,'exit_code':code,'seconds':round(perf_counter()-started,3),'command':command})
        print(name+': '+status,flush=True)
    print('Checking frozen journeys…',flush=True)
    journeys=evaluate(ROOT/'fixtures/evaluation/municipal-journeys.json')
    save_report(journeys,output/'journeys')
    checks.append({'name':'journeys','status':'passed' if journeys['summary']['passed']==journeys['summary']['total'] else 'failed','summary':journeys['summary']})
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'mode':'offline; no live-model experiment',
            'passed':all(check['status']=='passed' for check in checks),'checks':checks,
            'suite_sha256':hashlib.sha256((ROOT/'fixtures/evaluation/readiness-suite.json').read_bytes()).hexdigest(),
            'case_sha256':journeys['cases_sha256'],
            'source_sha256':journeys['source_sha256'],
            'pending_human_evidence':['Independent usability observation','Teammate unpublished experiment files/logs','Professor guidance on meeting reports'],
            'interpretation':'Passing software checks does not verify real-world accessibility, user benefit, every physical address entrance, or the pending human evidence.'}
    (output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'checks':checks},ensure_ascii=False),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.output)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
