"""Read uploaded CSV / XLSX / XLS files into rows + a preview summary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        # utf-8-sig transparently strips a UTF-8 BOM if present.
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig",
                         keep_default_na=False, na_values=[])
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def preview(df: pd.DataFrame, n: int = 5) -> dict:
    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "head": df.head(n).to_dict(orient="records"),
    }


def to_rows(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records")


def guess_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    """Best-effort split into (text_cols, meta_cols) for the picker defaults."""
    text_pref = ["title", "steps", "expected", "tags", "preconditions",
                 "description", "summary", "testcase description", "teststeps",
                 "expected result", "precondition"]
    meta_pref = ["id", "jira_id", "priority", "module", "component", "status",
                 "scenario tid", "is automated"]
    lower = {c.lower(): c for c in columns}
    text_cols = [lower[t] for t in text_pref if t in lower]
    meta_cols = [lower[m] for m in meta_pref if m in lower]
    # Fallbacks so nothing is empty.
    if not text_cols:
        text_cols = [c for c in columns if c not in meta_cols][:4] or columns[:1]
    if not meta_cols:
        meta_cols = [c for c in columns if c not in text_cols][:4]
    return text_cols, meta_cols
