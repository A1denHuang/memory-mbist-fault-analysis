"""Infer coupling from measured responses, never from injection configuration."""
import csv
from pathlib import Path
from analyze import classify, read_fails


def coupling_from_reads(path, seed, victim):
    with Path(path).open(newline='',encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    required={'seed','victim','aggressor','initial','background','phase','actual'}
    if not rows or set(rows[0])!=required:raise ValueError('Invalid probe columns')
    trials={}
    for row in rows:
        s,v,a,i,b,x=(int(row[k]) for k in ('seed','victim','aggressor','initial','background','actual'))
        phase=row['phase']
        if s!=seed or v!=victim or not 0<=a<256 or a==v:raise ValueError('Probe identity/address mismatch')
        if i not in (0,1) or b not in (0,1) or x not in (0,1) or phase not in ('settle','toggle','rewrite'):
            raise ValueError('Invalid probe observation')
        key=(i,b,phase)
        group=trials.setdefault(a,{})
        if key in group:raise ValueError('Duplicate probe observation')
        group[key]=x
    keys={(i,b,p) for i in (0,1) for b in (0,1) for p in ('settle','toggle','rewrite')}
    if set(trials)!=set(range(256))-{victim} or any(set(g)!=keys for g in trials.values()):
        raise ValueError('Probe must cover all other addresses, backgrounds and directions')
    hits=[]
    for address,g in trials.items():
        if all(g[i,b,'settle']==b and g[i,b,'toggle']==1-b and g[i,b,'rewrite']==b
               for i in (0,1) for b in (0,1)):
            hits.append(dict(prediction='CFIN',aggressor=address))
        for trigger in (0,1):
            for value in (0,1):
                if all(g[i,b,'settle']==b and g[i,b,'rewrite']==b and
                       g[i,b,'toggle']==(value if 1-i==trigger else b)
                       for i in (0,1) for b in (0,1)):
                    hits.append(dict(prediction='CFID',aggressor=address,trigger=trigger,value=value))
                def state_response(i,b,phase):
                    settled=value if i==trigger else b
                    if phase=='settle':return settled
                    if phase=='toggle':return value if 1-i==trigger else settled
                    return value if 1-i==trigger else b
                if all(g[i,b,p]==state_response(i,b,p) for i,b,p in keys):
                    hits.append(dict(prediction='CFST',aggressor=address,trigger=trigger,value=value))
    # Ambiguous/composite responses do not force a unique diagnosis.
    return hits[0] if len(hits)==1 else None


def predict(seed, fail_csv, probe_csv=None):
    frame=read_fails(fail_csv)
    baseline=classify(frame)
    result=dict(seed=seed,baseline=baseline['prediction'],prediction=baseline['prediction'],
                method='March-C-only',reason=baseline['reason'])
    if probe_csv is not None:
        if frame.addr.nunique()!=1:raise ValueError('Probe requires exactly one observed failing address')
        hit=coupling_from_reads(probe_csv,seed,int(frame.addr.iloc[0]))
        result['method']='March-C-plus-toggle-rewrite'
        if hit:
            result.update(hit)
            result['reason']='Unique causal response across both backgrounds and both aggressor transitions.'
        else:result['reason']='No unique coupling response; keep the March-only choice.'
    return result
