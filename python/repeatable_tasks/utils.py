import os
import re
from pathlib import Path
import glob
import shutil


def clean_pgn(pgn_path: Path):
    with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # 1. Remove PGN comments {...}
    text = re.sub(r"\{[^}]*\}", "", text)

    # 2. Remove move numbers like "1..." (black move numbers)
    text = re.sub(r"\b\d+\.{3}\s*", "", text)

    # 3. Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

    tmp_path = pgn_path.with_suffix(".clean.pgn")

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)

    os.replace(tmp_path, pgn_path)

def concat_pgns(pgn_path: Path):
    concat_path = pgn_path / "concat.pgn"

    if concat_path.exists():
        concat_path.unlink()

    files = sorted(pgn_path.glob("*.pgn"))

    copy = shutil.copyfileobj
    buffer_size = 16 * 1024 * 1024

    with concat_path.open("wb") as out:
        for fname in files:
            with fname.open("rb") as f:
                copy(f, out, length=buffer_size)