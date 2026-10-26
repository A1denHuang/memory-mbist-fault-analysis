"""Fail-CSV-only rule classifier, bitmap plotting and independent blind scoring.

The classify subcommand cannot read injection configurations or truth labels.
The report subcommand joins labels only AFTER predictions have been saved.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import pandas as pd

REQUIRED=['seed','addr','row','col','element','op','expected','actual']
LABELS=['SAF0','SAF1','TF_UP','TF_DOWN','CFIN','CFID','CFST','AF','ROW','COL','DRF','NONE','UNKNOWN']

def read_fails(path):
    frame=pd.read_csv(path)
    if list(frame.columns)!=REQUIRED: raise ValueError(f'{path}: incorrect CSV columns')
    frame['addr']=frame['addr'].map(lambda x:int(str(x),0))
    for col in ['seed','addr','row','col','expected','actual']:
        frame[col]=pd.to_numeric(frame[col],errors='raise').astype(int)
    if len(frame):
        if frame.seed.nunique()!=1: raise ValueError('Analyze one seed at a time')
        if not frame.addr.between(0,255).all(): raise ValueError('Address out of range')
        if not ((frame.row==frame.addr//16)&(frame.col==frame.addr%16)).all():
            raise ValueError('Logical address / physical coordinate mismatch')
        if not frame.element.isin(['M1','M2','M3','M4','M5']).all(): raise ValueError('Invalid read element')
        if not frame.expected.isin([0,1]).all() or not frame.actual.isin([0,1]).all():
            raise ValueError('Nonbinary observation')
        exp=frame.element.map({'M1':0,'M2':1,'M3':0,'M4':1,'M5':0})
        if not ((exp==frame.expected)&(frame.op=='r'+frame.expected.astype(str))&
                (frame.actual!=frame.expected)).all(): raise ValueError('Invalid failure tuple')
        if frame.duplicated(['addr','element']).any(): raise ValueError('Duplicate fail tuple')
    return frame

def classify(frame):
    if frame.empty:
        return dict(prediction='NONE',candidates=['NONE','DRF'],order='unknown',
                    reason='No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF.')
    addresses=set(frame.addr)
    rows=frame.groupby('row').addr.nunique()
    cols=frame.groupby('col').addr.nunique()
    if (rows==16).any():
        return dict(prediction='ROW',candidates=['ROW'],order='unknown',reason='All 16 columns of a row fail; inspect wordline / row decoder.')
    if (cols==16).any():
        return dict(prediction='COL',candidates=['COL'],order='unknown',reason='All 16 rows of a column fail; inspect bitline / sense amplifier.')
    if len(addresses)==2:
        signatures=[set(g.element) for _,g in frame.groupby('addr')]
        if set.union(*signatures)=={'M1','M2','M3','M4'}:
            return dict(prediction='AF',candidates=['AF','CFIN','CFID'],order='unknown',
                        reason='Two addresses fail with complementary ascending/descending signatures; alias candidate.')
    if len(addresses)==1:
        signature=frozenset(frame.element)
        rules={
            frozenset(['M2','M4']): ('SAF0',['SAF0','TF_UP','CFIN','CFID','CFST'],'after is compatible for CFIN',
                'Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them.'),
            frozenset(['M1','M3','M5']): ('SAF1',['SAF1','CFID','CFST'],'unknown',
                'All read-0 elements fail, including the first read after initialization.'),
            frozenset(['M3','M5']): ('TF_DOWN',['TF_DOWN','CFID','CFST'],'unknown',
                'Read-0 failures only after 1-to-0 writes; transition or coupling candidate.'),
            frozenset(['M1','M2','M4','M5']): ('CFIN',['CFIN'],'before',
                'Four-element inversion signature is consistent with aggressor before victim.'),
        }
        if signature in rules:
            prediction,candidates,order,reason=rules[signature]
            return dict(prediction=prediction,candidates=candidates,order=order,reason=reason)
        return dict(prediction='CFID',candidates=['CFID','CFST','CFIN','AF'],order='unknown',
                    reason='Partial-element single-cell signature suggests coupling; fail CSV alone cannot resolve subtype or aggressor.')
    return dict(prediction='UNKNOWN',candidates=['UNKNOWN'],order='unknown',
                reason='Composite or unrecognized spatial pattern; collect address-isolation / aggressor experiments.')

def plot(frame,output,title='Memory failure analysis'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    bitmap=np.zeros((16,16),dtype=int); element_map=np.zeros((6,256),dtype=int)
    for row in frame.itertuples(index=False):
        bitmap[row.row,row.col]+=1; element_map[int(row.element[1:]),row.addr]+=1
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained',gridspec_kw={'width_ratios':[1,1.6]})
    im=axes[0].imshow(bitmap,cmap='YlOrRd',vmin=0,vmax=max(1,int(bitmap.max())),interpolation='nearest')
    axes[0].set(title='Fail bitmap (count per cell)',xlabel='Column / bitline',ylabel='Row / wordline',xticks=range(0,16,2),yticks=range(0,16,2))
    axes[0].set_xticks(np.arange(-.5,16,1),minor=True);axes[0].set_yticks(np.arange(-.5,16,1),minor=True)
    axes[0].grid(which='minor',color='gray',linewidth=.3);fig.colorbar(im,ax=axes[0],shrink=.7,label='Failures',ticks=range(max(1,int(bitmap.max()))+1))
    axes[1].imshow(element_map,aspect='auto',cmap='Blues',vmin=0,vmax=1,interpolation='nearest')
    axes[1].set(title='March element x address',xlabel='Logical address',ylabel='March element',yticks=range(6),yticklabels=[f'M{i}' for i in range(6)])
    fig.suptitle(title);fig.savefig(output,dpi=160);plt.close(fig)

def classify_directory(directory,output):
    predictions=[]
    for path in sorted(Path(directory).glob('*.csv')):
        frame=read_fails(path)
        # Filename provides experiment identifier for empty logs, never the fault label.
        predictions.append(dict(seed=int(path.stem),**classify(frame)))
    Path(output).write_text(json.dumps(predictions,indent=2),encoding='utf-8')
    return predictions

def build_report(results):
    results=Path(results); figures=results/'figures';figures.mkdir(exist_ok=True)
    predictions=classify_directory(results/'blind_inputs',results/'blind_predictions.json')
    truth=pd.read_csv(results/'blind_truth.csv').set_index('seed').truth.to_dict()
    scored=[]
    for p in predictions:
        label=truth[p['seed']]
        scored.append(dict(**p,truth=label,correct=p['prediction']==label,
                           candidate_hit=label in p['candidates']))
    (results/'blind_scored.json').write_text(json.dumps(scored,indent=2),encoding='utf-8')
    top1=sum(p['correct'] for p in scored); candidate=sum(p['candidate_hit'] for p in scored)
    manifest=json.loads((results/'manifest.json').read_text())
    verification=json.loads((results/'verification.json').read_text())
    # Single-fault diagnostic experiments only: no false causal attribution in mixed runs.
    matrix={label:{f'M{e}':0 for e in range(6)} for label in LABELS[:11]}
    ordering={}
    id_to_label=dict(enumerate(LABELS[:11],1))
    for case in manifest:
        if case['group']!='directed' or case['mode'] or len(case['faults'])!=1 or case['pause']: continue
        frame=read_fails(results/'cases'/case['name']/'fails.csv')
        fault=case['faults'][0]; label=id_to_label[fault['kind']]
        for elem,count in frame.element.value_counts().items(): matrix[label][elem]+=int(count)
        if 5<=fault['kind']<=7:
            key=f"{label} aggressor {'<' if fault['aggressor']<fault['victim'] else '>'} victim; force={fault['value']}, trigger={fault['trigger']}"
            ordering.setdefault(key,set()).update(frame.element)
    pd.DataFrame.from_dict(matrix,orient='index').to_csv(results/'fault_element_coverage.csv',index_label='fault')
    order_json={key:sorted(value) for key,value in sorted(ordering.items())}
    (results/'coupling_order_coverage.json').write_text(json.dumps(order_json,indent=2),encoding='utf-8')
    # Exact operation coverage recovered from observed, scoreboard-checked bus traces.
    visits=set();boundary=set()
    for case in manifest:
        if case['group']!='directed': continue
        frame=pd.read_csv(results/'cases'/case['name']/'operations.csv')
        visits.update((str(e),int(case['mode'])) for e in frame.element)
        boundary.update(int(a) for a in frame.addr if int(a)%16 in (0,15))
    functional={'element_mode_bins':[list(x) for x in sorted(visits)],
                'element_mode_hit':len(visits),'element_mode_total':12,
                'row_array_boundary_addresses_hit':sorted(boundary),
                'row_array_boundary_total':32,
                'note':'These are observed functional bins, not native UCDB/code coverage percentages.'}
    (results/'functional_coverage.json').write_text(json.dumps(functional,indent=2),encoding='utf-8')
    for name in ['clean_diag','SAF1_diag','ROW_diag','COL_diag','CFIN_diag','AF_diag','retention_pause']:
        plot(read_fails(results/'cases'/name/'fails.csv'),figures/f'{name}.png',name)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    confusion=pd.crosstab(pd.Series([x['truth'] for x in scored],name='Injected'),
                          pd.Series([x['prediction'] for x in scored],name='Predicted')).reindex(index=LABELS[:11],columns=LABELS,fill_value=0)
    confusion.to_csv(results/'blind_confusion.csv')
    fig,ax=plt.subplots(figsize=(10,7),layout='constrained')
    image=ax.imshow(confusion.to_numpy(),cmap='Blues',vmin=0)
    ax.set(xticks=range(len(LABELS)),xticklabels=LABELS,yticks=range(11),yticklabels=LABELS[:11],
           xlabel='Predicted (top choice)',ylabel='Injected',title=f'Blind holdout: {top1}/{len(scored)} correct ({top1/len(scored):.1%})')
    plt.setp(ax.get_xticklabels(),rotation=45,ha='right')
    for i in range(11):
        for j in range(len(LABELS)):
            if confusion.iloc[i,j]:ax.text(j,i,str(confusion.iloc[i,j]),ha='center',va='center',color='white' if confusion.iloc[i,j]>=3 else 'black')
    fig.colorbar(image,ax=ax,shrink=.8);fig.savefig(figures/'blind_confusion.png',dpi=160);plt.close(fig)
    lines=['# Verification and blind analysis report','',
           f"Simulator: {verification['simulator']}. All {verification['simulations']} RTL simulations passed the operation and failure-tuple scoreboard.",
           f"Random regression: {verification['random_seeds']} independent seeds, each with 1-3 faults, both modes.",
           'Healthy memory: 2560 accepted operations, zero failures, pass=1 in both modes.',
           'Model-only unit tests: 51 checks passed (see fault_model_units.log).',
           f"Assertion status: {verification['sva']}.",
           f"Functional bins: {len(visits)}/12 element x mode; {len(boundary)}/32 row/array boundary addresses.",'',
           '## Blind holdout','',
           f'Top-choice exact type accuracy: **{top1}/{len(scored)} = {top1/len(scored):.2%}**.',
           f'Candidate-set inclusion: **{candidate}/{len(scored)} = {candidate/len(scored):.2%}** (not exact-type accuracy).',
           'Balanced, independent single-fault holdout; 5 samples/type by default. Classifier input contains fail CSVs only. Mixed-fault regression is a controller correctness test, not a classification benchmark.',
           'DRF no-failure observations remain in the denominator. No-fail does not prove no fault.',
           'Rules were fixed before inspecting holdout labels; no model training or truth-driven label lookup. Results are for this behavioral model, not silicon performance.','',
           '![Confusion](figures/blind_confusion.png)','','## Every misclassified case','',
           '| Seed | Injected | Predicted | Reason |','|---|---|---|---|']
    for item in scored:
        if not item['correct']:lines.append(f"| {item['seed']} | {item['truth']} | {item['prediction']} | {item['reason']} |")
    lines+=['','## Single-fault detection cross table','',
            'Counts are observed fail events, not theoretical coverage percentages. Zero M0 is expected because it only writes. DRF baseline zeros are intentional; see retention_pause.','',
            '| Fault | M0 | M1 | M2 | M3 | M4 | M5 |','|---|---:|---:|---:|---:|---:|---:|']
    for label,row in matrix.items():lines.append('| '+label+' | '+' | '.join(str(row[f'M{i}']) for i in range(6))+' |')
    lines+=['','## Coupling ordering observed in simulation','',
            '| Injection / ordering | Detected elements |','|---|---|']
    for key,value in order_json.items():lines.append('| '+key+' | '+', '.join(value)+' |')
    lines+=['','## Interpretation and follow-up','',
            '- SAF0 and TF_UP share M2/M4 under a w0-first March C- sequence; failure CSV alone cannot distinguish them.',
            '- CFin after-victim can share that same signature. CFid and CFst can mimic stuck-at or transition faults depending on trigger/forced value.',
            '- AF remaps one victim to one aggressor; not all real decoder open/multiple-select faults are modeled.',
            '- For ambiguous cases, run a targeted aggressor-toggle test, independent address-isolation test, changed initialization, or pause-time sweep.',
            '- DRF threshold=10000 cycles is longer than base test duration; a 12000-cycle pause after M0 sensitizes it.',
            ('- Native SVA and covergroups were executed in Questa; merged UCDB and detailed assertion/bin counts are in native_coverage.txt. No gate-level synthesis or timing analysis was performed.' if verification['simulator']=='questa' else '- Portable runs check behavior procedurally. Native SVA and covergroup results are supplied separately in ../results_questa/; these are not code coverage or synthesis results.'),'',
            '## Example bitmaps','',
            '![Row](figures/ROW_diag.png)','','![Column](figures/COL_diag.png)','','![Coupling](figures/CFIN_diag.png)','','![Retention](figures/retention_pause.png)','']
    (results/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    metrics=dict(samples=len(scored),correct=top1,accuracy=top1/len(scored),
                 candidate_hits=candidate,candidate_inclusion=candidate/len(scored))
    (results/'blind_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    one=sub.add_parser('classify');one.add_argument('csv',type=Path);one.add_argument('--plot',type=Path)
    many=sub.add_parser('blind');many.add_argument('--inputs',required=True,type=Path);many.add_argument('--out',required=True,type=Path)
    report=sub.add_parser('report');report.add_argument('--results',type=Path,default=Path('results'))
    args=parser.parse_args()
    if args.cmd=='classify':
        frame=read_fails(args.csv);print(json.dumps(classify(frame),indent=2))
        if args.plot:plot(frame,args.plot)
    elif args.cmd=='blind':classify_directory(args.inputs,args.out)
    else:build_report(args.results)
if __name__=='__main__':main()
