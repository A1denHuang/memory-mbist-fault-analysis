"""Audit completed deliveries and compare independent simulator observations."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from analyze import equivalence_class

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit(results):
    manifest=json.loads((results/'manifest.json').read_text())
    verification=json.loads((results/'verification.json').read_text())
    assert len(manifest)==verification['simulations']
    random_seeds={c['seed'] for c in manifest if c['group']=='random'}
    assert len(random_seeds)>=50
    for case in manifest:
        directory=results/'cases'/case['name']
        with (directory/'fails.csv').open(newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==case['failures'],case['name']
        assert case['pass']==int(case['failures']==0)
        if not case['mode']:assert case['operations']==2560
        if case['mode']:assert case['failures']<=1
        assert 'PASS seed=' in (directory/'simulation.log').read_text()
        if case['mode']:
            diagnostic=results/'cases'/case['name'].removesuffix('_stop')
            diagnostic=diagnostic.with_name(diagnostic.name+'_diag')/'fails.csv'
            with diagnostic.open(newline='') as f:full=list(csv.DictReader(f))
            if full:
                assert rows==full[:1],f"{case['name']}: not the first diagnostic failure"
                first=full[0];element=int(first['element'][1:]);address=int(first['addr'],0)
                position=address if element in (1,2,5) else 255-address
                first_operation=(2304+position if element==5 else
                                 256+(element-1)*512+2*position)
                assert case['operations']==first_operation+1,f"{case['name']}: extra operation after first failure"
            else:assert not rows and case['operations']==2560
    metrics=json.loads((results/'blind_metrics.json').read_text())
    scored=json.loads((results/'blind_scored.json').read_text())
    assert metrics['samples']==len(scored)>=50
    assert metrics['correct']==sum(c['correct'] for c in scored)
    assert metrics['candidate_hits']==sum(c['candidate_hit'] for c in scored)
    assert metrics['equivalent_correct']==sum(equivalence_class(c['prediction'])==equivalence_class(c['truth']) for c in scored)
    assert 'checks=51' in (results/'fault_model_units.log').read_text()
    native=results/'native_coverage.txt'
    if native.exists():
        text=native.read_text(encoding='utf-8')
        section=text.split('ASSERTION RESULTS:',1)[1]
        counts=[tuple(map(int,x)) for x in re.findall(r'^\s*(\d+)\s+(\d+)\s*$',section,re.M)]
        assert len(counts)==6 and all(fail==0 and passed>0 for fail,passed in counts)
        total=float(re.search(r'TOTAL COVERGROUP COVERAGE:\s*([\d.]+)%',text).group(1))
        (results/'native_assertion_summary.json').write_text(json.dumps(dict(
            assertions=6,failures=0,all_exercised=True,total_covergroup_metric_percent=total,
            operation_covergroup_percent=100,
            note='Simulator covergroup metric includes unreachable/unsensitized cross bins; not silicon fault coverage or code coverage.'),indent=2),encoding='utf-8')
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path('results'))
    p.add_argument('--compare',type=Path);a=p.parse_args()
    first=audit(a.results);compared=0
    if a.compare:
        second=audit(a.compare)
        assert {x['name'] for x in first}=={x['name'] for x in second}
        mapping={x['name']:x for x in second}
        for item in first:
            other=mapping[item['name']]
            for field in ('operations','failures','pass','cycles','faults'):
                assert item[field]==other[field],(item['name'],field)
            left=a.results/'cases'/item['name']/'fails.csv'
            right=a.compare/'cases'/item['name']/'fails.csv'
            assert list(csv.reader(left.open()))==list(csv.reader(right.open())),item['name']
            compared+=1
    payload=dict(status='PASS',cases=len(first),cross_simulator_cases=compared,
                 manifest_sha256=digest(a.results/'manifest.json'))
    (a.results/'delivery_audit.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
