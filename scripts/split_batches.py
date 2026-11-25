"""Split the full batch into two batches at random, the first for dataset version 1 and both for version 2."""

import argparse
from pathlib import Path

import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--raw-dir", default="data/raw")
parser.add_argument("--fraction", type=float, default=0.6, help="share of rows that stays in the first batch")
parser.add_argument("--seed", type=int, default=42)
args = parser.parse_args()

if not 0.0 < args.fraction < 1.0:
    raise SystemExit("--fraction must be between 0 and 1")

raw_dir = Path(args.raw_dir)
first_path = raw_dir / "batch_01_baseline.csv"
second_path = raw_dir / "batch_02_new_arrival.csv"

# Guard, so a second run cannot split the already split file again
if second_path.exists():
    raise SystemExit(f"{second_path} already exists, the data is already split.")

# Same reading as data.py, so the text None in Intersection_Type survives
frame = pd.read_csv(first_path, keep_default_na=False, na_values=[""])

# Random rows go to the first batch, the rest to the second, the order inside each batch is kept
first = frame.sample(frac=args.fraction, random_state=args.seed).sort_index()
second = frame.drop(first.index)

first.to_csv(first_path, index=False, lineterminator="\n")
second.to_csv(second_path, index=False, lineterminator="\n")

print(f"{len(frame)} rows -> {first_path.name} {len(first)} rows, {second_path.name} {len(second)} rows")