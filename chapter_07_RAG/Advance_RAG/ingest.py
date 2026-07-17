"""CLI ingestion — build the Qdrant collection from a CSV/XLSX without the UI.

Examples
--------
    python ingest.py testcase/VWO_2000_Test_Cases.csv
    python ingest.py data/test_cases.csv \
        --text-cols title,steps,expected,tags \
        --meta-cols id,jira_id,priority,module
"""

from __future__ import annotations

import argparse

from rag import config, dataio, models, pipeline, qdrant_store


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest a CSV/XLSX into Qdrant")
    ap.add_argument("path", help="path to .csv / .xlsx / .xls")
    ap.add_argument("--text-cols", default="", help="comma-separated columns to embed")
    ap.add_argument("--meta-cols", default="", help="comma-separated payload columns")
    args = ap.parse_args()

    df = dataio.read_table(args.path)
    guess_text, guess_meta = dataio.guess_columns(list(df.columns))
    text_cols = [c for c in args.text_cols.split(",") if c] or guess_text
    meta_cols = [c for c in args.meta_cols.split(",") if c] or guess_meta

    print(f"Loaded {df.shape[0]} rows x {df.shape[1]} cols from {args.path}")
    print(f"  text cols: {text_cols}")
    print(f"  meta cols: {meta_cols}")
    print(f"  backend  : {models.backend_name()} ({models.get_embedder().name})")

    rows = dataio.to_rows(df)
    pipeline.ingest_sync(rows, text_cols, meta_cols)
    print(f"Collection '{config.COLLECTION_NAME}' now has "
          f"{qdrant_store.count()} points.")


if __name__ == "__main__":
    main()
