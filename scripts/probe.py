"""Collect follow-up bus observations and evaluate an observation-only classifier.

Hardware collection loads a hidden fault fixture. Prediction sees only failure
and probe CSVs. Scoring reads labels only after prediction JSON is saved.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
from analyze import equivalence_class, read_fails
from logs import public_log
from probe_classifier import predict
from run import ROOT, KINDS, command, compile_tb, random_fault


def probe_binary(build):
    return compile_tb(build,'tb_coupling_probe',[
        ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_coupling_probe.sv'])


def collect(inputs,configs,out):
    out.mkdir(parents=True,exist_ok=True)
    build=out/'build';build.mkdir(exist_ok=True)
    simulator=probe_binary(build)
    count=0
    for path in sorted(inputs.glob('*.csv')):
        frame=read_fails(path)
        if frame.addr.nunique()!=1:continue
        seed=int(path.stem);victim=int(frame.addr.iloc[0]);cfg=configs(seed)
        text=command(simulator+[f'+CFG={cfg.as_posix()}',f'+LOG={(out/(path.stem+".csv")).as_posix()}',
                     f'+SEED={seed}',f'+VICTIM={victim}'])
        if 'PASS coupling probe' not in text:raise RuntimeError(text)
        (out/(path.stem+'.log')).write_text(public_log(text,ROOT),encoding='utf-8')
        count+=1
    return count


def predictions(inputs,probes,out):
    values=[]
    for path in sorted(inputs.glob('*.csv')):
        auxiliary=probes/path.name
        values.append(predict(int(path.stem),path,auxiliary if auxiliary.exists() else None))
    out.write_text(json.dumps(values,indent=2),encoding='utf-8')
    return values


def score(saved_predictions,truth_csv,out,title):
    # This is the first point labels are read; prediction cannot access this map.
    values=json.loads(saved_predictions.read_text())
    with truth_csv.open(newline='',encoding='utf-8') as stream:
        truth={int(row['seed']):row['truth'] for row in csv.DictReader(stream)}
    if {v['seed'] for v in values}!=set(truth):raise ValueError('Prediction/label population mismatch')
    scored=[]
    for row in values:
        label=truth[row['seed']]
        scored.append(dict(**row,truth=label,correct=row['prediction']==label,
            equivalent_correct=equivalence_class(row['prediction'])==equivalence_class(label)))
    n=len(scored)
    def total(key,equivalent=False):
        return sum((equivalence_class(r[key])==equivalence_class(r['truth'])) if equivalent
                   else r[key]==r['truth'] for r in scored)
    metrics=dict(samples=n,baseline_correct=total('baseline'),baseline_accuracy=total('baseline')/n,
        baseline_equivalent_correct=total('baseline',True),baseline_equivalent_accuracy=total('baseline',True)/n,
        assisted_correct=total('prediction'),assisted_accuracy=total('prediction')/n,
        assisted_equivalent_correct=total('prediction',True),assisted_equivalent_accuracy=total('prediction',True)/n,
        equivalence_classes={'SAF0_OR_TF_UP':['SAF0','TF_UP']},
        probe_cases=sum(r['method']!='March-C-only' for r in scored),
        method_sha256=hashlib.sha256((ROOT/'scripts/probe_classifier.py').read_bytes()).hexdigest())
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    (out/'scored.json').write_text(json.dumps(scored,indent=2),encoding='utf-8')
    lines=[f'# {title}','',
        '| Method | Strict exact type | SAF0/TF_UP merged only |',
        '|---|---:|---:|',
        f"| March C- CSV | {metrics['baseline_correct']}/{n} ({metrics['baseline_accuracy']:.2%}) | {metrics['baseline_equivalent_correct']}/{n} ({metrics['baseline_equivalent_accuracy']:.2%}) |",
        f"| March C- + auxiliary reads | {metrics['assisted_correct']}/{n} ({metrics['assisted_accuracy']:.2%}) | {metrics['assisted_equivalent_correct']}/{n} ({metrics['assisted_equivalent_accuracy']:.2%}) |",'',
        'Only SAF0/TF_UP is merged. Coupling errors and no-failure DRF observations remain errors. Same samples and denominator for all four metrics.','',
        '## Per-type counts','',
        '| Truth | Samples | March-only correct | Assisted correct |','|---|---:|---:|---:|']
    for label in KINDS.values():
        subset=[r for r in scored if r['truth']==label]
        lines.append(f"| {label} | {len(subset)} | {sum(r['baseline']==label for r in subset)} | {sum(r['correct'] for r in subset)} |")
    lines+=['','## Remaining errors','',
        '| Seed | Truth | Prediction |','|---|---|---|']
    lines += [f"| {r['seed']} | {r['truth']} | {r['prediction']} |" for r in scored if not r['correct']]
    lines+=['','## Method and limits','',
        'The victim comes only from the failing address in the March CSV. All other 255 addresses are tried as aggressors. Four fresh trials per address cover both initial aggressor states and victim backgrounds. Settle, toggle, and victim-rewrite reads separate inversion, transition-triggered forcing, and state forcing.',
        'No injection type, aggressor or force value is supplied to prediction. Fixture configuration is used only by the SRAM simulator. Predictions are saved before scoring loads labels.',
        'Fresh array state between trials is simulator setup via initialize/load_config, not a hardware test primitive. Results apply to this single-fault behavioral model. A silicon implementation needs a justified reset/preconditioning procedure; no production test or independent validation of fault semantics is claimed.',
        '3060 additional reads and 4080 writes per probed cell (255 addresses x 4 trials); this is a diagnostic follow-up, not an improvement in March C- itself.','']
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(metrics,indent=2))


def benchmark(out,start,samples):
    if samples<55 or samples%11:raise ValueError('Use a balanced multiple of 11, at least 55 samples')
    out.mkdir(parents=True,exist_ok=True)
    inputs=out/'inputs';inputs.mkdir(exist_ok=True)
    fixtures=out/'fixtures';fixtures.mkdir(exist_ok=True)
    build=out/'build';build.mkdir(exist_ok=True)
    sim=compile_tb(build,'tb_mbist',[ROOT/'rtl/mbist_controller.sv',ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_mbist.sv'])
    truth=[]
    for index in range(samples):
        seed=start+index;kind=index%11+1;f=random_fault(random.Random(seed),kind)
        cfg=fixtures/f'{seed}.cfg'
        cfg.write_text('1\n'+f"{kind} {f['victim']} {f['aggressor']} {f['value']} {f['trigger']} {f['retention']}\n",encoding='ascii')
        text=command(sim+[f'+CFG={cfg.as_posix()}',f'+LOG={(inputs/(str(seed)+".csv")).as_posix()}',
            f'+SUMMARY={(fixtures/(str(seed)+".txt")).as_posix()}',f'+SEED={seed}', '+STOP=0'])
        if 'PASS seed=' not in text:raise RuntimeError(text)
        (fixtures/f'{seed}.log').write_text(public_log(text,ROOT),encoding='utf-8')
        truth.append(dict(seed=seed,truth=KINDS[kind]))
    with (out/'truth.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=['seed','truth']);writer.writeheader();writer.writerows(truth)
    probes=out/'probes'
    collect(inputs,lambda seed:fixtures/f'{seed}.cfg',probes)
    saved=out/'predictions.json';predictions(inputs,probes,saved)
    score(saved,out/'truth.csv',out,'Fresh-seed follow-up evaluation')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    review=sub.add_parser('review');review.add_argument('--results',type=Path,default=ROOT/'results')
    fresh=sub.add_parser('benchmark');fresh.add_argument('--out',type=Path,default=ROOT/'results_followup')
    fresh.add_argument('--seed-start',type=int,default=200001);fresh.add_argument('--samples',type=int,default=55)
    predict_cmd=sub.add_parser('predict');predict_cmd.add_argument('--inputs',type=Path,required=True)
    predict_cmd.add_argument('--probes',type=Path,required=True);predict_cmd.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.cmd=='predict':predictions(args.inputs,args.probes,args.out)
    elif args.cmd=='benchmark':benchmark(args.out.resolve(),args.seed_start,args.samples)
    else:
        results=args.results.resolve();out=results/'followup';out.mkdir(exist_ok=True)
        probes=out/'probes';inputs=results/'blind_inputs'
        collect(inputs,lambda seed:results/'cases'/f'blind_{seed}'/'faults.cfg',probes)
        saved=out/'predictions.json';predictions(inputs,probes,saved)
        score(saved,results/'blind_truth.csv',out,'Reviewed original samples (development evaluation)')
if __name__=='__main__':main()
