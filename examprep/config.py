"""Uygulama ayarları. Veri klasörü EXAMPREP_DATA_DIR ile değiştirilebilir."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("EXAMPREP_DATA_DIR", PROJECT_ROOT / "data"))
DB_FILENAME = "examprep.db"
PAGES_DIRNAME = "pages"
