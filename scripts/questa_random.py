"""Compile and exercise native SystemVerilog constrained random fault_cfg."""
import argparse
import json
from pathlib import Path
from run import ROOT, command, compile_tb

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=20261026)
    p.add_argument('--count',type=int,choices=[1,2,3],default=3)
    p.add_argument('--batch',type=int,default=1,help='Generate independently seeded configs with random 1-3 fault counts')
    p.add_argument('--verify-rtl',action='store_true',help='Run generated configs through Icarus scoreboard in both modes')
    p.add_argument('--out',type=Path,default=ROOT/'results_questa/native_random.cfg')
    a=p.parse_args()
    if a.batch<1:p.error('--batch must be positive')
    out=a.out.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    build=out.parent/'config_build';build.mkdir(exist_ok=True)
    if not (build/'work').exists():command(['vlib','work'],cwd=build)
    text=command(['vlog','-sv',ROOT/'tb/fault_cfg.sv',ROOT/'tb/tb_random_cfg.sv'],cwd=build)
    text+=command(['vsim','-c','-onfinish','stop','tb_random_cfg',f'+SEED={a.seed}',
                   f'+COUNT={a.count}',f'+OUT={out.as_posix()}',f'+BATCH={a.batch}',
                   '-do','onerror {quit -code 1}; run -all; quit -code 0'],cwd=build)
    paths=[]
    for index in range(a.batch):
        path=out if a.batch==1 else Path(f'{out}_{a.seed+index}.cfg')
        paths.append(path)
        records=path.read_text().splitlines();count=int(records[0])
        assert 1<=count<=3 and len(records)==count+1
        if a.batch==1:assert count==a.count
        for record in records[1:]:
            kind,victim,aggressor,value,trigger,retention=map(int,record.split())
            assert 1<=kind<=11 and 0<=victim<256 and 0<=aggressor<256
            assert kind not in (5,6,7,8) or victim!=aggressor
            assert value in (0,1) and trigger in (0,1) and retention>0
    (out.parent/'native_random.log').write_text(text,encoding='utf-8')
    if a.verify_rtl:
        simulator=compile_tb(build,'tb_mbist',[ROOT/'rtl/mbist_controller.sv',
            ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_mbist.sv'])
        for index,path in enumerate(paths):
            for mode in (0,1):
                prefix=out.parent/f'checked_{a.seed+index}_{mode}'
                output=command(simulator+[f'+CFG={path.as_posix()}',f'+SEED={a.seed+index}',f'+STOP={mode}',
                    f'+LOG={prefix.as_posix()}.csv',f'+SUMMARY={prefix.as_posix()}.txt'])
                assert 'PASS seed=' in output
                Path(f'{prefix}.log').write_text(output,encoding='utf-8')
    (out.parent/'native_random_summary.json').write_text(json.dumps(dict(
        generator='SystemVerilog fault_cfg.randomize() in Questa',seeds=a.batch,
        initial_seed=a.seed,constraint_checks='PASS',
        rtl_scoreboard_runs=2*a.batch if a.verify_rtl else 0,
        rtl_simulator='iverilog' if a.verify_rtl else None),indent=2),encoding='utf-8')
    print(f'PASS native SV random configurations: {a.batch}, output {out}')
if __name__=='__main__':main()
