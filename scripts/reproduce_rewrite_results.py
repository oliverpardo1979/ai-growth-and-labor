"""Check stored results, or explicitly recompute both published comparisons."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='check saved evidence (default)')
    mode.add_argument('--solve', action='store_true', help='recompute all eight paths and audits')
    args = parser.parse_args()
    if args.solve:
        subprocess.run([sys.executable, 'scripts/simulate_rewrite_illustrative_rsi.py'],
                       cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                    '-p', 'test_publication_results.py', '-v'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
