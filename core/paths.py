from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATA_SRC_DIR = DATA_DIR / "external"
DATA_DST_DIR = DATA_DIR / "processed"
DUCKDB_PATH = DATA_DST_DIR / "bea.duckdb"
