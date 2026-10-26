import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze import equivalence_class
from logs import public_log
from probe import probe_binary
from probe_classifier import coupling_from_reads
from run import command


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.build=Path(cls.temporary.name)
        cls.simulator=probe_binary(cls.build)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_equivalence_does_not_hide_coupling_or_silent_retention(self):
        self.assertEqual(equivalence_class('SAF0'),equivalence_class('TF_UP'))
        for label in ('CFIN','CFID','CFST','NONE','DRF'):
            self.assertEqual(equivalence_class(label),label)
        self.assertNotEqual(equivalence_class('NONE'),equivalence_class('DRF'))

    def test_logs_keep_diagnostic_and_drop_machine_prefix(self):
        raw='FATAL: Z:\\lab\\private user\\project\\tb\\tb_mbist.sv:79: Sequence mismatch at operation 1'
        cleaned=public_log(raw)
        self.assertEqual(cleaned,'FATAL: tb\\tb_mbist.sv:79: Sequence mismatch at operation 1')
        self.assertNotIn('private user',cleaned)

    def test_probe_coupling_parameter_matrix_and_stuck_controls(self):
        count=0
        for victim,aggressor in ((0,255),(255,0)):
            for kind in (5,6,7):
                for value in ((0,) if kind==5 else (0,1)):
                    for trigger in ((0,) if kind==5 else (0,1)):
                        with self.subTest(kind=kind,victim=victim,value=value,trigger=trigger):
                            hit=self.run_probe(kind,victim,aggressor,value,trigger)
                            self.assertEqual(hit['prediction'],{5:'CFIN',6:'CFID',7:'CFST'}[kind])
                            self.assertEqual(hit['aggressor'],aggressor)
                            if kind!=5:
                                self.assertEqual(hit['value'],value)
                                self.assertEqual(hit['trigger'],trigger)
                            count+=1
        for kind in (1,2,3,4):
            with self.subTest(control=kind):self.assertIsNone(self.run_probe(kind,0,255,0,0))
        self.assertEqual(count,18)

    def run_probe(self,kind,victim,aggressor,value,trigger):
        cfg=self.build/'fixture.cfg';log=self.build/'observations.csv'
        cfg.write_text(f'1\n{kind} {victim} {aggressor} {value} {trigger} 10000\n')
        text=command(self.simulator+[f'+CFG={cfg.as_posix()}',f'+LOG={log.as_posix()}',f'+VICTIM={victim}','+SEED=7'])
        self.assertIn('PASS coupling probe',text)
        result=coupling_from_reads(log,7,victim)
        # Truncated observations must never be treated as a valid diagnosis.
        with log.open(newline='') as stream:rows=list(csv.DictReader(stream))
        with log.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows[:-1])
        with self.assertRaises(ValueError):coupling_from_reads(log,7,victim)
        return result

if __name__=='__main__':unittest.main()
