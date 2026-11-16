"""Uygulama ayarları. Veri klasörü EXAMPREP_DATA_DIR ile değiştirilebilir."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("EXAMPREP_DATA_DIR", PROJECT_ROOT / "data"))
DB_FILENAME = "examprep.db"
PAGES_DIRNAME = "pages"

# Benzerlik kontrolü (üretilen soru ↔ kaynak sorular)
EMBEDDING_MODEL = os.environ.get(
    "EXAMPREP_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
# Yüksek eşik: bu kosinüsün üstü veri örtüşmesinden bağımsız olarak kopya sayılır
# (ayrıntılı kurallar: examprep/similarity.py)
SIMILARITY_THRESHOLD = float(os.environ.get("EXAMPREP_SIMILARITY_THRESHOLD", "0.95"))
