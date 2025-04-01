import os
from pathlib import Path

# Define base directory relative to this file's location
BASE_DIR = Path(__file__).resolve().parent.parent.parent # -> backend/

UPLOAD_DIR = BASE_DIR / "data" / "uploads"
RESULT_DIR = BASE_DIR / "data" / "results"

# Create directories if they don't exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# Convert Path objects to strings for functions expecting strings
UPLOAD_DIR_STR = str(UPLOAD_DIR)
RESULT_DIR_STR = str(RESULT_DIR)

CPDB_DATABASE_PATH = os.getenv(
    "CPDB_DATABASE_PATH",
    # Replace with the actual path to your downloaded/unzipped DB directory
    BASE_DIR/"cellphonedb_data/v5.0.0/cellphonedb.zip"
)