"""Reproducible compile, directed tests, randomized regression and blind holdout.

No analysis import is made until every RTL simulation has passed.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KINDS = {1:'SAF0', 2:'SAF1', 3:'TF_UP', 4:'TF_DOWN', 5:'CFIN', 6:'CFID',
         7:'CFST', 8:'AF', 9:'ROW', 10:'COL', 11:'DRF'}

def command(args, *, cwd=ROOT, allow_artifact=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=120)
    output = result.stdout + result.stderr
    # Some MSYS Icarus builds return 1 after successful code generation under
    # Windows restricted process execution. Only accept a NEW nonempty product
    # with no diagnostic error; subsequent vvp execution still must return 0.
    if re.search(r'\*\*\s+(?:Error|Fatal):|Assertion.*failed|Fatal:',output,re.I):
        raise RuntimeError(f'Simulation/compiler diagnostic failure: {args}\n{output}')
    if result.returncode and not (allow_artifact and allow_artifact.is_file()
            and allow_artifact.stat().st_size > 0
            and not re.search(r'error|syntax|sorry|fatal', output, re.I)):
        raise RuntimeError(f'Command failed ({result.returncode}): {args}\n{output}')
    return output

def compile_tb(build, top, sources, retention=0, simulator='iverilog'):
    if simulator == 'questa':
        lib = build / 'work'
        if not lib.exists():
            command(['vlib', 'work'],cwd=build)
        text=command(['vlog','-work','work','-sv','+define+ENABLE_SVA', *sources,
                 ROOT/'tb/mbist_sva.sv',ROOT/'tb/mbist_coverage.sv'],cwd=build)
        (build/f'compile_{top}_{retention}.log').write_text(text,encoding='utf-8')
        return ['vsim','-c','-coverage','-onfinish','stop','-lib','work',top,
                f'-gRETENTION_CYCLES={retention}'] if top=='tb_mbist' else [
                'vsim','-c','-coverage','-onfinish','stop','-lib','work',top]
    product = build / f'{top}_{retention}.vvp'
    product.unlink(missing_ok=True)
    args = ['iverilog','-g2012','-Wall','-s',top,'-o',product]
    if top == 'tb_mbist':
        args += [f'-Ptb_mbist.RETENTION_CYCLES={retention}']
    output=command(args+sources, allow_artifact=product)
    (build/f'compile_{top}_{retention}.log').write_text(output,encoding='utf-8')
    return ['vvp',product]

def fault(kind, victim=58, aggressor=12, value=0, trigger=1, retention=10000):
    return dict(kind=kind, victim=victim, aggressor=aggressor, value=value,
                trigger=trigger, retention=retention)

def random_fault(rng, kind=None):
    victim, aggressor = rng.sample(range(256),2)
    return fault(kind or rng.randint(1,11),victim,aggressor,rng.randrange(2),rng.randrange(2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',type=int,default=60)
    p.add_argument('--blind-seeds',type=int,default=55)
    p.add_argument('--out',type=Path,default=ROOT/'results')
    p.add_argument('--simulator',choices=['iverilog','questa'],default='iverilog')
    p.add_argument('--no-analysis',action='store_true')
    p.add_argument('--resume',action='store_true',help='Reuse matching, successfully completed cases after an interrupted run')
    args=p.parse_args()
    if args.seeds<50 or args.blind_seeds<50:
        p.error('Acceptance requires at least 50 regression and 50 blind seeds')
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    build=out/'build'; build.mkdir(exist_ok=True)
    cases=out/'cases'; cases.mkdir(exist_ok=True)
    sources=[ROOT/'rtl/mbist_controller.sv',ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_mbist.sv']
    base=compile_tb(build,'tb_mbist',sources,simulator=args.simulator)
    retained=compile_tb(build,'tb_mbist',sources,12000,simulator=args.simulator)
    micro=compile_tb(build,'tb_fault_model',[ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_fault_model.sv'],simulator=args.simulator)
    def simulate(cmd,plusargs,coverage_path=None):
        if args.simulator=='questa':
            target=(coverage_path or build/'units.ucdb').as_posix()
            return command(cmd+plusargs+['-do',f'onerror {{quit -code 1}}; run -all; coverage report -assert; coverage report -cvg; coverage save {{{target}}}; quit -code 0'],cwd=build)
        return command(cmd+plusargs)
    text=simulate(micro,[])
    if 'PASS fault-model' not in text: raise RuntimeError(text)
    (out/'fault_model_units.log').write_text(text,encoding='utf-8')
    manifest=[]
    def run(name, fs, seed=0, mode=0, pause=False, expected_detection=None, group='directed'):
        directory=cases/name; directory.mkdir(exist_ok=True)
        cfg=directory/'faults.cfg'
        config_text=str(len(fs))+'\n'+''.join(
            f"{f['kind']} {f['victim']} {f['aggressor']} {f['value']} {f['trigger']} {f['retention']}\n" for f in fs)
        reusable=(args.resume and cfg.exists() and cfg.read_text()==config_text
                  and (directory/'summary.txt').exists() and (directory/'fails.csv').exists()
                  and (directory/'simulation.log').exists()
                  and (args.simulator!='questa' or (directory/'coverage.ucdb').exists())
                  and (group!='directed' or (directory/'operations.csv').exists()))
        cfg.write_text(config_text,encoding='ascii')
        plus=[f'+CFG={cfg.as_posix()}',f'+LOG={(directory/"fails.csv").as_posix()}',
              f'+SUMMARY={(directory/"summary.txt").as_posix()}', f'+SEED={seed}',f'+STOP={mode}']
        if group=='directed': plus += [f'+TRACE={(directory/"operations.csv").as_posix()}']
        if name in ('clean_diag','SAF1_diag'): plus += [f'+VCD={(directory/"wave.vcd").as_posix()}']
        # Recompile separate Questa work libraries so the pause generic stays local.
        text=(directory/'simulation.log').read_text(encoding='utf-8') if reusable else simulate(retained if pause else base,plus,directory/'coverage.ucdb')
        (directory/'simulation.log').write_text(text,encoding='utf-8')
        if 'PASS seed=' not in text: raise RuntimeError(text)
        summary=dict((k,int(v)) for k,v in re.findall(r'(operations|failures|pass|cycles)=(\d+)',(directory/'summary.txt').read_text()))
        if expected_detection is not None and (summary['failures']>0)!=expected_detection:
            raise AssertionError(f'{name}: detection expectation failed: {summary}')
        if not fs and summary['operations']!=2560: raise AssertionError('Clean operation count')
        manifest.append(dict(name=name,group=group,seed=seed,mode=mode,pause=pause,
                             faults=fs,**summary))
    for mode in (0,1): run('clean_diag' if mode==0 else 'clean_stop',[],mode=mode,expected_detection=False)
    for kind,label in KINDS.items():
        for mode in (0,1):
            run(f'{label}_{"stop" if mode else "diag"}',[fault(kind)],mode=mode,
                expected_detection=kind!=11)
    for kind in (5,6,7):
        for victim,aggressor in ((0,255),(255,0),(15,16),(16,15)):
            for value in (0,1):
                for trigger in (0,1):
                    run(f'coupling_{kind}_{victim}_{aggressor}_{value}_{trigger}',
                        [fault(kind,victim,aggressor,value,trigger)],expected_detection=True)
    for victim in (0,15,16,240,255):
        for kind in (1,2,3,4,8,9,10):
            run(f'boundary_{kind}_{victim}',[fault(kind,victim,127,1)],expected_detection=True)
    run('retention_pause',[fault(11)],pause=True,expected_detection=True)
    for seed in range(1,args.seeds+1):
        rng=random.Random(seed)
        fs=[random_fault(rng) for _ in range(rng.randint(1,3))]
        run(f'random_{seed:03d}_diag',fs,seed=seed,group='random')
        run(f'random_{seed:03d}_stop',fs,seed=seed,mode=1,group='random')
    # Independent, balanced single-fault holdout. Classification sees ONLY CSVs.
    blind_inputs=out/'blind_inputs'; blind_inputs.mkdir(exist_ok=True)
    truth=[]
    for index in range(args.blind_seeds):
        seed=100001+index; kind=index%11+1
        fs=[random_fault(random.Random(seed),kind)]
        name=f'blind_{seed}'
        run(name,fs,seed=seed,group='blind')
        shutil.copyfile(cases/name/'fails.csv',blind_inputs/f'{seed}.csv')
        truth.append(dict(seed=seed,truth=KINDS[kind]))
    if args.simulator=='questa':
        text=command(['vcover','merge',out/'coverage_merged.ucdb',
                      *[p.relative_to(cases) for p in sorted(cases.glob('*/coverage.ucdb'))]],cwd=cases)
        (out/'coverage_merge.log').write_text(text,encoding='utf-8')
        text=command(['vcover','report','-cvg','-assert','-details',out/'coverage_merged.ucdb'])
        (out/'native_coverage.txt').write_text(text,encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with (out/'blind_truth.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['seed','truth']);w.writeheader();w.writerows(truth)
    summary=dict(simulator=args.simulator,simulations=len(manifest),random_seeds=args.seeds,
                 blind_seeds=args.blind_seeds,scoreboard='all passed',
                 sva='enabled in Questa' if args.simulator=='questa' else 'portable procedural equivalents passed; native SVA not executed')
    (out/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    if not args.no_analysis:
        command([sys.executable,ROOT/'scripts/analyze.py','report','--results',out])
        print(f'Analysis report: {out / "report.md"}',flush=True)

if __name__=='__main__': main()
