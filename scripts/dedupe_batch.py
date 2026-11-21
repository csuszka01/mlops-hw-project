"""Remove exact duplicate rows from a batch CSV, keeping the first copy."""

import sys
from pathlib import Path

import pandas as pd

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/batch_01_baseline.csv")

# Same reading as data.py, so the text None in Intersection_Type survives
frame = pd.read_csv(path, keep_default_na=False, na_values=[""])
deduped = frame.drop_duplicates(keep="first")
deduped.to_csv(path, index=False, lineterminator="\n")

print(f"{path} {len(frame)} rows -> {len(deduped)} rows ({len(frame) - len(deduped)} removed)")