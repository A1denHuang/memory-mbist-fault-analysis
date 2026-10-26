"""Prove the scoreboard detects representative controller bugs.

Creates temporary mutants under results/build, never edits the delivered RTL.
"""
import json
from pathlib import Path
import subprocess
from run import ROOT, command

def main():
    source=(ROOT/'rtl/mbist_controller.sv').read_text()
    build=ROOT/'results/build/mutations';build.mkdir(parents=True,exist_ok=True)
    mutations=[
        ('address_skip',"address + 1'b1", "address + 2'd2",False),
        ('wrong_read_expectation','read_expected <= exp_bit','read_expected <= ~exp_bit',False),
        ('missing_fail_valid','pass <= 0; fail_valid <= 1','pass <= 0; fail_valid <= 0',True),
        ('bad_operation_count','operation_count + 1','operation_count + 2',False),
        ('ignore_stop','rdata != read_expected && stop_latched','1\'b0',True),
    ]
    results=[]
    for name,old,new,faulted in mutations:
        assert old in source,name
        rtl=build/f'{name}.sv';rtl.write_text(source.replace(old,new),encoding='utf-8')
        product=build/f'{name}.vvp';product.unlink(missing_ok=True)
        command(['iverilog','-g2012','-s','tb_mbist','-o',product,rtl,
                 ROOT/'tb/sram_fault_model.sv',ROOT/'tb/tb_mbist.sv'],allow_artifact=product)
        config=build/f'{name}.cfg';config.write_text('1\n2 58 12 0 1 10000\n' if faulted else '0\n')
        child=subprocess.run(['vvp',str(product),f'+CFG={config.as_posix()}',
            f'+LOG={(build/(name+".csv")).as_posix()}',
            f'+SUMMARY={(build/(name+".txt")).as_posix()}',
            f'+STOP={int(name=="ignore_stop")}'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        output=child.stdout+child.stderr
        if child.returncode==0 or 'FATAL' not in output:
            raise AssertionError(f'Mutant escaped: {name}\n{output}')
        (build/f'{name}.log').write_text(output,encoding='utf-8')
        results.append(dict(mutation=name,status='detected',diagnostic=output.splitlines()[0]))
    (ROOT/'results/mutation_report.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(f'PASS scoreboard detected {len(results)}/{len(mutations)} representative RTL bugs')
if __name__=='__main__':main()
