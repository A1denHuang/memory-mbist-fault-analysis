"""Check publishable text for machine-specific absolute paths.

--clean rewrites existing result logs only; future logs are normalized at source.
Git history is intentionally not rewritten by this tool.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
from logs import public_log

ROOT=Path(__file__).resolve().parents[1]
PATH_PATTERN=re.compile(r'\b[A-Za-z]:[\\/]|/' + r'home/[^/\s]+/')

SUMMARY_FILES={
    'results':{'report.md','verification.json','blind_metrics.json','blind_confusion.csv',
        'fault_element_coverage.csv','functional_coverage.json','coupling_order_coverage.json',
        'delivery_audit.json','mutation_report.json'},
    'results_questa':{'report.md','verification.json','blind_metrics.json','blind_confusion.csv',
        'fault_element_coverage.csv','functional_coverage.json','coupling_order_coverage.json',
        'native_assertion_summary.json'},
    'results_followup':{'report.md','metrics.json'},
}


def published_result(relative):
    """Only summaries and report figures belong in the source repository."""
    relative=Path(relative);parts=relative.parts
    if not parts or parts[0] not in SUMMARY_FILES:return True
    if len(parts)==2:return parts[1] in SUMMARY_FILES[parts[0]]
    if len(parts)!=3:return False
    if parts[0] in ('results','results_questa') and parts[1]=='figures':
        return relative.suffix=='.png'
    if parts[:2]==('results','followup'):return parts[2] in ('report.md','metrics.json')
    return parts==('results_questa','native_configs','native_random_summary.json')


def files():
    raw=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
    return sorted({Path(p.decode('utf-8')) for p in raw.split(b'\0') if p})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--clean',action='store_true')
    args=parser.parse_args();changed=0;issues=[];layout_issues=[]
    for relative in files():
        if not published_result(relative):layout_issues.append(relative.as_posix())
        path=ROOT/relative
        if not path.is_file() or path.suffix=='.png':continue
        try:text=path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:continue
        if args.clean and relative.parts[0] in ('results','results_questa','results_followup') and path.suffix in ('.log','.txt','.json','.md'):
            cleaned=public_log(text,ROOT)
            if path.suffix=='.json':json.loads(cleaned)
            if text!=cleaned:
                path.write_text(cleaned,encoding='utf-8');changed+=1
            text=cleaned
        # This file contains an intentionally fictitious path for normalization tests.
        if relative.as_posix()=='tests/test_analysis.py':continue
        if PATH_PATTERN.search(text):issues.append(relative.as_posix())
    print(json.dumps(dict(normalized_files=changed,absolute_path_findings=issues,
                         generated_result_findings=layout_issues),indent=2))
    if issues or layout_issues:raise SystemExit(1)
if __name__=='__main__':main()
