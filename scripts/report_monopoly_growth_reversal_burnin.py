"""Render the revised reversal experiment without overwriting its predecessor."""
import csv
import json
from simulate_monopoly_growth_reversal_burnin import ROOT, OUT, make_design
from report_monopoly_growth_reversal import main as report


def main():
    initialization = json.loads((OUT/'initialization.json').read_text())
    with (OUT/'competitive_prehistory.csv').open(newline='', encoding='utf-8') as f:
        prehistory = [{k:float(v) for k,v in row.items()} for row in csv.DictReader(f)]
    report(design_factory=make_design, output=OUT,
        figure_directory=ROOT/'figures_rewrite'/'monopoly_growth_reversal_burnin',
        initialization=initialization, prehistory=prehistory)


if __name__ == '__main__':
    main()
