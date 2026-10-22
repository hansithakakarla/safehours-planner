"""Create the small dataset that gets committed and deployed to Render.

Usage (run once on your computer, from the repo folder):
    python prepare_data.py path/to/full/city_hour.csv

It keeps only Bengaluru, Chennai and Delhi and only the City, Datetime and
AQI columns, then writes data/city_hour.csv (a few MB instead of ~70 MB).
"""
import sys
from pathlib import Path

import pandas as pd

CITIES = {"bengaluru", "bangalore", "chennai", "delhi"}
KEEP = ["City", "Datetime", "AQI"]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    source = Path(sys.argv[1])
    out = Path(__file__).resolve().parent / "data" / "city_hour.csv"

    df = pd.read_csv(source, usecols=lambda c: str(c).strip() in KEEP)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df["City"].astype(str).str.strip().str.casefold().isin(CITIES)]

    out.parent.mkdir(parents=True, exist_ok=True)
    same_file = source.resolve() == out.resolve()
    df[KEEP].to_csv(out, index=False)
    print(f"Wrote {len(df):,} rows to {out}"
          + (" (overwrote the full file)" if same_file else ""))


if __name__ == "__main__":
    main()
